#!/bin/sh
set -e
P4A=/root/.buildozer/android/platform/python-for-android

echo "=== START buildozer android debug ==="

# Pass 1: clone p4a + accept SDK licenses + apply patches (before compile)
PYTHONHTTPSVERIFY=0 yes | /home/user/.venv/bin/buildozer -v android debug 2>&1 || true

# Patch p4a now that it's cloned
if [ -d "$P4A" ]; then
  echo "=== applying p4a patches (cython 3.0.11 + libx264 chmod) ==="
  /usr/bin/python3 /app/ci/patch_p4a.py "$P4A"
  # also patch the already-generated dist template if present
  DIST=/root/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/netstreamplayer/templates/AndroidManifest.tmpl.xml
  if [ -f "$DIST" ]; then sed -i '/android:hardwareAccelerated/d' "$DIST"; fi
else
  echo "p4a not cloned yet, skipping patches"
fi

# Pass 2: the real build
PYTHONHTTPSVERIFY=0 yes | /home/user/.venv/bin/buildozer -v android debug 2>&1 | tee /tmp/buildozer.log
echo "=== EXIT=$? ==="
