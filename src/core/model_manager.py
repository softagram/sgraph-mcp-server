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
    
    def __init__(self):
        self._models: Dict[str, SGraph] = {}
        self._loader = ModelLoader()
        logger.info("🔧 ModelManager initialized")
    
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
                timeout=60.0  # 60 second timeout
            )
            
            load_time = time.perf_counter() - start_time
            logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")
            
            # Generate unique model ID
            model_id = nanoid.generate(size=24)
            logger.info(f"🆔 Generated model ID: {model_id}")
            
            # Store model in memory cache
            self._models[model_id] = model
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
