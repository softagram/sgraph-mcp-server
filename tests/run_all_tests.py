#!/usr/bin/env python3
"""
Test runner for all sgraph-mcp-server tests.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests(test_type: str = "all"):
    """Run tests of specified type."""
    
    test_commands = {
        "unit": ["python", "-m", "pytest", "tests/unit/", "-v"],
        "integration": ["python", "-m", "pytest", "tests/integration/", "-v"],
        "performance": ["python", "tests/performance/run_tests.py"],
        "all": ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]
    }
    
    if test_type not in test_commands:
        print(f"❌ Unknown test type: {test_type}")
        print(f"Available types: {list(test_commands.keys())}")
        return False
    
    print(f"🧪 Running {test_type} tests...")
    print("=" * 50)
    
    try:
        result = subprocess.run(
            test_commands[test_type],
            cwd=project_root,
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n✅ {test_type} tests PASSED!")
            return True
        else:
            print(f"\n❌ {test_type} tests FAILED!")
            return False
            
    except FileNotFoundError as e:
        print(f"❌ Test runner not found: {e}")
        print("Make sure pytest is installed: uv add pytest")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run sgraph-mcp-server tests")
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="all",
        choices=["unit", "integration", "performance", "all"],
        help="Type of tests to run"
    )
    
    args = parser.parse_args()
    
    success = run_tests(args.test_type)
    sys.exit(0 if success else 1)
