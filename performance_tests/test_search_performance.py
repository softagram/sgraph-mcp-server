#!/usr/bin/env python3
"""
Performance test for sgraph_search_elements_by_name function.

This test loads the langchain.xml.zip model and measures the performance
of searching for the ConstitutionalPrinciple class element.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sgraph_helper import SGraphHelper


async def test_search_performance():
    """Test the performance of sgraph_search_elements_by_name."""
    print("=== SGraph Search Performance Test ===")
    
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
    
    # Test case: Search for ConstitutionalPrinciple
    search_pattern = "ConstitutionalPrinciple"
    expected_path = "/langchain-ai/langchain/libs/langchain/langchain/chains/constitutional_ai/models.py/ConstitutionalPrinciple"
    expected_type = "class"
    
    print(f"🔍 Searching for pattern: '{search_pattern}'")
    print(f"🎯 Expected path: {expected_path}")
    print(f"🏷️  Expected type: {expected_type}")
    
    # Perform the search and measure time
    search_start = time.perf_counter()
    try:
        results = helper.search_elements_by_name(
            model=model,
            pattern=search_pattern,
            element_type=expected_type
        )
        search_end = time.perf_counter()
        search_duration = (search_end - search_start) * 1000  # Convert to milliseconds
        
        print(f"⏱️  Search completed in: {search_duration:.2f} ms")
        print(f"📈 Found {len(results)} matching elements")
        
        # Verify results
        found_target = False
        for element in results:
            element_path = element.getPath()
            element_type = element.getType()
            element_name = element.name
            
            print(f"   - {element_name} ({element_type}): {element_path}")
            
            if element_path == expected_path and element_type == expected_type:
                found_target = True
                print(f"   ✅ Found target element!")
        
        # Performance assertion
        max_duration_ms = 100
        if search_duration > max_duration_ms:
            print(f"❌ PERFORMANCE FAILURE: Search took {search_duration:.2f} ms, expected < {max_duration_ms} ms")
            return False
        else:
            print(f"✅ PERFORMANCE PASS: Search completed within {max_duration_ms} ms limit")
        
        # Correctness assertion
        if not found_target:
            print(f"❌ CORRECTNESS FAILURE: Target element not found")
            return False
        else:
            print(f"✅ CORRECTNESS PASS: Target element found correctly")
        
        return True
        
    except Exception as e:
        search_end = time.perf_counter()
        search_duration = (search_end - search_start) * 1000
        print(f"❌ Search failed after {search_duration:.2f} ms: {e}")
        return False


async def main():
    """Main test runner."""
    print("Starting performance test...")
    
    success = await test_search_performance()
    
    if success:
        print("\n🎉 All tests PASSED!")
        sys.exit(0)
    else:
        print("\n💥 Tests FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
