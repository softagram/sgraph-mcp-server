#!/usr/bin/env python3
"""
Runner script for all performance tests.
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_search_performance import test_search_performance
from test_all_search_performance import test_all_search_functions_performance
from test_bulk_analysis_performance import test_bulk_analysis_performance
from test_model_overview_performance import main as test_model_overview_performance


async def main():
    """Run all performance tests."""
    print("🚀 Running SGraph MCP Server Performance Tests")
    print("=" * 50)
    
    tests = [
        ("Search Elements by Name", test_search_performance),
        ("All Search Functions Comprehensive", test_all_search_functions_performance),
        ("Bulk Analysis Functions", test_bulk_analysis_performance),
        ("Model Overview Performance", test_model_overview_performance),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 30)
        
        try:
            success = await test_func()
            if success:
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                failed += 1
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("💥 Some tests failed!")
        sys.exit(1)
    else:
        print("🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
