"""
Navigation-related MCP tools.

Tools for getting specific elements and traversing the model structure.
"""

from pydantic import BaseModel

from src.core.element_converter import ElementConverter
from .model_tools import get_model_manager


class SGraphGetRootElement(BaseModel):
    model_id: str


class SGraphGetElement(BaseModel):
    model_id: str
    element_path: str


class SGraphGetElementIncomingAssociations(BaseModel):
    model_id: str
    element_path: str


class SGraphGetElementOutgoingAssociations(BaseModel):
    model_id: str
    element_path: str


def register_tools(mcp):
    """Register navigation tools with the MCP server."""
    
    @mcp.tool()
    async def sgraph_get_root_element(sgraph_get_root_element: SGraphGetRootElement):
        """Get the root element from a model."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_root_element.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        root_element = model.rootNode
        if root_element is None:
            return {"error": "No root element found"}
        
        return ElementConverter.element_to_dict(root_element)

    @mcp.tool()
    async def sgraph_get_element(sgraph_get_element: SGraphGetElement):
        """Get an element from a model by the path."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_element.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        element = model.findElementFromPath(sgraph_get_element.element_path)
        if element is None:
            return {"error": "Element not found"}
        
        return ElementConverter.element_to_dict(element)

    @mcp.tool()
    async def sgraph_get_element_incoming_associations(
        sgraph_get_element_incoming_associations: SGraphGetElementIncomingAssociations,
    ):
        """Get the incoming associations of single element. Does not include the associations of the children."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_element_incoming_associations.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        element = model.findElementFromPath(sgraph_get_element_incoming_associations.element_path)
        if element is None:
            return {"error": "Element not found"}
        
        associations = [
            ElementConverter.association_to_dict(assoc) for assoc in element.incoming
        ]
        
        return {
            "element_path": sgraph_get_element_incoming_associations.element_path,
            "incoming_associations": associations,
            "count": len(associations),
        }

    @mcp.tool()
    async def sgraph_get_element_outgoing_associations(
        sgraph_get_element_outgoing_associations: SGraphGetElementOutgoingAssociations,
    ):
        """Get the outgoing associations of single element. Does not include the associations of the children."""
        model_manager = get_model_manager()
        model = model_manager.get_model(sgraph_get_element_outgoing_associations.model_id)
        if model is None:
            return {"error": "Model not loaded"}
        
        element = model.findElementFromPath(sgraph_get_element_outgoing_associations.element_path)
        if element is None:
            return {"error": "Element not found"}
        
        associations = [
            ElementConverter.association_to_dict(assoc) for assoc in element.outgoing
        ]
        
        return {
            "element_path": sgraph_get_element_outgoing_associations.element_path,
            "outgoing_associations": associations,
            "count": len(associations),
        }