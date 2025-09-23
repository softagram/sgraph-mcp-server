"""
Model management MCP tools.

Tools for loading models and getting overview information.
"""

from pydantic import BaseModel

from src.core.model_manager import ModelManager
from src.services.overview_service import OverviewService
from src.utils.validators import validate_path

# Initialize components
model_manager = ModelManager()


class SGraphLoadModel(BaseModel):
    path: str


class SGraphGetModelOverview(BaseModel):
    model_id: str
    max_depth: int = 3
    include_counts: bool = True


def register_tools(mcp):
    """Register model tools with the MCP server."""
    
    @mcp.tool()
    async def sgraph_load_model(sgraph_load_model: SGraphLoadModel):
        """Load a sgraph from a file and return the model id."""
        try:
            print(f"🔧 MCP Tool: sgraph_load_model called with path: {sgraph_load_model.path}")
            
            # Validate path
            is_valid, error = validate_path(sgraph_load_model.path, must_exist=True)
            if not is_valid:
                print(f"❌ MCP Tool: Invalid path - {error}")
                return {"error": f"Invalid path: {error}"}
            
            model_id = await model_manager.load_model(sgraph_load_model.path)
            print(f"✅ MCP Tool: Model loaded successfully with ID: {model_id}")
            return {"model_id": model_id}
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {str(e)}"
            print(f"❌ MCP Tool: {error_msg}")
            return {"error": error_msg}
        except TimeoutError as e:
            error_msg = f"Loading timeout: {str(e)}"
            print(f"⏰ MCP Tool: {error_msg}")
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Loading failed: {str(e)}"
            print(f"💥 MCP Tool: {error_msg}")
            return {"error": error_msg}

    @mcp.tool()
    async def sgraph_get_model_overview(
        sgraph_get_model_overview: SGraphGetModelOverview,
    ):
        """Get hierarchical overview of the model structure up to specified depth."""
        model = model_manager.get_model(sgraph_get_model_overview.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            result = OverviewService.get_model_overview(
                model,
                sgraph_get_model_overview.max_depth,
                sgraph_get_model_overview.include_counts,
            )
            return result
        except Exception as e:
            return {"error": f"Model overview failed: {str(e)}"}


# Export the model manager instance for use by other tools
def get_model_manager() -> ModelManager:
    """Get the shared model manager instance."""
    return model_manager