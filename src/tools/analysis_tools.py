"""
Analysis-related MCP tools.

Tools for dependency analysis and bulk operations.
"""

from pydantic import BaseModel
from typing import Optional, List

from src.services.dependency_service import DependencyService
from .model_tools import get_model_manager


class SGraphGetSubtreeDependencies(BaseModel):
    model_id: str
    root_path: str
    include_external: bool = True
    max_depth: Optional[int] = None


class SGraphGetDependencyChain(BaseModel):
    model_id: str
    element_path: str
    direction: str = "outgoing"  # "outgoing", "incoming", or "both"
    max_depth: Optional[int] = None


class SGraphGetMultipleElements(BaseModel):
    model_id: str
    element_paths: List[str]
    additional_fields: List[str] = []


def register_tools(mcp):
    """Register analysis tools with the MCP server."""
    
    @mcp.tool()
    async def sgraph_get_subtree_dependencies(
        sgraph_get_subtree_dependencies: SGraphGetSubtreeDependencies,
    ):
        """Get all dependencies within a subtree, categorized by internal, incoming, and outgoing."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_subtree_dependencies.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            result = DependencyService.get_subtree_dependencies(
                model,
                sgraph_get_subtree_dependencies.root_path,
                sgraph_get_subtree_dependencies.include_external,
                sgraph_get_subtree_dependencies.max_depth,
            )
            return result
        except Exception as e:
            return {"error": f"Subtree dependency analysis failed: {str(e)}"}

    @mcp.tool()
    async def sgraph_get_dependency_chain(
        sgraph_get_dependency_chain: SGraphGetDependencyChain,
    ):
        """Get transitive dependency chain from an element. Direction can be 'outgoing', 'incoming', or 'both'."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_dependency_chain.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        valid_directions = ["outgoing", "incoming", "both"]
        if sgraph_get_dependency_chain.direction not in valid_directions:
            return {"error": f"Invalid direction. Must be one of: {valid_directions}"}
        
        try:
            result = DependencyService.get_dependency_chain(
                model,
                sgraph_get_dependency_chain.element_path,
                sgraph_get_dependency_chain.direction,
                sgraph_get_dependency_chain.max_depth,
            )
            return result
        except Exception as e:
            return {"error": f"Dependency chain analysis failed: {str(e)}"}

    @mcp.tool()
    async def sgraph_get_multiple_elements(
        sgraph_get_multiple_elements: SGraphGetMultipleElements,
    ):
        """Get information for multiple elements efficiently in a single request."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_multiple_elements.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            result = DependencyService.get_multiple_elements(
                model,
                sgraph_get_multiple_elements.element_paths,
                sgraph_get_multiple_elements.additional_fields,
            )
            return result
        except Exception as e:
            return {"error": f"Multiple elements retrieval failed: {str(e)}"}