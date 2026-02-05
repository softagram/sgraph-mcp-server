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
        """Load a graph model from file and return its ID for subsequent queries."""
        try:
            is_valid, error = validate_path(input.path, must_exist=True)
            if not is_valid:
                return {"error": f"Invalid path: {error}"}

            model_manager = get_model_manager()
            model_id = await model_manager.load_model(input.path)
            return {"model_id": model_id}

        except FileNotFoundError as e:
            return {"error": f"File not found: {e}"}
        except TimeoutError as e:
            return {"error": f"Loading timeout: {e}"}
        except Exception as e:
            return {"error": f"Loading failed: {e}"}
