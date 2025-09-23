"""
Overview service for sgraph models.

Handles model structure overview and hierarchical analysis.
"""

import logging
from typing import Dict, Any

from sgraph import SGraph, SElement

logger = logging.getLogger(__name__)


class OverviewService:
    """Provides model overview functionality."""
    
    @staticmethod
    def get_model_overview(
        model: SGraph,
        max_depth: int = 3,
        include_counts: bool = True,
    ) -> Dict[str, Any]:
        """Get hierarchical overview of the model structure up to specified depth."""
        logger.debug(f"Generating model overview: depth={max_depth}, counts={include_counts}")
        
        result = {
            "root_path": "",
            "max_depth": max_depth,
            "tree_structure": {},
            "summary": {
                "total_elements": 0,
                "depth_counts": {},
                "type_distribution": {},
            }
        }
        
        # Start from root element
        root_element = model.rootNode
        total_elements = 0
        depth_counts = {}
        type_distribution = {}
        
        def build_tree_structure(element: SElement, current_depth: int) -> Dict[str, Any]:
            nonlocal total_elements
            total_elements += 1
            
            # Track depth statistics
            if current_depth not in depth_counts:
                depth_counts[current_depth] = 0
            depth_counts[current_depth] += 1
            
            # Track type distribution
            element_type = element.getType() or "unknown"
            if element_type not in type_distribution:
                type_distribution[element_type] = 0
            type_distribution[element_type] += 1
            
            # Build structure for this element
            structure = {
                "name": element.name,
                "path": element.getPath(),
                "type": element_type,
                "depth": current_depth,
            }
            
            if include_counts:
                structure["child_count"] = len(element.children)
                structure["incoming_count"] = len(element.incoming)
                structure["outgoing_count"] = len(element.outgoing)
            
            # Add children if we haven't reached max depth
            if current_depth < max_depth:
                structure["children"] = {}
                for child in element.children:
                    child_name = child.name or f"<unnamed_{child.getType()}>"
                    structure["children"][child_name] = build_tree_structure(child, current_depth + 1)
            elif len(element.children) > 0:
                # Indicate there are more children beyond max depth
                structure["has_more_children"] = len(element.children)
            
            return structure
        
        # Build the complete tree structure
        root_structure = build_tree_structure(root_element, 0)
        result["tree_structure"] = root_structure
        
        # Add summary statistics
        result["summary"]["total_elements"] = total_elements
        result["summary"]["depth_counts"] = depth_counts
        result["summary"]["type_distribution"] = type_distribution
        
        logger.debug(f"Model overview complete: {total_elements} elements across {len(depth_counts)} depth levels")
        
        return result
