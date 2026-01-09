#!/usr/bin/env python3
"""
Test runner for the GoodWe Dynamic Price Optimiser
Moved out of `test/` so pytest won't auto-discover it as a test file.
Runs all test suites and provides detailed reporting (unittest-based runner).
"""

import unittest
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def run_all_tests():
    """Run all test suites"""
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), '..', 'test')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2,
        descriptions=True,
        failfast=False
    )
    
    print("=" * 80)
    print("GOODWE DYNAMIC PRICE OPTIMISER - TEST SUITE")
    print("=" * 80)
    print()
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
    
    return success


def run_specific_test(test_name):
    """Run a specific test suite"""
    test_modules = {
        'price_date': 'test_price_date_behavior',
        'scoring': 'test_scoring_algorithm',
        'integration': 'test_master_coordinator_integration'
    }
    
    if test_name not in test_modules:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(test_modules.keys())}")
        return False
    
    module_name = test_modules[test_name]
    print(f"Running {module_name}...")
    
    # Import and run specific test
    try:
        module = __import__(module_name)
        suite = unittest.TestLoader().loadTestsFromModule(module)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return len(result.failures) == 0 and len(result.errors) == 0
    except ImportError as e:
        print(f"Error importing {module_name}: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_all_tests()
    
    sys.exit(0 if success else 1)
