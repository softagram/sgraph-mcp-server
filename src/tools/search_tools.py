"""
Search-related MCP tools.

Tools for searching elements by name, type, and attributes.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.services.search_service import SearchService
from src.core.element_converter import ElementConverter
from .model_tools import get_model_manager


class SGraphSearchElementsByName(BaseModel):
    model_id: str
    pattern: str
    element_type: Optional[str] = None
    scope_path: Optional[str] = None


class SGraphGetElementsByType(BaseModel):
    model_id: str
    element_type: str
    scope_path: Optional[str] = None


class SGraphSearchElementsByAttributes(BaseModel):
    model_id: str
    attribute_filters: Dict[str, Any]
    scope_path: Optional[str] = None


def register_tools(mcp):
    """Register search tools with the MCP server."""
    
    @mcp.tool()
    async def sgraph_search_elements_by_name(
        sgraph_search_elements_by_name: SGraphSearchElementsByName,
    ):
        """Search for elements by name pattern (regex or glob). Optionally filter by element type and scope path."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_search_elements_by_name.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            elements = SearchService.search_elements_by_name(
                model,
                sgraph_search_elements_by_name.pattern,
                sgraph_search_elements_by_name.element_type,
                sgraph_search_elements_by_name.scope_path,
            )
            element_dicts = ElementConverter.elements_to_list(elements)
            return {
                "elements": element_dicts,
                "count": len(element_dicts),
                "pattern": sgraph_search_elements_by_name.pattern,
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}

    @mcp.tool()
    async def sgraph_get_elements_by_type(
        sgraph_get_elements_by_type: SGraphGetElementsByType,
    ):
        """Get all elements of a specific type. Optionally limit search to a scope path."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_elements_by_type.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            elements = SearchService.get_elements_by_type(
                model,
                sgraph_get_elements_by_type.element_type,
                sgraph_get_elements_by_type.scope_path,
            )
            element_dicts = ElementConverter.elements_to_list(elements)
            return {
                "elements": element_dicts,
                "count": len(element_dicts),
                "element_type": sgraph_get_elements_by_type.element_type,
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}

    @mcp.tool()
    async def sgraph_search_elements_by_attributes(
        sgraph_search_elements_by_attributes: SGraphSearchElementsByAttributes,
    ):
        """Search for elements by attribute values. attribute_filters is a dict of attribute_name -> expected_value."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_search_elements_by_attributes.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        try:
            elements = SearchService.search_elements_by_attributes(
                model,
                sgraph_search_elements_by_attributes.attribute_filters,
                sgraph_search_elements_by_attributes.scope_path,
            )
            element_dicts = ElementConverter.elements_to_list(elements)
            return {
                "elements": element_dicts,
                "count": len(element_dicts),
                "attribute_filters": sgraph_search_elements_by_attributes.attribute_filters,
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}