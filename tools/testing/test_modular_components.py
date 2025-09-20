#!/usr/bin/env python3
"""
Modular component testing utility.

Tests that modular components work correctly in isolation and integration.
Useful for validating architecture changes and refactoring.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_component_imports():
    """Test that all modular components can be imported correctly."""
    
    print("🧪 Testing component imports...")
    results = {}
    
    try:
        # Test core components
        from src.core.model_manager import ModelManager
        from src.core.element_converter import ElementConverter
        results["core"] = "✅ PASS"
        
        # Test services
        from src.services.search_service import SearchService
        from src.services.dependency_service import DependencyService
        from src.services.overview_service import OverviewService
        results["services"] = "✅ PASS"
        
        # Test utils
        from src.utils.validators import validate_model_id, validate_path
        from src.utils.logging import setup_logging
        results["utils"] = "✅ PASS"
        
        return True, results
        
    except Exception as e:
        results["error"] = f"❌ FAIL: {str(e)}"
        return False, results


async def test_component_functionality(model_path: str = None):
    """Test basic functionality of components with a real model."""
    
    print("🔧 Testing component functionality...")
    results = {}
    
    if not model_path:
        model_path = "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip"
    
    if not os.path.exists(model_path):
        results["model_loading"] = "⚠️  SKIP: Model file not found"
        return True, results
    
    try:
        from src.core.model_manager import ModelManager
        from src.services.search_service import SearchService
        from src.services.overview_service import OverviewService
        
        # Test ModelManager
        manager = ModelManager()
        model_id = await manager.load_model(model_path)
        model = manager.get_model(model_id)
        
        if model:
            results["model_loading"] = "✅ PASS"
            
            # Test OverviewService
            overview = OverviewService.get_model_overview(model, max_depth=2)
            if overview and "summary" in overview:
                results["overview_service"] = "✅ PASS"
            else:
                results["overview_service"] = "❌ FAIL: Invalid overview"
            
            # Test SearchService
            files = SearchService.get_elements_by_type(model, "file")
            if len(files) > 0:
                results["search_service"] = "✅ PASS"
            else:
                results["search_service"] = "❌ FAIL: No files found"
        else:
            results["model_loading"] = "❌ FAIL: Model not retrieved"
            
        return True, results
        
    except Exception as e:
        results["error"] = f"❌ FAIL: {str(e)}"
        return False, results


def test_service_isolation():
    """Test that services can be used independently."""
    
    print("🔬 Testing service isolation...")
    results = {}
    
    try:
        from src.services.search_service import SearchService
        from src.services.dependency_service import DependencyService
        from src.services.overview_service import OverviewService
        
        # Check that services have expected static methods
        search_methods = ["search_elements_by_name", "get_elements_by_type", "search_elements_by_attributes"]
        dependency_methods = ["get_subtree_dependencies", "get_dependency_chain", "get_multiple_elements"]
        overview_methods = ["get_model_overview"]
        
        for method in search_methods:
            if hasattr(SearchService, method) and callable(getattr(SearchService, method)):
                results[f"search_{method}"] = "✅ PASS"
            else:
                results[f"search_{method}"] = "❌ FAIL: Method missing"
        
        for method in dependency_methods:
            if hasattr(DependencyService, method) and callable(getattr(DependencyService, method)):
                results[f"dependency_{method}"] = "✅ PASS"
            else:
                results[f"dependency_{method}"] = "❌ FAIL: Method missing"
                
        for method in overview_methods:
            if hasattr(OverviewService, method) and callable(getattr(OverviewService, method)):
                results[f"overview_{method}"] = "✅ PASS"
            else:
                results[f"overview_{method}"] = "❌ FAIL: Method missing"
        
        return True, results
        
    except Exception as e:
        results["error"] = f"❌ FAIL: {str(e)}"
        return False, results


async def run_all_tests(model_path: str = None):
    """Run all modular component tests."""
    
    print("🚀 MODULAR COMPONENT TEST SUITE")
    print("=" * 50)
    
    overall_success = True
    all_results = {}
    
    # Test 1: Component imports
    success, results = await test_component_imports()
    all_results["imports"] = results
    overall_success = overall_success and success
    
    # Test 2: Service isolation
    success, results = test_service_isolation()
    all_results["isolation"] = results
    overall_success = overall_success and success
    
    # Test 3: Component functionality
    success, results = await test_component_functionality(model_path)
    all_results["functionality"] = results
    overall_success = overall_success and success
    
    # Print results
    print("\n📊 TEST RESULTS")
    print("-" * 30)
    
    for test_category, test_results in all_results.items():
        print(f"\n{test_category.upper()}:")
        for test_name, result in test_results.items():
            print(f"  {test_name}: {result}")
    
    print(f"\n🎯 OVERALL RESULT: {'✅ PASS' if overall_success else '❌ FAIL'}")
    return overall_success


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test modular components")
    parser.add_argument(
        "--model", 
        help="Path to sgraph model for functionality testing"
    )
    
    args = parser.parse_args()
    
    success = await run_all_tests(args.model)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
