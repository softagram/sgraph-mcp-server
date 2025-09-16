#!/usr/bin/env python3
"""
Comprehensive performance test for all search functions after stack-based optimization.

This test measures the performance of:
- sgraph_search_elements_by_name
- sgraph_get_elements_by_type  
- sgraph_search_elements_by_attributes
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sgraph_helper import SGraphHelper


async def test_all_search_functions_performance():
    """Test the performance of all search functions with stack-based optimization."""
    print("=== Comprehensive Search Performance Test ===")
    
    # Initialize helper
    helper = SGraphHelper()
    
    # Path to the test model
    model_path = Path(__file__).parent.parent / "sgraph-example-models" / "langchain.xml.zip"
    
    if not model_path.exists():
        print(f"❌ Test model not found at: {model_path}")
        return False
    
    print(f"📁 Loading model from: {model_path}")
    
    # Load the model and measure loading time
    load_start = time.perf_counter()
    try:
        model_id = await helper.load_sgraph(str(model_path))
        load_end = time.perf_counter()
        load_duration = (load_end - load_start) * 1000  # Convert to milliseconds
        print(f"⏱️  Model loaded in: {load_duration:.2f} ms")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False
    
    # Get the model for direct access
    model = helper.get_model(model_id)
    if model is None:
        print("❌ Failed to retrieve loaded model")
        return False
    
    print(f"📊 Model loaded successfully with ID: {model_id}")
    print()
    
    all_tests_passed = True
    
    # Test 1: Search by name
    print("🔍 Test 1: Search Elements by Name")
    print("-" * 40)
    search_pattern = "ConstitutionalPrinciple"
    expected_path = "/langchain-ai/langchain/libs/langchain/langchain/chains/constitutional_ai/models.py/ConstitutionalPrinciple"
    expected_type = "class"
    
    search_start = time.perf_counter()
    try:
        results = helper.search_elements_by_name(
            model=model,
            pattern=search_pattern,
            element_type=expected_type
        )
        search_end = time.perf_counter()
        search_duration = (search_end - search_start) * 1000
        
        print(f"⏱️  Search by name: {search_duration:.2f} ms")
        print(f"📈 Found {len(results)} matching elements")
        
        # Verify correctness
        found_target = any(
            element.getPath() == expected_path and element.getType() == expected_type
            for element in results
        )
        
        if search_duration > 100:
            print(f"❌ PERFORMANCE FAILURE: Search took {search_duration:.2f} ms, expected < 100 ms")
            all_tests_passed = False
        elif not found_target:
            print(f"❌ CORRECTNESS FAILURE: Target element not found")
            all_tests_passed = False
        else:
            print(f"✅ Search by name: PASSED")
        
    except Exception as e:
        print(f"❌ Search by name failed: {e}")
        all_tests_passed = False
    
    print()
    
    # Test 2: Search by type
    print("🏷️  Test 2: Get Elements by Type")
    print("-" * 40)
    element_type = "class"
    
    search_start = time.perf_counter()
    try:
        results = helper.get_elements_by_type(
            model=model,
            element_type=element_type
        )
        search_end = time.perf_counter()
        search_duration = (search_end - search_start) * 1000
        
        print(f"⏱️  Search by type: {search_duration:.2f} ms")
        print(f"📈 Found {len(results)} '{element_type}' elements")
        
        # Verify correctness - should find many classes including our target
        found_target = any(
            element.getPath() == expected_path
            for element in results
        )
        
        if search_duration > 200:  # More lenient since this finds many results
            print(f"❌ PERFORMANCE FAILURE: Search took {search_duration:.2f} ms, expected < 200 ms")
            all_tests_passed = False
        elif not found_target:
            print(f"❌ CORRECTNESS FAILURE: Target class not found among results")
            all_tests_passed = False
        elif len(results) < 10:  # Should find many classes in langchain
            print(f"❌ CORRECTNESS FAILURE: Too few classes found, expected many more")
            all_tests_passed = False
        else:
            print(f"✅ Search by type: PASSED")
        
    except Exception as e:
        print(f"❌ Search by type failed: {e}")
        all_tests_passed = False
    
    print()
    
    # Test 3: Search by attributes (using 'name' attribute as a proxy)
    print("🔧 Test 3: Search Elements by Attributes")
    print("-" * 40)
    
    search_start = time.perf_counter()
    try:
        # Search for elements with 'name' attribute containing 'Constitutional'
        results = helper.search_elements_by_attributes(
            model=model,
            attribute_filters={"name": ".*Constitutional.*"}
        )
        search_end = time.perf_counter()
        search_duration = (search_end - search_start) * 1000
        
        print(f"⏱️  Search by attributes: {search_duration:.2f} ms")
        print(f"📈 Found {len(results)} matching elements")
        
        # Verify correctness - should find elements with 'Constitutional' in the name
        found_target = any(
            "Constitutional" in element.name
            for element in results
        )
        
        if search_duration > 200:  # More lenient since this does regex matching
            print(f"❌ PERFORMANCE FAILURE: Search took {search_duration:.2f} ms, expected < 200 ms")
            all_tests_passed = False
        elif not found_target:
            print(f"❌ CORRECTNESS FAILURE: No elements with 'Constitutional' in name found")
            all_tests_passed = False
        else:
            print(f"✅ Search by attributes: PASSED")
            
        # Print some example results
        for element in results[:3]:  # Show first 3 results
            print(f"   - {element.name} ({element.getType()}): {element.getPath()}")
        
    except Exception as e:
        print(f"❌ Search by attributes failed: {e}")
        all_tests_passed = False
    
    print()
    print("=" * 50)
    
    return all_tests_passed


async def main():
    """Main test runner."""
    print("Starting comprehensive performance test...")
    
    success = await test_all_search_functions_performance()
    
    if success:
        print("🎉 All search performance tests PASSED!")
        sys.exit(0)
    else:
        print("💥 Some tests FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
