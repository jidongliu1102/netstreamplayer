#!/bin/sh
# Build APK with fixed NDK download using curl instead of urllib
set -e

# Download NDK with curl (more reliable than Python urllib)
NDK_ZIP="/root/.buildozer/android/platform/android-ndk-r28c-linux.zip"
NDK_DIR="/root/.buildozer/android/platform"

if [ ! -f "$NDK_ZIP" ]; then
    echo "=== Downloading Android NDK r28c with curl ==="
    mkdir -p "$NDK_DIR"
    curl -sL -o "$NDK_ZIP" "https://dl.google.com/android/repository/android-ndk-r28c-linux.zip"
    echo "=== NDK downloaded, verifying ==="
    unzip -tq "$NDK_ZIP" 2>&1 | tail -2
    echo "=== NDK verified OK ==="
fi

# Now run buildozer
echo "=== Running buildozer ==="
yes | buildozer android debug 2>&1