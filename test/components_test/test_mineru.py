#!/usr/bin/env python3
"""
Test script for mineru command line tool
"""

import subprocess
import os
import sys
import tempfile
import shutil

# Test configuration

test_file = "/home/hxdi/Kosmos/test_data/KIMI K2_OPEN AGENTIC INTELLIGENCE.pdf"
test_file = "GLM-4.5_Agentic, Reasoning, and Coding (ARC).pdf"
output_dir = "/home/hxdi/Kosmos/test_data"
backend = "vlm-http-client"
mineru_server_url = "http://10.17.99.13:30005"
mineru_model_source = "modelscope"

def test_mineru_version():
    """Test mineru version command"""
    print("Testing mineru version...")
    try:
        result = subprocess.run(['mineru', '--version'],
                               capture_output=True, text=True, check=True)
        print(f"mineru version: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error testing version: {e}")
        return False

def test_mineru_help():
    """Test mineru help command"""
    print("Testing mineru help...")
    try:
        result = subprocess.run(['mineru', '--help'],
                               capture_output=True, text=True, check=True)
        print("mineru help command works")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error testing help: {e}")
        return False

def test_mineru_basic():
    """Test basic mineru functionality"""
    print("Testing basic mineru functionality...")

    # Check if test file exists
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return False

    # Create a temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Run mineru with basic parameters
            cmd = [
                'mineru',
                '--path', test_file,
                '--output', temp_dir,
                '--backend', backend,
                '--url', mineru_server_url,
                '--source', mineru_model_source
            ]

            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            print("mineru basic test passed")
            print(f"stdout: {result.stdout}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Error in basic test: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return False

def test_mineru_with_method():
    """Test mineru with specific method parameter"""
    print("Testing mineru with method parameter...")

    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            cmd = [
                'mineru',
                '--path', test_file,
                '--output', temp_dir,
                '--backend', backend,
                '--url', mineru_server_url,
                '--source', mineru_model_source,
                '--method', 'auto'
            ]

            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            print("mineru method test passed")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Error in method test: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return False

def main():
    """Run all tests"""
    print("Starting mineru tests...")

    tests = [
        test_mineru_version,
        test_mineru_help,
        test_mineru_basic,
        test_mineru_with_method
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print(f"Test {test.__name__}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"Test {test.__name__}: ERROR - {e}")
            results.append(False)

    print(f"\nResults: {sum(results)}/{len(results)} tests passed")

    if all(results):
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())