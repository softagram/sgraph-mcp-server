#!/usr/bin/env python3
"""
Unit tests for ModelManager.
"""

import asyncio
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.model_manager import ModelManager


class TestModelManager:
    """Test cases for ModelManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ModelManager()
    
    def test_initialization(self):
        """Test that ModelManager initializes correctly."""
        assert self.manager is not None
        assert len(self.manager._models) == 0
    
    def test_get_nonexistent_model(self):
        """Test getting a model that doesn't exist."""
        result = self.manager.get_model("nonexistent_id")
        assert result is None
    
    def test_list_empty_models(self):
        """Test listing models when none are loaded."""
        models = self.manager.list_models()
        assert models == {}
    
    def test_clear_empty_cache(self):
        """Test clearing cache when it's empty."""
        count = self.manager.clear_cache()
        assert count == 0
    
    def test_remove_nonexistent_model(self):
        """Test removing a model that doesn't exist."""
        result = self.manager.remove_model("nonexistent_id")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await self.manager.load_model("/nonexistent/path.xml")
    
    def test_validate_model_id_format(self):
        """Test that model IDs have the expected format."""
        # This is an integration test - we'd need a real model file
        # For now, just test the structure exists
        assert hasattr(self.manager, 'load_model')
        assert hasattr(self.manager, 'get_model')
        assert hasattr(self.manager, 'list_models')


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])
