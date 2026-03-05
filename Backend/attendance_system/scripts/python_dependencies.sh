#!/usr/bin/env bash
set -e

PROJECT_MAIN_DIR_NAME="project/attendance/Backend/attendance_system"

# Validate variables
if [ -z "$PROJECT_MAIN_DIR_NAME" ]; then
    echo "Error: PROJECT_MAIN_DIR_NAME is not set. Please set it to your project directory name." >&2
    exit 1
fi

# Change ownership to ubuntu user
sudo chown -R ubuntu:ubuntu "/home/ubuntu/$PROJECT_MAIN_DIR_NAME"

# Create virtual environment
echo "Creating virtual environment..."
virtualenv "/home/ubuntu/project/venv"

# Activate virtual environment
echo "Activating virtual environment..."
source "/home/ubuntu/project/venv/bin/activate"

# Install dependencies
echo "Installing Python dependencies..."
pip install -r "/home/ubuntu/project/attendance/Backend/requirements.txt"

echo "Dependencies installed successfully."
