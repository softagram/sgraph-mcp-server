"""
Model management for sgraph models.

Handles loading, caching, and lifecycle management of sgraph models.
"""

import asyncio
import logging
import time
import os
from typing import Optional, Dict

import nanoid
from sgraph import SGraph
from sgraph.loader.modelloader import ModelLoader

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages sgraph model loading and caching."""

    # Matches the timeout on load_model(); bounds how long a tool call waits for a
    # deferred parse, not the parse itself.
    DEFERRED_LOAD_TIMEOUT = 300.0

    def __init__(self):
        self._models: Dict[str, SGraph] = {}
        self._model_paths: Dict[str, str] = {}  # model_id -> path
        self._loader = ModelLoader()
        self._default_model_id: Optional[str] = None
        self.default_scope: Optional[str] = None
        # A model configured at startup but not parsed yet. Parsing is deferred to
        # the first tool call so a session that never queries sgraph pays nothing:
        # a 112 MB model costs ~7 s of CPU and ~635 MB of heap, and every Claude
        # Code session spawns its own stdio server.
        self._deferred_path: Optional[str] = None
        self._deferred_error: Optional[str] = None
        self._deferred_task: Optional[asyncio.Task] = None
        logger.info("🔧 ModelManager initialized")
    
    def set_deferred_model(self, path: str, default_scope: Optional[str] = None) -> None:
        """Record the model to load on first use, without parsing it."""
        self._deferred_path = path
        self._deferred_task = None
        if default_scope:
            self.default_scope = default_scope

        # Deferring the parse must not defer the news that the path is wrong, so
        # stat it now. This stays a warning rather than a hard failure: the file
        # may be an analysis still being written, and the load is retried on use.
        if os.path.exists(os.path.expanduser(path)):
            self._deferred_error = None
            logger.info(f"🕓 Model deferred until first use: {path}")
        else:
            self._deferred_error = f"Model file does not exist: {path}"
            logger.warning(f"⚠️ Deferred model path does not exist (yet): {path}")

    def no_model_error(self) -> str:
        """Explain to a caller why no model is available.

        A deferred model that failed to load would otherwise be invisible: the
        tool would report "no model loaded" and hide the real cause.
        """
        if self._deferred_error:
            return (
                f"Configured model failed to load ({self._deferred_path}): "
                f"{self._deferred_error}"
            )
        return "No model loaded. Call sgraph_load_model first."

    def _record_deferred_outcome(self, task: "asyncio.Task") -> None:
        """Consume a finished parse's result so a failure is never lost.

        Every caller may have been cancelled by then, leaving nobody to observe
        the exception; asyncio would otherwise only surface it as "Task exception
        was never retrieved" at garbage-collection time.
        """
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            self._deferred_error = str(error)
            logger.error(f"💥 Deferred model load failed: {error}")

    async def ensure_default_model(self) -> Optional[str]:
        """Return the default model ID, parsing a deferred model on first use.

        Returns None - never raises - when there is nothing to load or the load
        failed; `no_model_error()` then carries the reason. A failed load stays
        retryable, so a transient I/O error does not break the session for good.
        """
        if self._default_model_id is not None:
            return self._default_model_id
        if self._deferred_path is None:
            return None

        # No lock: there is no await between this check and create_task, so the
        # event loop cannot interleave another caller here. Every concurrent
        # caller therefore attaches to one task rather than queueing behind a lock
        # and each starting its own parse after the first one fails.
        if self._deferred_task is None or self._deferred_task.done():
            # A finished task can only be a failed one - success returns above -
            # so this both starts the first parse and retries a broken one.
            path = self._deferred_path
            logger.info(f"⏳ Loading deferred model on first use: {path}")
            # Parse off the event loop so the MCP connection stays serviceable.
            self._deferred_task = asyncio.create_task(
                asyncio.to_thread(self.load_model_sync, path)
            )
            self._deferred_task.add_done_callback(self._record_deferred_outcome)
        task = self._deferred_task

        try:
            # Shielded: a tool call cancelled by the client (its timeout, or the
            # user interrupting) must not abandon a parse that may be gigabytes
            # in. The next call attaches to this same parse instead of starting a
            # second one alongside it. wait_for bounds the waiting, not the parse.
            model_id = await asyncio.wait_for(
                asyncio.shield(task), timeout=self.DEFERRED_LOAD_TIMEOUT
            )
        except Exception as e:
            # _record_deferred_outcome logs and records a parse failure; a timeout
            # here leaves the parse running for the next caller to pick up.
            self._deferred_error = self._deferred_error or str(e)
            return None

        self._deferred_error = None
        self._default_model_id = model_id
        # Only reached on success. A parse whose callers were all cancelled sets
        # _default_model_id from load_model_sync instead, and the check at the top
        # of this method then shadows the stale _deferred_path.
        self._deferred_path = None
        return model_id

    async def load_model(self, path: str) -> str:
        """Load a sgraph model with comprehensive logging and error handling."""
        logger.info(f"🔍 Starting to load model from: {path}")
        
        # Validate file exists
        if not os.path.exists(path):
            error_msg = f"Model file does not exist: {path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Check file size for logging
        file_size = os.path.getsize(path)
        logger.info(f"📁 File size: {file_size / (1024*1024):.1f} MB")
        
        start_time = time.perf_counter()
        
        try:
            logger.info(f"⏳ Loading model using ModelLoader...")
            # Use asyncio.to_thread with timeout to prevent hanging
            model = await asyncio.wait_for(
                asyncio.to_thread(self._loader.load_model, path),
                timeout=300.0  # 5 minute timeout for large models
            )
            
            load_time = time.perf_counter() - start_time
            logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")
            
            # Generate unique model ID
            model_id = nanoid.generate(size=24)
            logger.info(f"🆔 Generated model ID: {model_id}")
            
            # Store model in memory cache
            self._models[model_id] = model
            self._model_paths[model_id] = os.path.abspath(path)
            logger.info(f"💾 Model cached in memory (total models: {len(self._models)})")
            
            # Log basic model info
            if hasattr(model, 'rootNode') and model.rootNode:
                logger.info(f"🌳 Model root: {model.rootNode.name if model.rootNode.name else 'unnamed'}")
                logger.info(f"👶 Root children: {len(model.rootNode.children)}")
            
            return model_id
            
        except asyncio.TimeoutError:
            error_msg = f"Model loading timed out after 60 seconds: {path}"
            logger.error(f"⏰ {error_msg}")
            raise TimeoutError(error_msg)
            
        except Exception as e:
            load_time = time.perf_counter() - start_time
            error_msg = f"Failed to load model after {load_time:.2f} seconds: {str(e)}"
            logger.error(f"💥 {error_msg}")
            raise RuntimeError(error_msg) from e
    
    def load_model_sync(self, path: str) -> str:
        """Load a model synchronously (for startup auto-load)."""
        logger.info(f"🔍 Sync-loading model from: {path}")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file does not exist: {path}")

        # Check if already loaded from this path
        abs_path = os.path.abspath(path)
        for mid, mpath in self._model_paths.items():
            if mpath == abs_path:
                logger.info(f"♻️ Model already loaded from {path}, reusing ID: {mid}")
                return mid

        file_size = os.path.getsize(path)
        logger.info(f"📁 File size: {file_size / (1024*1024):.1f} MB")

        start_time = time.perf_counter()
        model = self._loader.load_model(path)
        load_time = time.perf_counter() - start_time
        logger.info(f"✅ Model loaded in {load_time:.2f}s")

        model_id = nanoid.generate(size=24)
        self._models[model_id] = model
        self._model_paths[model_id] = abs_path
        self._default_model_id = model_id
        logger.info(f"🆔 Model ID: {model_id} (set as default)")

        return model_id

    @property
    def default_model_id(self) -> Optional[str]:
        """Get the default model ID (set by auto-load or first loaded model)."""
        return self._default_model_id

    def get_model(self, model_id: str) -> Optional[SGraph]:
        """Retrieve a cached model by ID."""
        return self._models.get(model_id)
    
    def list_models(self) -> Dict[str, Dict]:
        """List all cached models with metadata."""
        models_info = {}
        for model_id, model in self._models.items():
            models_info[model_id] = {
                "root_name": model.rootNode.name if model.rootNode and model.rootNode.name else "unnamed",
                "children_count": len(model.rootNode.children) if model.rootNode else 0,
            }
        return models_info
    
    def clear_cache(self) -> int:
        """Clear all cached models and return count of cleared models."""
        count = len(self._models)
        self._models.clear()
        logger.info(f"🗑️ Cleared {count} models from cache")
        return count
    
    def remove_model(self, model_id: str) -> bool:
        """Remove a specific model from cache."""
        if model_id in self._models:
            del self._models[model_id]
            logger.info(f"🗑️ Removed model {model_id} from cache")
            return True
        return False
