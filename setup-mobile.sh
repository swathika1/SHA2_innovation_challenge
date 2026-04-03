#!/bin/bash
# SHA2 Rehab Coach - Mobile App Quick Setup for macOS/Linux/WSL

set -e  # Exit on error

echo
echo "========================================="
echo "SHA2 Rehab Coach - Mobile App Setup"
echo "========================================="
echo

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found. Please install from https://nodejs.org/"
    exit 1
fi

echo "[✓] Node.js found:"
node --version

# Check npm
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found."
    exit 1
fi

echo "[✓] npm found:"
npm --version

echo
echo "[1] Installing npm dependencies..."
npm install

echo "[✓] Dependencies installed"

echo
echo "[2] Checking Capacitor..."
npx cap --version || {
    echo "ERROR: Capacitor not accessible"
    exit 1
}

echo "[✓] Capacitor available"

echo
echo "[3] Syncing files to Android..."
npx cap sync || echo "WARNING: Capacitor sync had issues, but continuing..."

echo
echo "========================================="
echo "Setup Complete! ✓"
echo "========================================="
echo
echo "Next steps:"
echo " 1. Open in Android Studio:"
echo "    npm run open:android"
echo
echo " 2. Or start emulator and run:"
echo "    npx cap run android"
echo
echo "For more details, see MOBILE_APP_SETUP.md"
echo

# Optional: Ask to open Android Studio
read -p "Open Android Studio now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    npx cap open android
fi
