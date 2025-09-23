"""
Element conversion utilities for sgraph elements.

Handles conversion of SElement objects to dictionaries and other formats.
"""

from typing import Any, Dict, List
from sgraph import SElement


class ElementConverter:
    """Converts sgraph elements to various formats."""
    
    @staticmethod
    def element_to_dict(
        element: SElement,
        additional_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Convert an SElement to a dictionary representation."""
        if additional_fields is None:
            additional_fields = []
            
        result = {
            "name": element.name,
            "path": element.getPath(),
            "type": element.getType(),
            "child_paths": [child.getPath() for child in element.children],
        }
        
        # Add any additional fields requested
        for field in additional_fields:
            if hasattr(element, field):
                result[field] = getattr(element, field)
        
        return result
    
    @staticmethod
    def elements_to_list(
        elements: List[SElement],
        additional_fields: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """Convert a list of SElements to a list of dictionaries."""
        return [
            ElementConverter.element_to_dict(element, additional_fields)
            for element in elements
        ]
    
    @staticmethod
    def association_to_dict(association) -> Dict[str, Any]:
        """Convert an association to a dictionary representation."""
        return {
            "from": association.fromElement.getPath(),
            "to": association.toElement.getPath(),
            "type": getattr(association, 'type', 'unknown'),
        }
