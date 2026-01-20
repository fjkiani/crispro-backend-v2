"""
Run Universal Tests - Direct Python Execution

Runs all universal tests without pytest dependency.
"""

import sys
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "errors": []
}


def run_test_module(module_name, test_class_name=None):
    """Run a test module."""
    print(f"\n{'='*80}")
    print(f"Running: {module_name}")
    print(f"{'='*80}\n")
    
    try:
        # Import module
        module = __import__(module_name.replace("/", ".").replace(".py", ""), fromlist=[""])
        
        # Find test classes
        test_classes = [obj for name, obj in module.__dict__.items() 
                       if isinstance(obj, type) and name.startswith("Test")]
        
        if not test_classes:
            print(f"⚠️  No test classes found in {module_name}")
            return
        
        # Run tests in each class
        for test_class in test_classes:
            if test_class_name and test_class.__name__ != test_class_name:
                continue
                
            print(f"\n📋 Test Class: {test_class.__name__}")
            print("-" * 80)
            
            # Find test methods
            test_methods = [method for method in dir(test_class) 
                          if method.startswith("test_")]
            
            for method_name in test_methods:
                try:
                    print(f"  🧪 {method_name}...", end=" ")
                    test_instance = test_class()
                    test_method = getattr(test_instance, method_name)
                    test_method()
                    print("✅ PASSED")
                    results["passed"] += 1
                except AssertionError as e:
                    print(f"❌ FAILED: {str(e)}")
                    results["failed"] += 1
                    results["errors"].append(f"{test_class.__name__}.{method_name}: {str(e)}")
                except Exception as e:
                    print(f"❌ ERROR: {str(e)}")
                    results["failed"] += 1
                    results["errors"].append(f"{test_class.__name__}.{method_name}: {str(e)}")
                    traceback.print_exc()
    
    except Exception as e:
        print(f"❌ Failed to import {module_name}: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"{module_name}: {str(e)}")
        traceback.print_exc()


def main():
    """Run all universal tests."""
    print("\n" + "="*80)
    print("UNIVERSALIZATION TEST SUITE")
    print("="*80)
    
    # Test modules to run
    test_modules = [
        "tests.test_universal_profile_adapter",
        "tests.test_universal_config",
        "tests.test_biomarker_intelligence_universal"
    ]
    
    for module in test_modules:
        run_test_module(module)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📊 Total:  {results['passed'] + results['failed']}")
    
    if results["errors"]:
        print(f"\n❌ Errors:")
        for error in results["errors"]:
            print(f"   • {error}")
    
    print("="*80 + "\n")
    
    # Exit with error code if any failures
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    main()


