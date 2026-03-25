#!/usr/bin/env python3
"""
UEFN Codex Agent - Verification & Health Check Script
Verifies that all components are properly integrated and working.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

class HealthCheck:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
    
    def print_header(self, text):
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}\n")
    
    def check(self, name: str, condition: bool, details: str = ""):
        if condition:
            print(f"✓ {name}")
            if details:
                print(f"  {details}")
            self.checks_passed += 1
        else:
            print(f"✗ {name}")
            if details:
                print(f"  {details}")
            self.checks_failed += 1
    
    def warn(self, message):
        print(f"⚠ {message}")
        self.warnings.append(message)
    
    def verify_project_structure(self):
        self.print_header("Project Structure Verification")
        
        # Check critical directories
        dirs = [
            ("app/backend", "Backend server directory"),
            ("app/frontend", "React frontend application"),
            ("app/electron", "Electron main process"),
            ("vendor/uefn-toolbelt", "UEFN-TOOLBELT vendor package"),
            ("config", "Configuration files"),
            ("data", "Data directory"),
            ("docs", "Documentation"),
        ]
        
        for dir_path, description in dirs:
            full_path = self.project_root / dir_path
            self.check(
                f"Directory exists: {dir_path}",
                full_path.exists(),
                description if not full_path.exists() else str(full_path)
            )
    
    def verify_python_setup(self):
        self.print_header("Python Setup Verification")
        
        # Check Python version
        try:
            result = subprocess.run(
                [sys.executable, "--version"],
                capture_output=True,
                text=True
            )
            python_version = result.stdout.strip()
            self.check(
                "Python installed",
                sys.version_info >= (3, 11),
                f"Found: {python_version}"
            )
        except Exception as e:
            self.check("Python installed", False, str(e))
        
        # Check backend files
        backend_files = [
            "app/backend/server.py",
            "app/backend/requirements.txt",
        ]
        
        for file_path in backend_files:
            full_path = self.project_root / file_path
            self.check(
                f"Backend file exists: {file_path}",
                full_path.exists()
            )
    
    def verify_node_setup(self):
        self.print_header("Node.js Setup Verification")
        
        # Check Node version
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True
            )
            node_version = result.stdout.strip()
            self.check(
                "Node.js installed",
                True,
                f"Found: {node_version}"
            )
        except Exception:
            self.check("Node.js installed", False, "Node.js not found in PATH")
        
        # Check npm
        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True
            )
            npm_version = result.stdout.strip()
            self.check(
                "npm installed",
                True,
                f"Found: npm {npm_version}"
            )
        except Exception:
            self.check("npm installed", False, "npm not found in PATH")
    
    def verify_uefn_toolbelt(self):
        self.print_header("UEFN-TOOLBELT Verification")
        
        toolbelt_root = self.project_root / "vendor" / "uefn-toolbelt"
        
        # Check toolbelt structure
        toolbelt_files = [
            "Content/Python/UEFN_Toolbelt/__init__.py",
            "Content/Python/UEFN_Toolbelt/core/__init__.py",
            "Content/Python/UEFN_Toolbelt/registry.py",
            "mcp_server.py",
            "launcher.py",
            "README.md",
        ]
        
        for file_path in toolbelt_files:
            full_path = toolbelt_root / file_path
            self.check(
                f"Toolbelt file: {file_path}",
                full_path.exists()
            )
    
    def verify_app_integration(self):
        self.print_header("App Integration Verification")
        
        # Check app structure
        app_files = [
            "app/backend/server.py",
            "app/electron/package.json",
            "app/electron/src/main.ts",
            "app/electron/src/preload.ts",
            "app/frontend/src/App.tsx",
            "app/frontend/src/index.tsx",
            "app/frontend/package.json",
            "app/frontend/tsconfig.json",
        ]
        
        for file_path in app_files:
            full_path = self.project_root / file_path
            self.check(
                f"App integration: {file_path}",
                full_path.exists()
            )
    
    def verify_documentation(self):
        self.print_header("Documentation Verification")
        
        docs = [
            "UNIFIED_APP_README.md",
            "INTEGRATION_PLAN.md",
            "DEVELOPMENT.md",
        ]
        
        for doc in docs:
            full_path = self.project_root / doc
            self.check(
                f"Documentation: {doc}",
                full_path.exists()
            )
    
    def verify_backend_can_start(self):
        self.print_header("Backend Startup Verification")
        
        try:
            result = subprocess.run(
                [sys.executable, "-c", 
                 "import fastapi; import uvicorn; print('FastAPI ready')"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.check(
                "FastAPI dependencies importable",
                result.returncode == 0,
                result.stdout.strip() if result.stdout else result.stderr.strip()
            )
        except Exception as e:
            self.warn(f"Could not verify FastAPI import: {e}")
    
    def verify_frontend_ready(self):
        self.print_header("Frontend Build Verification")
        
        package_json = self.project_root / "app/frontend/package.json"
        if package_json.exists():
            with open(package_json) as f:
                config = json.load(f)
                self.check(
                    "React configured",
                    "react" in config.get("dependencies", {})
                )
    
    def verify_electron_ready(self):
        self.print_header("Electron Configuration Verification")
        
        package_json = self.project_root / "app/electron/package.json"
        if package_json.exists():
            with open(package_json) as f:
                config = json.load(f)
                self.check(
                    "Electron configured",
                    "electron" in config.get("devDependencies", {})
                )
    
    def print_summary(self):
        self.print_header("Summary")
        
        total = self.checks_passed + self.checks_failed
        percentage = (self.checks_passed / total * 100) if total > 0 else 0
        
        print(f"Checks Passed: {self.checks_passed}/{total} ({percentage:.1f}%)")
        print(f"Checks Failed: {self.checks_failed}/{total}")
        print(f"Warnings: {len(self.warnings)}")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print("\n" + "="*60)
        if self.checks_failed == 0:
            print("✓ All checks passed! Application is ready to use.")
        elif self.checks_failed < 3:
            print("⚠ Some checks failed. Review above for details.")
        else:
            print("✗ Multiple checks failed. See above for details.")
        print("="*60 + "\n")
    
    def run_all_checks(self):
        print("\n")
        print("╔" + "="*58 + "╗")
        print("║" + " "*58 + "║")
        print("║  UEFN Codex Agent - System Health Check" + " "*16 + "║")
        print("║" + " "*58 + "║")
        print("╚" + "="*58 + "╝")
        
        self.verify_project_structure()
        self.verify_python_setup()
        self.verify_node_setup()
        self.verify_uefn_toolbelt()
        self.verify_app_integration()
        self.verify_documentation()
        self.verify_backend_can_start()
        self.verify_frontend_ready()
        self.verify_electron_ready()
        
        self.print_summary()
        
        return self.checks_failed == 0

def main():
    checker = HealthCheck()
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
