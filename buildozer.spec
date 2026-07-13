[app]

title = NetStreamPlayer
package.name = netstreamplayer
package.domain = com.nousresearch

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

requirements = python3,kivy==2.3.1,requests

orientation = portrait
# Android manifest orientation (supports sensor-based rotation)
android.manifest.orientation = fullSensor
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 34
android.minapi = 21
android.log_level = info
android.gradle_dependencies = 'androidx.core:core:1.12.0'

[buildozer]
log_level = 2
warn_on_root = 1