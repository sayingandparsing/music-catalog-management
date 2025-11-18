#!/bin/bash
# Quick installer for sacd_extract on macOS

set -e

echo "=========================================="
echo "SACD Extract Installer for macOS"
echo "=========================================="
echo ""

# Check if sacd_extract is already installed
if command -v sacd_extract &> /dev/null; then
    echo "✓ sacd_extract is already installed!"
    sacd_extract --help || true
    exit 0
fi

echo "sacd_extract is not installed. Installing..."
echo ""

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "Downloading sacd_extract..."
echo ""
echo "Please follow these steps:"
echo ""
echo "1. Visit: https://github.com/sacd-ripper/sacd-ripper/releases"
echo "2. Download the latest macOS release"
echo "3. Save it to: $TEMP_DIR"
echo ""
echo "Available options:"
echo ""
echo "Option A: Download pre-built binary (if available)"
echo "  - Look for 'sacd_extract-macos' or similar"
echo ""
echo "Option B: Build from source using Homebrew"
echo ""

read -p "Press Enter after downloading the binary, or type 'build' to build from source: " choice

if [ "$choice" = "build" ]; then
    echo ""
    echo "Building from source..."
    echo ""
    
    # Check for required tools
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    # Install dependencies
    echo "Installing build dependencies..."
    brew install cmake git
    
    # Clone and build
    echo "Cloning repository..."
    git clone https://github.com/sacd-ripper/sacd-ripper.git
    cd sacd-ripper
    
    echo "Building..."
    mkdir -p build
    cd build
    cmake ..
    make
    
    # Install
    echo "Installing to /usr/local/bin/..."
    sudo cp sacd_extract /usr/local/bin/
    sudo chmod +x /usr/local/bin/sacd_extract
    
else
    # Install downloaded binary
    echo ""
    echo "Looking for downloaded binary..."
    
    # Find the binary
    BINARY=$(find "$TEMP_DIR" -name "*sacd_extract*" -type f | head -1)
    
    if [ -z "$BINARY" ]; then
        echo "❌ Could not find sacd_extract binary in $TEMP_DIR"
        echo ""
        echo "Please manually install:"
        echo "  1. Download from: https://github.com/sacd-ripper/sacd-ripper/releases"
        echo "  2. Extract and make executable: chmod +x sacd_extract"
        echo "  3. Move to PATH: sudo mv sacd_extract /usr/local/bin/"
        exit 1
    fi
    
    echo "Found: $BINARY"
    echo "Installing to /usr/local/bin/..."
    
    chmod +x "$BINARY"
    sudo cp "$BINARY" /usr/local/bin/sacd_extract
fi

# Verify installation
echo ""
echo "Verifying installation..."
if command -v sacd_extract &> /dev/null; then
    echo "✓ sacd_extract installed successfully!"
    echo ""
    sacd_extract --help || true
    echo ""
    echo "=========================================="
    echo "Installation complete!"
    echo "You can now process SACD ISO files."
    echo "=========================================="
else
    echo "❌ Installation failed. Please install manually."
    echo "See INSTALL_SACD_EXTRACT.md for detailed instructions."
    exit 1
fi

# Cleanup
cd /
rm -rf "$TEMP_DIR"

