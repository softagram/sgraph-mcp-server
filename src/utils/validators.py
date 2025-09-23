"""
Input validation utilities for sgraph-mcp-server.
"""

import os
import re
from typing import Optional


def validate_model_id(model_id: str) -> bool:
    """Validate that a model ID has the expected format."""
    if not model_id:
        return False
    
    # Model IDs should be 24-character nanoid strings
    if len(model_id) != 24:
        return False
    
    # Should contain only alphanumeric characters and underscores/hyphens
    return bool(re.match(r'^[a-zA-Z0-9_-]{24}$', model_id))


def validate_path(path: str, must_exist: bool = True) -> tuple[bool, Optional[str]]:
    """
    Validate a file path.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"
    
    if not isinstance(path, str):
        return False, "Path must be a string"
    
    if must_exist and not os.path.exists(path):
        return False, f"Path does not exist: {path}"
    
    # Check for potentially dangerous paths
    if ".." in path:
        return False, "Path traversal detected"
    
    return True, None


def validate_element_type(element_type: str) -> bool:
    """Validate that an element type is reasonable."""
    if not element_type:
        return False
    
    # Common element types in sgraph models
    valid_types = {
        "file", "dir", "function", "class", "method", "variable", 
        "repository", "module", "package", "unknown", "other"
    }
    
    return element_type.lower() in valid_types or len(element_type) < 50


def validate_pattern(pattern: str) -> tuple[bool, Optional[str]]:
    """
    Validate a regex pattern.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not pattern:
        return False, "Pattern cannot be empty"
    
    try:
        re.compile(pattern)
        return True, None
    except re.error as e:
        return False, f"Invalid regex pattern: {str(e)}"
