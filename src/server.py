from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from sgraph_helper import SGraphHelper

mcp = FastMCP("SGraph")
mcp.settings.port = 8008

sgh = SGraphHelper()


class SGraphLoadModel(BaseModel):
    path: str


@mcp.tool()
async def sgraph_load_model(sgraph_load_model: SGraphLoadModel):
    """Load a sgraph from a file and return the model id."""
    model_id = await sgh.load_sgraph(sgraph_load_model.path)
    return {"model_id": model_id}


class SGraphGetRootElement(BaseModel):
    model_id: str


@mcp.tool()
async def sgraph_get_root_element(sgraph_get_root_element: SGraphGetRootElement):
    """Get the root element from a model."""
    model = sgh.get_model(sgraph_get_root_element.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    element_dict = sgh.element_to_dict(model.rootNode)
    return {"element": element_dict}


class SGraphGetElement(BaseModel):
    model_id: str
    element_path: str


@mcp.tool()
async def sgraph_get_element(sgraph_get_element: SGraphGetElement):
    """Get an element from a model by the path."""
    model = sgh.get_model(sgraph_get_element.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    root_element = model.rootNode
    element = root_element.findElement(sgraph_get_element.element_path)
    if element is None:
        return {"error": "Element not found"}
    element_dict = sgh.element_to_dict(element)
    return {"element": element_dict}


class SGraphGetElementIncomingAssociations(BaseModel):
    model_id: str
    element_path: str


@mcp.tool()
async def sgraph_get_element_incoming_associations(
    sgraph_get_element_incoming_associations: SGraphGetElementIncomingAssociations,
):
    """Get the incoming associations of single element. Does not include the associations of the children."""  # noqa: E501
    model = sgh.get_model(sgraph_get_element_incoming_associations.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    element = model.findElementFromPath(sgraph_get_element_incoming_associations.element_path)
    if element is None:
        return {"error": "Element not found"}
    incoming_associations_dicts = [
        sgh.element_to_dict(association.fromElement) for association in element.incoming
    ]
    return {"incoming_associations": incoming_associations_dicts}


class SGraphGetElementOutgoingAssociations(BaseModel):
    model_id: str
    element_path: str


@mcp.tool()
async def sgraph_get_element_outgoing_associations(
    sgraph_get_element_outgoing_associations: SGraphGetElementOutgoingAssociations,
):
    """Get the outgoing associations of single element. Does not include the associations of the children."""  # noqa: E501
    model = sgh.get_model(sgraph_get_element_outgoing_associations.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    element = model.findElementFromPath(sgraph_get_element_outgoing_associations.element_path)
    if element is None:
        return {"error": "Element not found"}
    outgoing_associations_dicts = [
        sgh.element_to_dict(association.toElement) for association in element.outgoing
    ]
    return {"outgoing_associations": outgoing_associations_dicts}


class SGraphSearchElementsByName(BaseModel):
    model_id: str
    pattern: str
    element_type: Optional[str] = None
    scope_path: Optional[str] = None


@mcp.tool()
async def sgraph_search_elements_by_name(
    sgraph_search_elements_by_name: SGraphSearchElementsByName,
):
    """Search for elements by name pattern (regex or glob). Optionally filter by element type and scope path."""  # noqa: E501
    model = sgh.get_model(sgraph_search_elements_by_name.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    try:
        elements = sgh.search_elements_by_name(
            model,
            sgraph_search_elements_by_name.pattern,
            sgraph_search_elements_by_name.element_type,
            sgraph_search_elements_by_name.scope_path,
        )
        element_dicts = [sgh.element_to_dict(element) for element in elements]
        return {
            "elements": element_dicts,
            "count": len(element_dicts),
            "pattern": sgraph_search_elements_by_name.pattern,
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


class SGraphGetElementsByType(BaseModel):
    model_id: str
    element_type: str
    scope_path: Optional[str] = None


@mcp.tool()
async def sgraph_get_elements_by_type(
    sgraph_get_elements_by_type: SGraphGetElementsByType,
):
    """Get all elements of a specific type. Optionally limit search to a scope path."""
    model = sgh.get_model(sgraph_get_elements_by_type.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    try:
        elements = sgh.get_elements_by_type(
            model,
            sgraph_get_elements_by_type.element_type,
            sgraph_get_elements_by_type.scope_path,
        )
        element_dicts = [sgh.element_to_dict(element) for element in elements]
        return {
            "elements": element_dicts,
            "count": len(element_dicts),
            "element_type": sgraph_get_elements_by_type.element_type,
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


class SGraphSearchElementsByAttributes(BaseModel):
    model_id: str
    attribute_filters: Dict[str, Any]
    scope_path: Optional[str] = None


@mcp.tool()
async def sgraph_search_elements_by_attributes(
    sgraph_search_elements_by_attributes: SGraphSearchElementsByAttributes,
):
    """Search for elements by attribute values. attribute_filters is a dict of attribute_name -> expected_value."""  # noqa: E501
    model = sgh.get_model(sgraph_search_elements_by_attributes.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    try:
        elements = sgh.search_elements_by_attributes(
            model,
            sgraph_search_elements_by_attributes.attribute_filters,
            sgraph_search_elements_by_attributes.scope_path,
        )
        element_dicts = [sgh.element_to_dict(element) for element in elements]
        return {
            "elements": element_dicts,
            "count": len(element_dicts),
            "attribute_filters": sgraph_search_elements_by_attributes.attribute_filters,
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


class SGraphGetSubtreeDependencies(BaseModel):
    model_id: str
    root_path: str
    include_external: bool = True
    max_depth: Optional[int] = None


@mcp.tool()
async def sgraph_get_subtree_dependencies(
    sgraph_get_subtree_dependencies: SGraphGetSubtreeDependencies,
):
    """Get all dependencies within a subtree, categorized by internal, incoming, and outgoing."""
    model = sgh.get_model(sgraph_get_subtree_dependencies.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    try:
        result = sgh.get_subtree_dependencies(
            model,
            sgraph_get_subtree_dependencies.root_path,
            sgraph_get_subtree_dependencies.include_external,
            sgraph_get_subtree_dependencies.max_depth,
        )
        return result
    except Exception as e:
        return {"error": f"Subtree dependency analysis failed: {str(e)}"}


class SGraphGetDependencyChain(BaseModel):
    model_id: str
    element_path: str
    direction: str = "outgoing"  # "outgoing", "incoming", or "both"
    max_depth: Optional[int] = None


@mcp.tool()
async def sgraph_get_dependency_chain(
    sgraph_get_dependency_chain: SGraphGetDependencyChain,
):
    """Get transitive dependency chain from an element. Direction can be 'outgoing', 'incoming', or 'both'."""
    model = sgh.get_model(sgraph_get_dependency_chain.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    # Validate direction parameter
    valid_directions = ["outgoing", "incoming", "both"]
    if sgraph_get_dependency_chain.direction not in valid_directions:
        return {"error": f"Invalid direction. Must be one of: {valid_directions}"}
    
    try:
        result = sgh.get_dependency_chain(
            model,
            sgraph_get_dependency_chain.element_path,
            sgraph_get_dependency_chain.direction,
            sgraph_get_dependency_chain.max_depth,
        )
        return result
    except Exception as e:
        return {"error": f"Dependency chain analysis failed: {str(e)}"}


class SGraphGetMultipleElements(BaseModel):
    model_id: str
    element_paths: List[str]
    additional_fields: List[str] = []


@mcp.tool()
async def sgraph_get_multiple_elements(
    sgraph_get_multiple_elements: SGraphGetMultipleElements,
):
    """Get information for multiple elements efficiently in a single request."""
    model = sgh.get_model(sgraph_get_multiple_elements.model_id)
    if model is None:
        return {"error": "Model not loaded"}
    
    try:
        result = sgh.get_multiple_elements(
            model,
            sgraph_get_multiple_elements.element_paths,
            sgraph_get_multiple_elements.additional_fields,
        )
        return result
    except Exception as e:
        return {"error": f"Multiple elements retrieval failed: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport="sse")
