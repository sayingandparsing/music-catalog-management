#!/bin/bash
# Setup script for DSD Music Converter

set -e

echo "==================================="
echo "DSD Music Converter - Setup"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.9"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)"; then
    echo "Error: Python 3.9 or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Check ffmpeg
echo "Checking ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg not found"
    echo ""
    echo "Please install ffmpeg:"
    echo "  macOS:    brew install ffmpeg"
    echo "  Ubuntu:   sudo apt-get install ffmpeg"
    echo "  Fedora:   sudo dnf install ffmpeg"
    exit 1
fi
FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1)
echo "✓ $FFMPEG_VERSION"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "Error: requirements.txt not found"
    exit 1
fi
echo ""

# Create .state directory
echo "Creating state directory..."
mkdir -p .state
echo "✓ .state directory created"
echo ""

# Make main.py executable
echo "Making main.py executable..."
chmod +x src/main.py
echo "✓ main.py is now executable"
echo ""

echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "Quick start:"
echo "  python3 src/main.py /path/to/music --archive /path/to/archive"
echo ""
echo "For more information, see README.md"

