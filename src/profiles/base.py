"""
Base profile components shared across all profiles.

Provides the ModelManager instance and common tools like load_model.
"""

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

from src.core.model_manager import ModelManager
from src.utils.validators import validate_path


# Shared ModelManager instance across all profiles
_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Get or create the shared ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


class LoadModelInput(BaseModel):
    """Input for loading a graph model."""
    path: str


def register_load_model(mcp: FastMCP) -> None:
    """Register the shared load_model tool."""

    @mcp.tool()
    async def sgraph_load_model(input: LoadModelInput):
        """Load a graph model from file and return its ID for subsequent queries.
        The first model loaded becomes the default, so later tools may omit model_id.
        Asking again for the default model's path returns the existing ID instantly."""
        try:
            model_manager = get_model_manager()

            # Answer from the default model (the startup model, parsed now if still
            # deferred) only when it is the one asked for; any other path is
            # loaded as a model of its own.
            if model_manager.is_default_path(input.path):
                already_loaded = model_manager.default_model_id is not None
                default_model_id = await model_manager.ensure_default_model()
                if default_model_id:
                    return {
                        "model_id": default_model_id,
                        "cached": already_loaded,
                        "default_scope": model_manager.default_scope,
                    }

            is_valid, error = validate_path(input.path, must_exist=True)
            if not is_valid:
                return {"error": f"Invalid path: {error}"}

            model_id = await model_manager.load_model(input.path)
            return {"model_id": model_id}

        except FileNotFoundError as e:
            return {"error": f"File not found: {e}"}
        except TimeoutError as e:
            return {"error": f"Loading timeout: {e}"}
        except Exception as e:
            return {"error": f"Loading failed: {e}"}
