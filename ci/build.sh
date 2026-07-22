#!/bin/sh
echo "=== START buildozer android debug ==="
PYTHONHTTPSVERIFY=0 yes | /home/user/.venv/bin/buildozer -v android debug 2>&1 | tee /tmp/buildozer.log
echo "=== EXIT=$? ==="
