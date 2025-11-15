#!/usr/bin/env python3
"""
Test script to verify DSD Music Converter setup.
Checks dependencies, configuration, and basic functionality.
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check Python version."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (3.9+ required)")
        return False


def check_ffmpeg():
    """Check if ffmpeg is installed."""
    print("Checking ffmpeg...")
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"  ✓ {version_line}")
            return True
        else:
            print("  ✗ ffmpeg not working properly")
            return False
    except FileNotFoundError:
        print("  ✗ ffmpeg not found")
        print("     Install: brew install ffmpeg (macOS)")
        print("              sudo apt-get install ffmpeg (Ubuntu)")
        return False
    except Exception as e:
        print(f"  ✗ Error checking ffmpeg: {e}")
        return False


def check_python_modules():
    """Check required Python modules."""
    print("Checking Python modules...")
    
    required_modules = {
        'click': 'click',
        'yaml': 'pyyaml',
        'mutagen': 'mutagen',
        'musicbrainzngs': 'python-musicbrainzngs',
        'discogs_client': 'python3-discogs-client',
        'tqdm': 'tqdm'
    }
    
    all_installed = True
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            print(f"  ✓ {package_name}")
        except ImportError:
            print(f"  ✗ {package_name} not installed")
            all_installed = False
    
    if not all_installed:
        print("\n  Install missing modules:")
        print("    pip3 install -r requirements.txt")
    
    return all_installed


def check_project_structure():
    """Check project structure."""
    print("Checking project structure...")
    
    required_files = [
        'config.yaml',
        'requirements.txt',
        'src/__init__.py',
        'src/main.py',
        'src/config.py',
        'src/logger.py',
        'src/scanner.py',
        'src/archiver.py',
        'src/converter.py',
        'src/state_manager.py',
        'src/metadata_enricher.py'
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} missing")
            all_exist = False
    
    return all_exist


def check_config():
    """Check configuration file."""
    print("Checking configuration...")
    
    config_file = Path('config.yaml')
    if not config_file.exists():
        print("  ✗ config.yaml not found")
        print("     Copy config.example.yaml to config.yaml and customize")
        return False
    
    try:
        import yaml
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check archive_dir
        archive_dir = config.get('paths', {}).get('archive_dir')
        if not archive_dir or archive_dir == '/path/to/your/archive':
            print("  ⚠ archive_dir not configured in config.yaml")
            print("     Set paths.archive_dir to a valid directory")
            return False
        
        print(f"  ✓ config.yaml valid")
        return True
        
    except Exception as e:
        print(f"  ✗ Error reading config.yaml: {e}")
        return False


def test_imports():
    """Test importing main modules."""
    print("Testing module imports...")
    
    sys.path.insert(0, str(Path('src').absolute()))
    
    modules = [
        'config',
        'logger',
        'scanner',
        'archiver',
        'converter',
        'state_manager',
        'metadata_enricher'
    ]
    
    all_imported = True
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            all_imported = False
    
    return all_imported


def main():
    """Run all tests."""
    print("=" * 50)
    print("DSD Music Converter - Setup Verification")
    print("=" * 50)
    print()
    
    tests = [
        ("Python Version", check_python_version),
        ("FFmpeg", check_ffmpeg),
        ("Python Modules", check_python_modules),
        ("Project Structure", check_project_structure),
        ("Configuration", check_config),
        ("Module Imports", test_imports)
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
        print()
    
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8s} {test_name}")
        if not result:
            all_passed = False
    
    print()
    
    if all_passed:
        print("All tests passed! ✓")
        print()
        print("You can now use the converter:")
        print("  python3 src/main.py /path/to/music --archive /path/to/archive")
        return 0
    else:
        print("Some tests failed. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

