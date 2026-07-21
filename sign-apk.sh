#!/bin/bash
# sign-apk.sh - Sign a release APK with a debug key
# Usage: bash sign-apk.sh [path-to-unsigned-apk]

set -e

APK_PATH="${1:-bin/NetStreamPlayer-1.0.0-arm64-v8a-release-unsigned.apk}"
KEYSTORE="netstreamplayer.keystore"
KEY_ALIAS="netstreamplayer"
KEYSTORE_PASS="android"
KEY_PASS="android"

echo "=== APK Signing Tool ==="
echo ""

# Check if apk exists
if [ ! -f "$APK_PATH" ]; then
    echo "Error: APK not found: $APK_PATH"
    echo "Usage: $0 [path-to-unsigned-apk]"
    exit 1
fi

# Generate keystore if it doesn't exist
if [ ! -f "$KEYSTORE" ]; then
    echo "Generating keystore..."
    keytool -genkey -v -keystore "$KEYSTORE" -alias "$KEY_ALIAS" \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$KEYSTORE_PASS" -keypass "$KEY_PASS" \
        -dname "CN=NetStreamPlayer, OU=Development, O=NousResearch, L=Unknown, ST=Unknown, C=CN" \
        -noprompt
    echo "Keystore created: $KEYSTORE"
fi

# Sign the APK
echo "Signing APK: $APK_PATH"
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 \
    -keystore "$KEYSTORE" \
    -storepass "$KEYSTORE_PASS" -keypass "$KEY_PASS" \
    "$APK_PATH" "$KEY_ALIAS"

echo ""
echo "Signing complete!"

# Align if zipalign is available
ALIGNED_APK="${APK_PATH%-unsigned*}-signed.apk"
if command -v zipalign &> /dev/null; then
    echo "Aligning APK..."
    zipalign -f -v 4 "$APK_PATH" "$ALIGNED_APK"
    echo "Aligned APK: $ALIGNED_APK"
else
    echo "zipalign not found. APK signed but not aligned."
    echo "To align manually:"
    echo "  zipalign -f -v 4 \"$APK_PATH\" \"$ALIGNED_APK\""
fi

echo ""
echo "Done!"