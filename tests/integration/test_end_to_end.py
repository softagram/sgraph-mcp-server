#!/usr/bin/env python3
"""
End-to-end integration tests for the modular sgraph-mcp-server.
"""

import asyncio
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.model_manager import ModelManager
from src.services.search_service import SearchService
from src.services.overview_service import OverviewService
from src.services.dependency_service import DependencyService


class TestEndToEnd:
    """End-to-end integration tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ModelManager()
        self.model_path = "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip"
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow from loading to analysis."""
        # Skip if model file doesn't exist
        if not os.path.exists(self.model_path):
            pytest.skip(f"Model file not found: {self.model_path}")
        
        # 1. Load model
        model_id = await self.manager.load_model(self.model_path)
        assert model_id is not None
        assert len(model_id) == 24  # nanoid length
        
        # 2. Get model from cache
        model = self.manager.get_model(model_id)
        assert model is not None
        
        # 3. Test overview service
        overview = OverviewService.get_model_overview(model, max_depth=2)
        assert "summary" in overview
        assert "total_elements" in overview["summary"]
        assert overview["summary"]["total_elements"] > 0
        
        # 4. Test search service
        files = SearchService.get_elements_by_type(model, "file")
        assert len(files) > 0
        
        # 5. Test search by name
        py_files = SearchService.search_elements_by_name(model, ".*\\.py", element_type="file")
        assert len(py_files) > 0
        
        # 6. Test dependency analysis (if elements exist)
        if files:
            deps = DependencyService.get_multiple_elements(
                model, 
                [files[0].getPath()],
                []
            )
            assert "elements" in deps
            assert deps["found_count"] == 1
        
        print(f"✅ End-to-end test passed with {overview['summary']['total_elements']} elements")
    
    def test_service_isolation(self):
        """Test that services can be used independently."""
        # Test that services don't depend on each other
        assert SearchService is not None
        assert OverviewService is not None
        assert DependencyService is not None
        
        # Each service should have its static methods
        assert hasattr(SearchService, 'search_elements_by_name')
        assert hasattr(OverviewService, 'get_model_overview')
        assert hasattr(DependencyService, 'get_subtree_dependencies')
    
    @pytest.mark.asyncio
    async def test_high_level_dependencies(self):
        """Test high-level dependency analysis functionality."""
        # Skip if model file doesn't exist
        if not os.path.exists(self.model_path):
            pytest.skip(f"Model file not found: {self.model_path}")
        
        # Load model
        model_id = await self.manager.load_model(self.model_path)
        assert model_id is not None
        
        model = self.manager.get_model(model_id)
        assert model is not None
        
        # Test high-level dependencies with default settings
        result = DependencyService.get_high_level_dependencies(model)
        assert "scope_path" in result
        assert "total_modules" in result
        assert "total_dependencies" in result
        assert "modules" in result
        assert "dependencies" in result
        
        # Verify results structure
        if result["total_modules"] > 0:
            assert len(result["modules"]) > 0
            # Check module structure
            module = result["modules"][0]
            assert "path" in module
            assert "outgoing_count" in module
            assert "incoming_count" in module
        
        if result["total_dependencies"] > 0:
            assert len(result["dependencies"]) > 0
            # Check dependency structure
            dep = result["dependencies"][0]
            assert "from" in dep
            assert "to" in dep
            assert "count" in dep
        
        # Test with metrics enabled (default)
        assert "metrics" in result
        assert "most_depended_upon" in result["metrics"]
        assert "most_dependent" in result["metrics"]
        assert "circular_dependencies" in result["metrics"]
        
        # Test with different aggregation levels
        result_level3 = DependencyService.get_high_level_dependencies(
            model, aggregation_level=3
        )
        assert "aggregation_level" in result_level3
        assert result_level3["aggregation_level"] == 3
        
        # Test without external dependencies
        result_no_external = DependencyService.get_high_level_dependencies(
            model, include_external=False
        )
        assert result_no_external is not None
        
        print(f"✅ High-level dependencies test passed: {result['total_modules']} modules, "
              f"{result['total_dependencies']} dependencies found")


if __name__ == "__main__":
    pytest.main([__file__])
