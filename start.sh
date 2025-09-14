#!/bin/bash

# Lead Automation System - Linux/Mac Startup Script

echo ""
echo "========================================="
echo "  Lead Automation System - Unix"
echo "========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Make the script executable
chmod +x start.py

# Run the Python startup script
python3 start.py "$@"