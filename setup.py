#!/usr/bin/env python3
"""
Setup script for Lead Automation System
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version {sys.version.split()[0]} is compatible")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_env_file():
    """Create .env file from template"""
    env_file = Path(".env")
    env_template = Path(".env.example")
    
    if env_file.exists():
        print("⚠️  .env file already exists")
        response = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if response != 'y':
            print("Keeping existing .env file")
            return True
    
    if not env_template.exists():
        print("❌ .env.example template not found")
        return False
    
    try:
        shutil.copy(env_template, env_file)
        print("✅ Created .env file from template")
        print("📝 Please edit .env file with your configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["logs", "temp", "exports"]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(exist_ok=True)
            print(f"📁 Created directory: {directory}")
    
    print("✅ Directories created successfully")
    return True

def check_google_service_account():
    """Check for Google service account file"""
    service_account_file = Path("google_service_account.json")
    
    if service_account_file.exists():
        print("✅ Google service account file found")
        return True
    else:
        print("⚠️  Google service account file not found")
        print("📋 Please follow these steps:")
        print("   1. Go to https://console.cloud.google.com/")
        print("   2. Create a new project or select existing")
        print("   3. Enable Google Sheets API")
        print("   4. Create service account credentials")
        print("   5. Download JSON key and save as 'google_service_account.json'")
        return False

def validate_setup():
    """Validate the setup"""
    print("\n🔍 Validating setup...")
    
    try:
        from config import Config
        validation = Config.validate()
        
        if validation['errors']:
            print("❌ Configuration validation failed:")
            for error in validation['errors']:
                print(f"   - {error}")
            return False
        
        if validation['warnings']:
            print("⚠️  Configuration warnings:")
            for warning in validation['warnings']:
                print(f"   - {warning}")
        
        print("✅ Setup validation completed")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("This might indicate missing dependencies")
        return False
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Lead Automation System")
    print("=" * 50)
    
    steps = [
        ("Checking Python version", check_python_version),
        ("Installing dependencies", install_dependencies),
        ("Creating .env file", create_env_file),
        ("Creating directories", create_directories),
        ("Checking Google service account", check_google_service_account),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if not step_func():
            print(f"❌ Setup failed at step: {step_name}")
            sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your configuration")
    print("2. Add google_service_account.json file")
    print("3. Run 'python main.py --validate' to check configuration")
    print("4. Run 'python main.py --info' to see system information")
    print("5. Run 'python main.py' to start the pipeline")
    
    print("\n💡 Useful commands:")
    print("   python main.py --help        # Show all options")
    print("   python main.py --validate    # Validate configuration")
    print("   python main.py --info        # Show system info")
    print("   python main.py              # Run full pipeline")

if __name__ == "__main__":
    main()