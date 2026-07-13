@echo off
REM sign-apk.bat - Sign the release APK
REM Usage: sign-apk.bat [path-to-unsigned-apk]

set KEYSTORE=netstreamplayer.keystore
set KEY_ALIAS=netstreamplayer
set KEYSTORE_PASS=android
set KEY_PASS=android

set APK_PATH=%~1
if "%APK_PATH%"=="" set APK_PATH=bin\NetStreamPlayer-1.0.0-arm64-v8a-release-unsigned.apk

echo === APK Signing Tool ===
echo.

if not exist "%APK_PATH%" (
    echo ERROR: APK not found: %APK_PATH%
    echo Usage: %~nx0 [path-to-unsigned-apk]
    pause
    exit /b 1
)

REM Generate keystore if needed
if not exist "%KEYSTORE%" (
    echo Generating keystore...
    keytool -genkey -v -keystore "%KEYSTORE%" -alias "%KEY_ALIAS%" ^
        -keyalg RSA -keysize 2048 -validity 10000 ^
        -storepass "%KEYSTORE_PASS%" -keypass "%KEY_PASS%" ^
        -dname "CN=NetStreamPlayer, OU=Development, O=NousResearch, L=Unknown, ST=Unknown, C=CN" ^
        -noprompt
    echo Keystore created: %KEYSTORE%
)

echo Signing APK: %APK_PATH%
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 ^
    -keystore "%KEYSTORE%" ^
    -storepass "%KEYSTORE_PASS%" -keypass "%KEY_PASS%" ^
    "%APK_PATH%" "%KEY_ALIAS%"

echo.
echo Signing complete!

set ALIGNED_APK=%APK_PATH:-unsigned=%
echo Aligned APK would be: %ALIGNED_APK%
echo.
echo To verify: jarsigner -verify -verbose -certs "%APK_PATH%"
echo.
pause