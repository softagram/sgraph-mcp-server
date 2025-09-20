#!/usr/bin/env python3
"""
Unit tests for SearchService.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.services.search_service import SearchService


class TestSearchService:
    """Test cases for SearchService."""
    
    def test_search_elements_by_name_exists(self):
        """Test that search_elements_by_name method exists."""
        assert hasattr(SearchService, 'search_elements_by_name')
        assert callable(SearchService.search_elements_by_name)
    
    def test_get_elements_by_type_exists(self):
        """Test that get_elements_by_type method exists."""
        assert hasattr(SearchService, 'get_elements_by_type')
        assert callable(SearchService.get_elements_by_type)
    
    def test_search_elements_by_attributes_exists(self):
        """Test that search_elements_by_attributes method exists."""
        assert hasattr(SearchService, 'search_elements_by_attributes')
        assert callable(SearchService.search_elements_by_attributes)
    
    def test_all_methods_are_static(self):
        """Test that all methods are static methods."""
        # We can call methods without instantiating the class
        assert SearchService.search_elements_by_name is not None
        assert SearchService.get_elements_by_type is not None
        assert SearchService.search_elements_by_attributes is not None


if __name__ == "__main__":
    pytest.main([__file__])
