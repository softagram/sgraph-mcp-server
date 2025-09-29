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


class SGraphAnalyzeExternalUsage(BaseModel):
    model_id: str
    scope_path: Optional[str] = None


class SGraphGetHighLevelDependencies(BaseModel):
    model_id: str
    scope_path: Optional[str] = None
    aggregation_level: int = 2  # Directory depth for aggregation (2 = /Project/module level)
    min_dependency_count: int = 1  # Minimum dependencies to include in results
    include_external: bool = True
    include_metrics: bool = True


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

    @mcp.tool()
    async def sgraph_analyze_external_usage(
        sgraph_analyze_external_usage: SGraphAnalyzeExternalUsage,
    ):
        """Analyze usage of External dependencies. Optionally restrict by scope_path (e.g., repository path)."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_analyze_external_usage.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            result = DependencyService.analyze_external_usage(
                model,
                sgraph_analyze_external_usage.scope_path,
            )
            return result
        except Exception as e:
            return {"error": f"External usage analysis failed: {str(e)}"}

    @mcp.tool()
    async def sgraph_get_high_level_dependencies(
        sgraph_get_high_level_dependencies: SGraphGetHighLevelDependencies,
    ):
        """Get high-level module dependencies aggregated at directory level. 
        
        This provides an architectural overview showing dependencies between modules/directories 
        rather than individual functions/classes. Useful for understanding overall system structure,
        identifying tightly coupled modules, and architectural analysis.
        """
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_high_level_dependencies.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            result = DependencyService.get_high_level_dependencies(
                model,
                sgraph_get_high_level_dependencies.scope_path,
                sgraph_get_high_level_dependencies.aggregation_level,
                sgraph_get_high_level_dependencies.min_dependency_count,
                sgraph_get_high_level_dependencies.include_external,
                sgraph_get_high_level_dependencies.include_metrics,
            )
            return result
        except Exception as e:
            return {"error": f"High-level dependency analysis failed: {str(e)}"}