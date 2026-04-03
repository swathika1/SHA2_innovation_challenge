# SHA2 Rehab Coach - Mobile App Setup Guide

## 🚀 Quick Start

This guide explains how to convert your Flask web app to a mobile app using **Capacitor** and test it on an Android emulator.

### Current Branch: `mobile-app`
You're on the dedicated mobile development branch. Your original code is safe on `docker-add`.

---

## 📋 What's New in Mobile Branch

### Files Created:
- `package.json` - Node.js project configuration
- `capacitor.config.json` - Capacitor mobile configuration
- `android/AndroidManifest.xml` - Android app manifest with permissions
- `static/mobile.css` - Responsive design for mobile screens
- `static/mobile-app.js` - Capacitor integration & device features
- `static/service-worker.js` - Offline support & caching
- `static/index-mobile.html` - Mobile app entry point
- `templates/base.html` - **Updated** with mobile CSS & scripts

### How It Works:

```
Your Flask Backend (unchanged!)
       ↑
       │ API Calls
       ↓
Capacitor Wrapper (Android/iOS shell)
       ↓
Mobile responsive UI (same HTML/CSS as web)
```

---

## 🔧 Installation & Setup

### Prerequisites:

1. **Node.js** (v16+) - Check: `node --version`
   - Already have: v22.20.0 ✅

