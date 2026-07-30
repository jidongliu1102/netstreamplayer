# NetStreamPlayer - Network Video Stream Player for Android

A Python-based Android application for playing MJPEG video streams from Motion and MJPG-Streamer.

## Features

- Add and manage multiple video sources (name, URL, username, password)
- Play MJPEG streams from Motion and MJPG-Streamer
- HTTP Basic Authentication support
- Fullscreen and windowed mode
- Portrait and landscape orientation
- Pinch-to-zoom and pan gestures
- Screenshot capture
- Video recording (frame-by-frame to JPEG)
- Configurable save directory

## Requirements

### For Development
- Python 3.11+
- Kivy 2.3.1
- Requests
- Pillow

### For Building APK
- Docker Desktop (recommended, for using Buildozer container)
- Or Linux environment with Buildozer installed

## Quick Start (Development)

```bash
# Install dependencies
uv venv --python 3.11
source .venv/Scripts/activate  # Windows
uv pip install kivy requests pillow

# Run the app
python main.py
```

## Building APK

### Using Docker (Windows/Mac/Linux)

```bash
# Build the APK
docker run --rm -v "%cd%":/app kivy/buildozer:latest android debug
```

### Using Docker (Linux/macOS)

```bash
docker run --rm -v "$(pwd)":/app kivy/buildozer:latest android debug
```

### Using Buildozer directly (Linux only)

```bash
# Install buildozer
pip install buildozer

# Build the APK
buildozer android debug
```

The APK will be located at `bin/NetStreamPlayer-1.0.0-<arch>-debug.apk`

## Signing the APK

```bash
# Generate a keystore (if you don't have one)
keytool -genkey -v -keystore netstreamplayer.keystore -alias netstreamplayer \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass android -keypass android

# Sign the APK
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 \
  -keystore netstreamplayer.keystore \
  bin/NetStreamPlayer-1.0.0-release-unsigned.apk netstreamplayer

# Align the APK
zipalign -f -v 4 \
  bin/NetStreamPlayer-1.0.0-release-unsigned.apk \
  bin/NetStreamPlayer-1.0.0-release.apk
```

## Stream URL Formats

### Motion
```
http://192.168.1.100:8081/
```

### MJPG-Streamer
```
http://192.168.1.100:8080/?action=stream
```

### With Authentication
```
http://username:password@192.168.1.100:8080/?action=stream
```

## Project Structure

```
d:/dp/
├── main.py              # Main application code
├── videostreamer.kv     # Kivy UI definition
├── buildozer.spec       # Build configuration for APK
├── sources.json         # Saved video sources (auto-created)
├── captures/            # Screenshots and recordings (auto-created)
└── README.md            # This file
```

## License

MIT