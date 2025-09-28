#!/usr/bin/env python3
"""
Perplexity Lead Enrichment - Startup Script
Launches the FastAPI backend and (optionally) the frontend build
"""

import os
import sys
import subprocess
import time
import threading
import signal
from pathlib import Path

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.ENDC}")

def print_banner():
    """Print startup banner"""
    banner = """
==============================================
  PERPLEXITY LEAD ENRICHMENT LAUNCHER
  Generate prompt -> query Perplexity -> parse results
==============================================
"""
    print_colored(banner, Colors.HEADER)

def check_requirements():
    """Check if all requirements are met"""
    print_colored("🔍 Checking requirements...", Colors.OKBLUE)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print_colored("❌ Python 3.8 or higher is required", Colors.FAIL)
        return False
    print_colored(f"✅ Python {sys.version.split()[0]}", Colors.OKGREEN)
    
    # Check if node is available for frontend
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print_colored(f"✅ Node.js {result.stdout.strip()}", Colors.OKGREEN)
        else:
            print_colored("⚠️  Node.js not found - frontend will not be available", Colors.WARNING)
    except FileNotFoundError:
        print_colored("⚠️  Node.js not found - frontend will not be available", Colors.WARNING)
    
    # Check if required files exist
    required_files = ['.env', 'requirements.txt', 'api/main.py']
    for file in required_files:
        if Path(file).exists():
            print_colored(f"✅ {file} found", Colors.OKGREEN)
        else:
            print_colored(f"❌ {file} missing", Colors.FAIL)
            return False
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    print_colored("📦 Installing Python dependencies...", Colors.OKBLUE)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print_colored("✅ Python dependencies installed", Colors.OKGREEN)
        return True
    except subprocess.CalledProcessError as e:
        print_colored(f"❌ Failed to install Python dependencies: {e}", Colors.FAIL)
        return False

def install_frontend_dependencies():
    """Install frontend dependencies"""
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print_colored("⚠️  Frontend directory not found", Colors.WARNING)
        return False
    
    print_colored("📦 Installing frontend dependencies...", Colors.OKBLUE)
    try:
        subprocess.check_call(['npm', 'install'], cwd=frontend_dir)
        print_colored("✅ Frontend dependencies installed", Colors.OKGREEN)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print_colored(f"❌ Failed to install frontend dependencies: {e}", Colors.FAIL)
        return False

def build_frontend():
    """Build the frontend"""
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        return False
    
    print_colored("🏗️  Building frontend...", Colors.OKBLUE)
    try:
        subprocess.check_call(['npm', 'run', 'build'], cwd=frontend_dir)
        print_colored("✅ Frontend built successfully", Colors.OKGREEN)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print_colored(f"❌ Failed to build frontend: {e}", Colors.FAIL)
        return False

def start_backend():
    """Start the backend server"""
    print_colored("🚀 Starting backend server...", Colors.OKBLUE)
    try:
        # Import uvicorn here to avoid import errors if not installed
        import uvicorn
        uvicorn.run(
            "api.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError:
        print_colored("❌ uvicorn not found. Installing...", Colors.WARNING)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]"])
        import uvicorn
        uvicorn.run(
            "api.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )

def start_frontend_dev():
    """Start the frontend development server"""
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print_colored("⚠️  Frontend directory not found", Colors.WARNING)
        return
    
    print_colored("🌐 Starting frontend development server...", Colors.OKBLUE)
    try:
        subprocess.call(['npm', 'start'], cwd=frontend_dir)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print_colored(f"❌ Failed to start frontend: {e}", Colors.FAIL)

def main():
    """Main function"""
    print_banner()
    
    if not check_requirements():
        print_colored("❌ Requirements check failed", Colors.FAIL)
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--backend-only':
            print_colored("🔧 Starting backend only...", Colors.OKCYAN)
            start_backend()
            return
        elif sys.argv[1] == '--setup':
            print_colored("🔧 Running setup only...", Colors.OKCYAN)
            install_frontend_dependencies()
            build_frontend()
            print_colored("✅ Setup completed!", Colors.OKGREEN)
            return
        elif sys.argv[1] == '--dev':
            print_colored("🔧 Starting development mode...", Colors.OKCYAN)
            install_frontend_dependencies()
            
            # Start backend in a separate thread
            backend_thread = threading.Thread(target=start_backend)
            backend_thread.daemon = True
            backend_thread.start()
            
            # Give backend time to start
            time.sleep(3)
            
            # Start frontend dev server
            start_frontend_dev()
            return
    
    # Production mode - build frontend and start backend
    print_colored("🔧 Production mode - building frontend...", Colors.OKCYAN)
    install_frontend_dependencies()
    build_frontend()
    
    print_colored("\n" + "="*60, Colors.HEADER)
    print_colored("🎉 LEAD AUTOMATION SYSTEM STARTED!", Colors.OKGREEN)
    print_colored("="*60, Colors.HEADER)
    print_colored("🌐 Frontend: http://localhost:8000", Colors.OKCYAN)
    print_colored("🔧 Backend API: http://localhost:8000/api", Colors.OKCYAN)
    print_colored("📖 API Docs: http://localhost:8000/docs", Colors.OKCYAN)
    print_colored("="*60 + "\n", Colors.HEADER)
    
    # Start backend
    start_backend()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n⚠️  Shutting down...", Colors.WARNING)
        sys.exit(0)
    except Exception as e:
        print_colored(f"❌ Unexpected error: {e}", Colors.FAIL)
        sys.exit(1)
