#!/usr/bin/env python3
"""
Unicode-safe wrapper for the API server
"""
import os
import sys
import subprocess

# Set environment variables for UTF-8 encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONLEGACYWINDOWSFSENCODING'] = '0'

if __name__ == "__main__":
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Run main.py
    try:
        # On Windows, use shell=False and specify encoding
        if sys.platform.startswith('win'):
            result = subprocess.run([sys.executable, "main.py"], shell=False, 
                                  encoding='utf-8', errors='replace', text=True)
            sys.exit(result.returncode)
        else:
            os.execv(sys.executable, [sys.executable, "main.py"])
    except Exception as e:
        print(f"Failed to run API server: {e}")
        sys.exit(1)