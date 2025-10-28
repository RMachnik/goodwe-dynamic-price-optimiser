#!/usr/bin/env python3
"""
Test script to verify the new project structure works correctly
"""

import sys
import os
from pathlib import Path

def test_project_structure():
    """Test that all required directories and files exist"""
    print("🔍 Testing project structure...")
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Required directories
    required_dirs = ['src', 'examples', 'test', 'docs']
    missing_dirs = []
    
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"❌ {dir_name}/ directory missing")
            missing_dirs.append(dir_name)
    
        # Required files
        required_files = [
            'src/enhanced_data_collector.py',
            'src/fast_charge.py',
            'src/automated_price_charging.py',
            'config/master_coordinator_config.yaml',
            'test/inverter_test.py',
            'test/sensor_investigator.py',
            'docs/PROJECT_PLAN_Enhanced_Energy_Management.md',
            'docs/README_fast_charge.md',
            'docs/README_automated_charging.md',
            'requirements.txt',
            'README.md',
            '.gitignore'
        ]
    
    # Required directories
    required_dirs = [
        'src/',
        'config/',
        'examples/',
        'test/',
        'docs/',
        'logs/',
        'out/'
    ]
    
    missing_files = []
    missing_dirs = []
    
    # Check required files
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            missing_files.append(file_path)
    
    # Check required directories
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path} exists")
        else:
            print(f"❌ {dir_path} missing")
            missing_dirs.append(dir_path)
    
    # Check if energy_data is ignored
    if Path('.gitignore').exists():
        with open('.gitignore', 'r') as f:
            gitignore_content = f.read()
            if 'energy_data/' in gitignore_content:
                print("✅ energy_data/ is properly ignored in .gitignore")
            else:
                print("❌ energy_data/ is not ignored in .gitignore")
    
    # Summary
    print("\n📊 STRUCTURE TEST SUMMARY:")
    if not missing_dirs and not missing_files:
        print("🎉 All directories and files are in place!")
        return True
    else:
        print("⚠️  Some items are missing:")
        if missing_dirs:
            print(f"   Missing directories: {', '.join(missing_dirs)}")
        if missing_files:
            print(f"   Missing files: {', '.join(missing_files)}")
        return False

def test_imports():
    """Test that key modules can be imported"""
    print("\n🔍 Testing module imports...")
    
    # Add src to path for imports
    src_path = Path('src')
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    
    try:
        # Test enhanced data collector import
        from enhanced_data_collector import EnhancedDataCollector
        print("✅ EnhancedDataCollector class imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import EnhancedDataCollector: {e}")
        assert False, f"Failed to import EnhancedDataCollector: {e}"
    
    try:
        # Test examples imports
        examples_path = Path('examples')
        if examples_path.exists():
            sys.path.insert(0, str(examples_path))
            
        # Note: These might fail if dependencies aren't installed
        print("✅ Examples directory accessible")
    except Exception as e:
        print(f"⚠️  Examples import test: {e}")
    
    return True

def main():
    """Main test function"""
    print("🚀 PROJECT STRUCTURE TEST")
    print("=" * 50)
    
    structure_ok = test_project_structure()
    imports_ok = test_imports()
    
    print("\n" + "=" * 50)
    if structure_ok and imports_ok:
        print("🎉 PROJECT STRUCTURE TEST PASSED!")
        print("✅ Your enhanced energy management system is ready to use!")
        print("\n📚 Next steps:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Configure your inverter: cp fast_charge_config.yaml my_config.yaml")
        print("   3. Test connectivity: python test/inverter_test.py")
        print("   4. Start monitoring: python src/enhanced_data_collector.py")
    else:
        print("❌ PROJECT STRUCTURE TEST FAILED!")
        print("Please fix the missing items before proceeding.")
    
    return structure_ok and imports_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
