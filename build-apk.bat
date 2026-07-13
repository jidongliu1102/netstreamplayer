@echo off
REM build-apk.bat - Build NetStreamPlayer APK using Docker
REM Run this after Docker Desktop is fully started

echo === NetStreamPlayer APK Builder (Windows) ===
echo.

REM Check if docker is available
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found in PATH.
    echo Please start Docker Desktop and try again.
    echo Docker Desktop is installed at: C:\Program Files\Docker\Docker\
    pause
    exit /b 1
)

echo Docker found. Building APK...
echo Note: First build may take 20-30 minutes to download SDK/NDK.
echo.

docker run --rm -v "%cd%":/app kivy/buildozer:latest android debug

echo.
if %ERRORLEVEL% EQU 0 (
    echo Build successful! APK should be in bin\ directory.
    echo.
    echo To sign the APK, run: sign-apk.bat
) else (
    echo Build failed. Check the error messages above.
    echo Common issues:
    echo   - Docker Desktop not fully started
    echo   - Internet connection for downloading dependencies
    echo   - Disk space
)

pause