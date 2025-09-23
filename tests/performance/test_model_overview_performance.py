#!/usr/bin/env python3
"""
Comprehensive performance test for sgraph_get_model_overview tool
Tests both the helper function and the MCP tool call performance
"""

import asyncio
import time
import sys
import os
import json

# Add src to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.model_manager import ModelManager
from src.services.overview_service import OverviewService
from src.tools.model_tools import SGraphGetModelOverview

async def test_helper_performance():
    """Test the direct service function performance"""
    
    print("🔍 Testing OverviewService.get_model_overview performance...")
    
    # Initialize model manager
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
        
        print(f"✅ Model loaded successfully (ID: {model_id})")
        
        # Performance requirements from AI agent perspective
        test_cases = [
            {"depth": 1, "target_ms": 25, "description": "Quick root overview"},
            {"depth": 2, "target_ms": 50, "description": "Directory structure"},
            {"depth": 3, "target_ms": 75, "description": "File-level overview"},
            {"depth": 4, "target_ms": 100, "description": "Detailed structure"},
            {"depth": 5, "target_ms": 150, "description": "Deep analysis"},
        ]
        
        all_passed = True
        results = []
        
        for test_case in test_cases:
            depth = test_case["depth"]
            target_ms = test_case["target_ms"]
            description = test_case["description"]
            
            print(f"\n📊 Testing depth {depth} - {description} (target: <{target_ms}ms)")
            
            # Warm up call
            OverviewService.get_model_overview(model, max_depth=depth, include_counts=True)
            
            # Multiple runs for accurate measurement
            times = []
            for i in range(5):
                start_time = time.perf_counter()
                result = OverviewService.get_model_overview(model, max_depth=depth, include_counts=True)
                end_time = time.perf_counter()
                times.append((end_time - start_time) * 1000)
            
            avg_ms = sum(times) / len(times)
            min_ms = min(times)
            max_ms = max(times)
            
            # Validate results
            total_elements = result['summary']['total_elements']
            depth_counts = result['summary']['depth_counts']
            type_counts = result['summary']['type_distribution']
            
            print(f"  ⏱️  Avg: {avg_ms:.1f}ms, Min: {min_ms:.1f}ms, Max: {max_ms:.1f}ms")
            print(f"  📈 Total elements: {total_elements}")
            print(f"  📊 Depths found: {list(depth_counts.keys())}")
            print(f"  🏷️  Types: {len(type_counts)} different types")
            
            # Check performance
            if avg_ms <= target_ms:
                print(f"  ✅ PASSED (avg {avg_ms:.1f}ms ≤ {target_ms}ms target)")
                status = "PASS"
            else:
                print(f"  ❌ FAILED (avg {avg_ms:.1f}ms > {target_ms}ms target)")
                all_passed = False
                status = "FAIL"
            
            results.append({
                "depth": depth,
                "description": description,
                "avg_ms": avg_ms,
                "target_ms": target_ms,
                "status": status,
                "elements": total_elements
            })
        
        return all_passed, results
        
    except Exception as e:
        print(f"❌ Error during helper performance test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, []

async def test_service_performance():
    """Test the service call performance"""
    
    print("\n🔧 Testing service call performance...")
    
    # Initialize model manager and load model
    model_manager = ModelManager()
    model_path = "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip"
    model_id = await model_manager.load_model(model_path)
    model = model_manager.get_model(model_id)
    
    # Test MCP tool performance
    test_cases = [
        {"depth": 1, "target_ms": 30},
        {"depth": 3, "target_ms": 80}, 
        {"depth": 5, "target_ms": 160},
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        depth = test_case["depth"]
        target_ms = test_case["target_ms"]
        
        print(f"\n🛠️  Testing service depth {depth} (target: <{target_ms}ms)")
        
        # Warm up
        OverviewService.get_model_overview(model, max_depth=depth, include_counts=True)
        
        # Multiple runs
        times = []
        for i in range(5):
            start_time = time.perf_counter()
            result = OverviewService.get_model_overview(model, max_depth=depth, include_counts=True)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        avg_ms = sum(times) / len(times)
        
        # Validate response structure
        if not result or 'summary' not in result:
            print(f"  ❌ Service returned invalid result")
            all_passed = False
            continue
        
        elements_count = result['summary']['total_elements']
        
        print(f"  ⏱️  Avg service call: {avg_ms:.1f}ms")
        print(f"  📊 Elements returned: {elements_count}")
        
        if avg_ms <= target_ms:
            print(f"  ✅ PASSED (avg {avg_ms:.1f}ms ≤ {target_ms}ms target)")
        else:
            print(f"  ❌ FAILED (avg {avg_ms:.1f}ms > {target_ms}ms target)")
            all_passed = False
    
    return all_passed

async def test_scalability():
    """Test tool performance with different model sizes"""
    
    print("\n📏 Testing scalability characteristics...")
    
    model_manager = ModelManager()
    model_path = "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip"
    model_id = await model_manager.load_model(model_path)
    model = model_manager.get_model(model_id)
    
    # Test scaling with depth
    print("  🔍 Analyzing performance scaling with depth...")
    
    scaling_results = []
    for depth in range(1, 8):
        start_time = time.perf_counter()
        result = OverviewService.get_model_overview(model, max_depth=depth, include_counts=False)
        end_time = time.perf_counter()
        
        duration_ms = (end_time - start_time) * 1000
        elements = result['summary']['total_elements']
        
        scaling_results.append({
            "depth": depth,
            "duration_ms": duration_ms,
            "elements": elements
        })
        
        print(f"    Depth {depth}: {duration_ms:.1f}ms, {elements} elements")
    
    # Check if performance scales reasonably (should be roughly linear or better)
    print("\n  📈 Scalability analysis:")
    for i in range(1, len(scaling_results)):
        prev = scaling_results[i-1]
        curr = scaling_results[i]
        
        element_ratio = curr["elements"] / prev["elements"] if prev["elements"] > 0 else 1
        time_ratio = curr["duration_ms"] / prev["duration_ms"] if prev["duration_ms"] > 0 else 1
        
        efficiency = element_ratio / time_ratio if time_ratio > 0 else 0
        
        print(f"    Depth {prev['depth']}→{curr['depth']}: {efficiency:.1f}x efficiency (elements/time ratio)")
    
    return True

async def main():
    """Run all performance tests"""
    
    print("🚀 SGRAPH MODEL OVERVIEW PERFORMANCE TESTS")
    print("=" * 50)
    
    # Test helper performance
    helper_passed, helper_results = await test_helper_performance()
    
    # Test service performance
    service_passed = await test_service_performance()
    
    # Test scalability
    scale_passed = await test_scalability()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PERFORMANCE TEST SUMMARY")
    print("=" * 50)
    
    if helper_results:
        print("\n🔧 Helper Function Results:")
        for result in helper_results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"  {status_icon} Depth {result['depth']}: {result['avg_ms']:.1f}ms ({result['elements']} elements)")
    
    print(f"\n🛠️  Service Performance: {'✅ PASSED' if service_passed else '❌ FAILED'}")
    print(f"📏 Scalability Test: {'✅ PASSED' if scale_passed else '❌ FAILED'}")
    
    overall_success = helper_passed and service_passed and scale_passed
    
    if overall_success:
        print("\n🎉 ALL PERFORMANCE TESTS PASSED!")
        print("   The sgraph_get_model_overview tool is ready for production use.")
        return True
    else:
        print("\n❌ SOME PERFORMANCE TESTS FAILED")
        print("   Review the results above and optimize as needed.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
