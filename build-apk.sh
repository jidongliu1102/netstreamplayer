#!/bin/bash
# build-apk.sh - Script to build the APK using Docker or local Buildozer
# Usage: bash build-apk.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== NetStreamPlayer APK Builder ==="
echo ""

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Docker found. Building with kivy/buildozer container..."
    
    # Check if Docker daemon is running
    if docker info &> /dev/null; then
        echo "Starting build with Buildozer Docker image..."
        docker run --rm -v "$(pwd)":/app kivy/buildozer:latest android debug
        echo ""
        echo "Build complete! APK should be in bin/ directory."
        exit 0
    else
        echo "Docker daemon is not running. Please start Docker Desktop first."
        echo ""
    fi
else
    echo "Docker not found."
fi

# Check if local buildozer is available
if command -v buildozer &> /dev/null; then
    echo "Local buildozer found. Building..."
    buildozer android debug
    echo ""
    echo "Build complete! APK should be in bin/ directory."
    exit 0
else
    echo "Local buildozer not found."
fi

echo ""
echo "=== ERROR: Neither Docker nor local Buildozer found! ==="
echo ""
echo "To install Docker:"
echo "  Windows: https://docs.docker.com/desktop/setup/install/windows-install/"
echo "  Linux:   curl -fsSL https://get.docker.com | sh"
echo ""
echo "To install Buildozer (Linux only):"
echo "  pip install buildozer"
echo ""
echo "To build manually with Docker:"
echo "  docker run --rm -v \"\$PWD\":/app kivy/buildozer:latest android debug"
echo ""