"""
Search service for sgraph elements.

Handles various search operations on sgraph models.
"""

import re
import logging
from typing import List, Optional, Dict, Any

from sgraph import SGraph, SElement
from src.utils.validators import validate_pattern

logger = logging.getLogger(__name__)


class SearchService:
    """Provides search functionality for sgraph elements."""
    
    @staticmethod
    def search_elements_by_name(
        model: SGraph,
        pattern: str,
        element_type: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> List[SElement]:
        """Search for elements by name pattern within optional scope and type filters."""
        logger.debug(f"Searching elements by name: pattern='{pattern}', type='{element_type}', scope='{scope_path}'")
        
        results = []
        start_element = model.rootNode
        
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                logger.warning(f"Scope path not found: {scope_path}")
                return results
        
        # Validate and compile pattern
        is_valid, error = validate_pattern(pattern)
        if not is_valid:
            logger.warning(f"Invalid pattern: {error}")
            # Fallback to literal search
            pattern = re.escape(pattern)
        
        try:
            regex_pattern = re.compile(pattern)
        except re.error:
            # Fallback to glob-style pattern
            glob_pattern = pattern.replace("*", ".*").replace("?", ".")
            regex_pattern = re.compile(glob_pattern)
        
        # Iterative traversal for performance
        stack = [start_element]
        while stack:
            element = stack.pop()
            
            # Check if element matches pattern
            if regex_pattern.search(element.name):
                # Check type filter if specified
                if element_type is None or element.getType() == element_type:
                    results.append(element)
            
            # Add children to stack
            stack.extend(element.children)
        
        logger.debug(f"Found {len(results)} elements matching pattern")
        return results
    
    @staticmethod
    def get_elements_by_type(
        model: SGraph,
        element_type: str,
        scope_path: Optional[str] = None,
    ) -> List[SElement]:
        """Get all elements of a specific type within optional scope."""
        logger.debug(f"Getting elements by type: type='{element_type}', scope='{scope_path}'")
        
        results = []
        start_element = model.rootNode
        
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                logger.warning(f"Scope path not found: {scope_path}")
                return results
        
        # Iterative traversal for performance
        stack = [start_element]
        while stack:
            element = stack.pop()
            
            if element.getType() == element_type:
                results.append(element)
            
            stack.extend(element.children)
        
        logger.debug(f"Found {len(results)} elements of type '{element_type}'")
        return results
    
    @staticmethod
    def search_elements_by_attributes(
        model: SGraph,
        attribute_filters: Dict[str, Any],
        scope_path: Optional[str] = None,
    ) -> List[SElement]:
        """Search for elements by attribute values within optional scope."""
        logger.debug(f"Searching elements by attributes: filters={attribute_filters}, scope='{scope_path}'")
        
        results = []
        start_element = model.rootNode
        
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                logger.warning(f"Scope path not found: {scope_path}")
                return results
        
        # Iterative traversal for performance
        stack = [start_element]
        while stack:
            element = stack.pop()
            
            # Check if element matches all attribute filters
            matches_all = True
            for attr_name, expected_value in attribute_filters.items():
                if not hasattr(element, attr_name):
                    matches_all = False
                    break
                
                actual_value = getattr(element, attr_name)
                
                # Support regex matching for string attributes
                if isinstance(expected_value, str) and isinstance(actual_value, str):
                    try:
                        if not re.search(expected_value, actual_value):
                            matches_all = False
                            break
                    except re.error:
                        # Fallback to exact match
                        if actual_value != expected_value:
                            matches_all = False
                            break
                elif actual_value != expected_value:
                    matches_all = False
                    break
            
            if matches_all:
                results.append(element)
            
            stack.extend(element.children)
        
        logger.debug(f"Found {len(results)} elements matching attributes")
        return results
