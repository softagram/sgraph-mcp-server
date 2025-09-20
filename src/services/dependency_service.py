"""
Dependency analysis service for sgraph elements.

Handles dependency chain analysis and subtree dependency mapping.
"""

import logging
from typing import Dict, Any, Optional, Set, List

from sgraph import SGraph, SElement
from src.core.element_converter import ElementConverter

logger = logging.getLogger(__name__)


class DependencyService:
    """Provides dependency analysis functionality."""
    
    @staticmethod
    def get_subtree_dependencies(
        model: SGraph,
        root_path: str,
        include_external: bool = True,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all dependencies within a subtree, including both incoming and outgoing."""
        logger.debug(f"Analyzing subtree dependencies: root='{root_path}', external={include_external}, depth={max_depth}")
        
        result = {
            "subtree_elements": [],
            "internal_dependencies": [],
            "incoming_dependencies": [],
            "outgoing_dependencies": [],
        }
        
        root_element = model.findElementFromPath(root_path)
        if root_element is None:
            logger.warning(f"Root path not found: {root_path}")
            return result
        
        subtree_elements = set()
        subtree_paths = set()
        
        # Build subtree using iterative traversal
        stack = [(root_element, 0)]
        while stack:
            element, depth = stack.pop()
            
            if max_depth is not None and depth > max_depth:
                continue
                
            subtree_elements.add(element)
            subtree_paths.add(element.getPath())
            
            for child in element.children:
                stack.append((child, depth + 1))
        
        result["subtree_elements"] = [
            ElementConverter.element_to_dict(element) for element in subtree_elements
        ]
        
        # Analyze dependencies for each element in subtree
        for element in subtree_elements:
            element_path = element.getPath()
            
            # Analyze outgoing dependencies
            for association in element.outgoing:
                target_path = association.toElement.getPath()
                
                if not include_external and "/External/" in target_path:
                    continue
                
                dep_info = ElementConverter.association_to_dict(association)
                
                if target_path in subtree_paths:
                    result["internal_dependencies"].append(dep_info)
                else:
                    result["outgoing_dependencies"].append(dep_info)
            
            # Analyze incoming dependencies
            for association in element.incoming:
                source_path = association.fromElement.getPath()
                
                if not include_external and "/External/" in source_path:
                    continue
                
                if source_path not in subtree_paths:
                    dep_info = ElementConverter.association_to_dict(association)
                    result["incoming_dependencies"].append(dep_info)
        
        logger.debug(f"Subtree analysis complete: {len(subtree_elements)} elements, "
                    f"{len(result['internal_dependencies'])} internal deps, "
                    f"{len(result['incoming_dependencies'])} incoming deps, "
                    f"{len(result['outgoing_dependencies'])} outgoing deps")
        
        return result
    
    @staticmethod
    def get_dependency_chain(
        model: SGraph,
        element_path: str,
        direction: str = "outgoing",
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get transitive dependency chain from an element."""
        logger.debug(f"Analyzing dependency chain: element='{element_path}', direction='{direction}', depth={max_depth}")
        
        result = {
            "root_element": element_path,
            "direction": direction,
            "max_depth": max_depth,
            "chain": [],
            "all_dependencies": [],
        }
        
        root_element = model.findElementFromPath(element_path)
        if root_element is None:
            logger.warning(f"Element path not found: {element_path}")
            return result
        
        visited = set()
        chain_elements = []
        
        def traverse_dependencies(element: SElement, depth: int, path: List[str]):
            if max_depth is not None and depth > max_depth:
                return
            
            element_path = element.getPath()
            if element_path in visited:
                return
            
            visited.add(element_path)
            current_path = path + [element_path]
            
            # Get associations based on direction
            associations = []
            if direction in ["outgoing", "both"]:
                associations.extend([
                    (assoc.toElement, "outgoing", getattr(assoc, 'type', 'unknown'))
                    for assoc in element.outgoing
                ])
            if direction in ["incoming", "both"]:
                associations.extend([
                    (assoc.fromElement, "incoming", getattr(assoc, 'type', 'unknown'))
                    for assoc in element.incoming
                ])
            
            # Process each association
            for target_element, dep_direction, dep_type in associations:
                target_path = target_element.getPath()
                
                result["all_dependencies"].append({
                    "from": element_path,
                    "to": target_path,
                    "direction": dep_direction,
                    "type": dep_type,
                    "depth": depth,
                })
                
                # Recursively traverse
                traverse_dependencies(target_element, depth + 1, current_path)
            
            # Record chain path if not at root
            if len(current_path) > 1:
                chain_elements.append({
                    "path": current_path,
                    "depth": depth,
                })
        
        traverse_dependencies(root_element, 0, [])
        
        result["chain"] = chain_elements
        
        logger.debug(f"Dependency chain analysis complete: {len(result['all_dependencies'])} dependencies, "
                    f"{len(chain_elements)} chain paths")
        
        return result
    
    @staticmethod
    def get_multiple_elements(
        model: SGraph,
        element_paths: List[str],
        additional_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Get information for multiple elements efficiently."""
        if additional_fields is None:
            additional_fields = []
            
        logger.debug(f"Getting multiple elements: {len(element_paths)} paths")
        
        result = {
            "requested_count": len(element_paths),
            "found_count": 0,
            "elements": [],
            "not_found": [],
        }
        
        for path in element_paths:
            element = model.findElementFromPath(path)
            if element is None:
                result["not_found"].append(path)
            else:
                element_dict = ElementConverter.element_to_dict(element, additional_fields)
                result["elements"].append(element_dict)
                result["found_count"] += 1
        
        logger.debug(f"Multiple elements retrieved: {result['found_count']}/{result['requested_count']} found")
        
        return result