2. **Android Studio** with Android Emulator
   - [Download](https://developer.android.com/studio)
   - Install API Level 26+ 

3. **Java Development Kit (JDK)**
   - Android Studio comes with it
   - Or install: `npm install -g @capacitor-community/android`

### Step 1: Install Dependencies

```bash
cd \\wsl.localhost\Ubuntu\home\swathika\IC26\docker\SHA2_innovation_challenge

# Install Node packages
npm install

# Verify installation
npx cap --version
```

**If PowerShell execution policy fails:**
```powershell
# Run as Administrator in PowerShell:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try npm install again
```

---

### Step 2: Initialize Capacitor for Android

```bash
# Create Capacitor project (interactive)
npx cap init

# When prompted:
# - App name: SHA2 Rehab Coach
# - App ID: com.sha2.rehabcoach
# - Web dir: static  <-- IMPORTANT!

# Add Android platform
npx cap add android

# Sync your web files to Android
npx cap sync
```

---

### Step 3: Configure Backend URL

Before building, ensure your Android emulator can reach your Flask backend:

**Edit `capacitor.config.json`:**

```json
{
  "server": {
    "androidScheme": "http",  // "https" if production
    "allowNavigation": ["*"],
    "cleartext": true          // Allow HTTP (dev only)
  }
}
```

**Then add your backend URL:**

```bash
# If using external IP (accessible from emulator):
npm run sync -- --host=http://192.168.1.100:5000

# Or set in capacitor.config.json:
"server": {
  "url": "http://10.0.2.2:5000"  // Android emulator localhost shorthand
}
```

---

## 📱 Running on Android Emulator

### Option A: Using Android Studio (GUI - Easiest)

```bash
# 1. Open Android project in Studio
npx cap open android

# 2. In Android Studio:
#    - Click "Run" (▶️) button
#    - Select emulator from dropdown
#    - Watch it build and launch!
```

### Option B: Command Line

```bash
# 1. Start emulator first
# List available emulators:
emulator -list-avds

# Start one:
emulator -avd Pixel_4_API_30

# 2. Build and run app
npx cap run android

# 3. View logs
adb logcat | grep -i "SHA2\|MobileApp\|Error"
```

---

## ✅ Testing the Mobile App

Once running on emulator:

1. **Check responsive layout**
   - Buttons are large (44px minimum)
   - Text is readable
   - Video fits screen
   - Navigation works

2. **Test camera access**
   - Emulator: Settings → Permissions → Camera → Allow
   - Try camera test page

3. **Test networking**
   - Should connect to your Flask backend
   - Check emulator IP: Settings → About phone → IP address

4. **Offline mode**
   - Disable network: Emulator Control Panel → Uncheck "Connected"
   - App should show offline indicator

---

## 🐛 Troubleshooting

### "Cannot connect to backend"

```bash
# Check if Flask is running:
```

1. From WSL terminal:
```bash
cd /home/swathika/IC26/docker/SHA2_innovation_challenge
python main.py  # or your Flask entry point
```

2. From emulator, use special IP for host machine:
   - Windows/Mac host → `10.0.2.2:5000`
   - Verify: Settings → About phone → Status

3. Update capacitor.config.json:
```json
"server": {
  "url": "http://10.0.2.2:5000"
}
```

Then: `npx cap sync && npx cap run android`

---

### "Build fails with Gradle error"

```bash
# Clean build
cd android
./gradlew clean
cd ..

npx cap sync
npx cap run android
```

---

### "Cannot find emulator"

```bash
# List available AVDs
$ANDROID_HOME\emulator\emulator -list-avds

# Or in Android Studio: AVD Manager → Create new emulator
```

---

### "App crashes on startup"

Check logs:
```bash
adb logcat | tail -50
```

Look for errors in console. Common issues:
- Backend unreachable
- Permission denied
- Service Worker registration failed (non-critical)

---

## 📊 Project Structure

```
SHA2_innovation_challenge/
├── package.json                    (Node.js config)
├── capacitor.config.json           (Mobile config)
├── android/                        (Android source - Capacitor generates)
│   ├── AndroidManifest.xml         (Permissions, features)
│   └── app/ ... (Gradle, Java code - auto-generated)
├── static/
│   ├── styles.css                  (Existing - desktop styles)
│   ├── mobile.css                  ✨ NEW - mobile responsive
│   ├── mobile-app.js               ✨ NEW - Capacitor integration
│   ├── service-worker.js           ✨ NEW - offline support
│   ├── index-mobile.html           ✨ NEW - mobile entry point
│   └── ... (existing assets)
├── templates/
│   ├── base.html                   ✨ UPDATED with mobile
│   └── ... (existing templates)
└── main.py                         (Unchanged - Flask backend)
```

---

## 🔄 Workflow

### Building:
```bash
# Development - sync changes to Android
npm run sync

# Test changes
npm run dev  # Opens Android Studio

# Or command line
npx cap run android
```

### Deploying:
```bash
# Create release build
cd android
./gradlew assembleRelease

# APK will be in: android/app/build/outputs/apk/release/app-release.apk
```

---

## 📱 Mobile-Specific Features

Your app now supports:

✅ **Responsive design**
- Touch-friendly buttons (44x44px minimum)
- Adaptive layouts for all screen sizes
- Safe area support (notches, status bars)

✅ **Offline support**
- Service Worker caches static assets
- Works without internet
- API calls fail gracefully

✅ **Device features**
- Camera access (for pose detection)
- Microphone (for voice)
- Permissions automatically handled

✅ **App lifecycle**
- Handles pause/resume
- Reconnects on app wake
- Saves state

---

## 🎯 Next Steps

1. **Build & Run**: Follow Android Emulator steps above
2. **Test**: Navigate through patient sessions, check camera, voice
3. **Debug**: Use `adb logcat` and Chrome DevTools (edge case)
4. **Optimize**: Adjust mobile.css for your specific needs
5. **Deploy**: Generate APK for Google Play Store

---

## 📚 Resources

- [Capacitor Docs](https://capacitorjs.com/docs)
- [Android Emulator Guide](https://developer.android.com/studio/run/emulator)
- [Capacitor Plugins](https://capacitorjs.com/docs/plugins)
- [Service Workers](https://developers.google.com/web/tools/workbox/guides/service-worker)

---

## ❓ Support

**Command reference:**

```bash
# Sync changes
npm run sync

# Open in Android Studio GUI
npm run open:android

# Run on emulator (CLI)
npx cap run android

# View logs
adb logcat

# List connected devices
adb devices

# Clear cache
npm run sync -- --force
```

---

**You're on the `mobile-app` git branch!**

Keep your original code safe on `docker-add` branch. Once tested, you can merge back or keep separate.

```bash
# View current branch
git branch

# Switch branches
git checkout docker-add     # Back to original
git checkout mobile-app     # Mobile version

# Merge when ready
git merge mobile-app        # From docker-add
```

Good luck! 🚀
