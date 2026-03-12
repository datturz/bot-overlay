#!/bin/bash
# Build script for macOS
# Run this on a macOS machine

echo "=== L2M Boss Timer - macOS Build Script ==="
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script must be run on macOS"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Install with: brew install python3"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install --upgrade pip
pip3 install pyqt5 pyttsx3 supabase python-dotenv pyinstaller

# Build the app
echo ""
echo "Building application..."
python3 -m PyInstaller --clean --noconfirm build_macos.spec

if [ $? -ne 0 ]; then
    echo "Error: Build failed"
    exit 1
fi

echo ""
echo "Build successful! App created at: dist/L2M_BossTimer.app"

# Create DMG
echo ""
echo "Creating DMG..."

# Check if create-dmg is installed
if ! command -v create-dmg &> /dev/null; then
    echo "Installing create-dmg..."
    brew install create-dmg
fi

# Create DMG
create-dmg \
    --volname "L2M Boss Timer" \
    --volicon "dist/L2M_BossTimer.app/Contents/Resources/icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "L2M_BossTimer.app" 150 190 \
    --hide-extension "L2M_BossTimer.app" \
    --app-drop-link 450 190 \
    "dist/L2M_BossTimer_v2.0.0.dmg" \
    "dist/L2M_BossTimer.app"

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Build Complete ==="
    echo "DMG created at: dist/L2M_BossTimer_v2.0.0.dmg"
else
    echo ""
    echo "DMG creation failed, but .app is available at: dist/L2M_BossTimer.app"
    echo "You can manually create DMG or just use the .app directly"
fi
