#!/usr/bin/env python3
"""
Performance test for sgraph_get_model_overview
"""

import asyncio
import time
import sys
import os

# Add src to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.model_manager import ModelManager
from src.services.overview_service import OverviewService

async def test_overview_performance():
    """Test the performance of the model overview functionality"""
    
    print("🔍 Testing sgraph_get_model_overview performance...")
    
    # Initialize helper
    model_manager = ModelManager()
    
    # Test with the combined model
    model_path = "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip"
    
    try:
        print(f"📁 Loading model from: {model_path}")
    model_id = await model_manager.load_model(model_path)
    model = model_manager.get_model(model_id)
        
        if model is None:
            print("❌ Failed to retrieve model")
            return False
        
        print(f"✅ Model loaded successfully")
        
        # Test different depths with performance measurement
        test_cases = [
            {"depth": 1, "expected_max_ms": 50},
            {"depth": 2, "expected_max_ms": 75}, 
            {"depth": 3, "expected_max_ms": 100},
            {"depth": 4, "expected_max_ms": 150},
            {"depth": 5, "expected_max_ms": 200},
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            depth = test_case["depth"]
            expected_max_ms = test_case["expected_max_ms"]
            
            print(f"\n📊 Testing depth {depth} (target: <{expected_max_ms}ms)...")
            
            # Warm up
            sgh.get_model_overview(model, max_depth=depth, include_counts=True)
            
            # Measure performance
            start_time = time.perf_counter()
            result = OverviewService.get_model_overview(model, max_depth=depth, include_counts=True)
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            
            # Check results
            total_elements = result['summary']['total_elements']
            max_actual_depth = max(result['summary']['depth_counts'].keys()) if result['summary']['depth_counts'] else 0
            
            print(f"  ⏱️  Duration: {duration_ms:.1f}ms")
            print(f"  📈 Total elements: {total_elements}")
            print(f"  📏 Max actual depth: {max_actual_depth}")
            
            if duration_ms <= expected_max_ms:
                print(f"  ✅ PASSED (within {expected_max_ms}ms target)")
            else:
                print(f"  ❌ FAILED (exceeded {expected_max_ms}ms target)")
                all_passed = False
            
            # Validate structure
            if depth != max_actual_depth:
                print(f"  📊 Note: Requested depth {depth}, actual max depth {max_actual_depth}")
        
        # Test with include_counts=False for performance comparison
        print(f"\n🚀 Testing performance without counts...")
        start_time = time.perf_counter()
        result_no_counts = sgh.get_model_overview(model, max_depth=3, include_counts=False)
        end_time = time.perf_counter()
        duration_no_counts = (end_time - start_time) * 1000
        
        start_time = time.perf_counter()
        result_with_counts = sgh.get_model_overview(model, max_depth=3, include_counts=True)
        end_time = time.perf_counter()
        duration_with_counts = (end_time - start_time) * 1000
        
        print(f"  Without counts: {duration_no_counts:.1f}ms")
        print(f"  With counts: {duration_with_counts:.1f}ms")
        print(f"  Overhead: {duration_with_counts - duration_no_counts:.1f}ms ({((duration_with_counts / duration_no_counts - 1) * 100):.1f}%)")
        
        print(f"\n{'='*50}")
        if all_passed:
            print("🎉 ALL PERFORMANCE TESTS PASSED!")
            return True
        else:
            print("❌ Some performance tests failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during performance test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_overview_performance())
    sys.exit(0 if success else 1)
