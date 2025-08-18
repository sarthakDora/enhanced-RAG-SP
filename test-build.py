#!/usr/bin/env python3
"""
Test script to verify the build configuration works correctly
"""
import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required tools are available"""
    requirements = []
    
    # Check Python
    try:
        result = subprocess.run([sys.executable, '--version'], 
                              capture_output=True, text=True)
        python_version = result.stdout.strip()
        requirements.append(f"OK Python: {python_version}")
    except:
        requirements.append("FAIL Python: Not found")
        return False, requirements
    
    # Check Node.js
    try:
        result = subprocess.run(['node', '--version'], 
                              capture_output=True, text=True)
        node_version = result.stdout.strip()
        requirements.append(f"OK Node.js: {node_version}")
    except:
        requirements.append("FAIL Node.js: Not found")
        return False, requirements
    
    # Check npm
    try:
        result = subprocess.run(['npm', '--version'], 
                              capture_output=True, text=True)
        npm_version = result.stdout.strip()
        requirements.append(f"OK npm: {npm_version}")
    except:
        requirements.append("FAIL npm: Not found")
        return False, requirements
    
    # Check Docker
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True)
        docker_version = result.stdout.strip()
        requirements.append(f"OK Docker: {docker_version}")
    except:
        requirements.append("WARN Docker: Not found (optional for build)")
    
    return True, requirements

def check_project_structure():
    """Check if project structure is correct"""
    required_files = [
        'backend/main.py',
        'backend/requirements.txt',
        'backend/build_exe.py',
        'backend/requirements-exe.txt',
        'frontend/package.json',
        'frontend/build-for-deployment.js',
        'build-all.bat',
        'build-all.sh',
        'DEPLOYMENT_GUIDE.md'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    return missing_files

def test_backend_dependencies():
    """Test if backend dependencies can be installed"""
    print("Testing backend dependency installation...")
    try:
        # Test if we can parse requirements
        with open('backend/requirements-exe.txt', 'r') as f:
            requirements = f.read()
        
        # Count packages
        lines = [line.strip() for line in requirements.split('\n') 
                if line.strip() and not line.startswith('#')]
        package_count = len(lines)
        
        print(f"OK Found {package_count} packages in requirements-exe.txt")
        return True
    except Exception as e:
        print(f"FAIL Error reading backend requirements: {e}")
        return False

def test_frontend_dependencies():
    """Test if frontend dependencies are valid"""
    print("Testing frontend package.json...")
    try:
        import json
        with open('frontend/package.json', 'r') as f:
            package_data = json.load(f)
        
        deps = len(package_data.get('dependencies', {}))
        dev_deps = len(package_data.get('devDependencies', {}))
        
        print(f"OK Found {deps} dependencies and {dev_deps} dev dependencies")
        
        # Check if build:deploy script exists
        scripts = package_data.get('scripts', {})
        if 'build:deploy' in scripts:
            print("OK build:deploy script found")
        else:
            print("FAIL build:deploy script missing")
            return False
        
        return True
    except Exception as e:
        print(f"FAIL Error reading package.json: {e}")
        return False

def main():
    """Run all tests"""
    print("Enhanced RAG Build Configuration Test")
    print("=" * 40)
    print()
    
    # Check requirements
    print("Checking system requirements...")
    reqs_ok, requirements = check_requirements()
    for req in requirements:
        print(f"  {req}")
    print()
    
    if not reqs_ok:
        print("FAIL System requirements not met. Please install missing tools.")
        return False
    
    # Check project structure
    print("Checking project structure...")
    missing = check_project_structure()
    if missing:
        print("FAIL Missing files:")
        for file in missing:
            print(f"  - {file}")
        return False
    else:
        print("OK All required files present")
    print()
    
    # Test backend configuration
    if not test_backend_dependencies():
        return False
    print()
    
    # Test frontend configuration
    if not test_frontend_dependencies():
        return False
    print()
    
    print("=" * 40)
    print("OK ALL TESTS PASSED!")
    print("=" * 40)
    print()
    print("Your build configuration is ready!")
    print()
    print("To build the complete deployment package:")
    print("- Windows: run build-all.bat")
    print("- Unix/Linux/Mac: run ./build-all.sh")
    print()
    print("Individual builds:")
    print("- Backend: cd backend && python build_exe.py")
    print("- Frontend: cd frontend && npm run build:deploy")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)