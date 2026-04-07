# Android Emulator Testing Guide

## 🎯 Getting the Emulator Ready

### Step 1: Install Android Studio

1. Download from [developer.android.com/studio](https://developer.android.com/studio)
2. Run installer
3. Follow setup wizard
4. Choose Android API Level 30 or higher

### Step 2: Create a Virtual Device (Emulator)

In Android Studio:

1. **Tools** → **Device Manager**
2. Click **Create Device**
3. Select device type (Pixel 4 or Pixel 5 recommended)
4. Select API Level (Level 30, 31, or 34)
5. Click **Next** → **Finish**

You now have an emulator ready to use!

---

## 📱 Running Your SHA2 App

### Method 1: Android Studio GUI (Easiest)

```bash
# Make sure Flask backend is running first!
# Then in your project folder:

npx cap open android
```

This opens Android Studio with your project. Then:

1. Click **Run** ▶️ button (top toolbar)
2. Select your emulator
3. Wait 1-2 minutes for build & install
4. App launches automatically!

### Method 2: Command Line

```bash
# 1. Make sure Flask backend is running

# 2. Start the emulator
emulator -avd Pixel_4_API_30 &

# 3. Wait for emulator to fully boot (watch for home screen)

# 4. Build and run app
npx cap run android

# 5. Watch logs
adb logcat | grep -i "SHA2\|error\|MobileApp"
```

---

## ✅ Testing Checklist

### 1. App Launch
- [ ] App appears after 30 seconds
- [ ] No immediate errors in console
- [ ] Background animation visible

### 2. Navigation
- [ ] Dashboard loads
- [ ] Can click buttons without lag
- [ ] Can navigate between tabs

### 3. Video/Camera
- [ ] Camera permission prompt appears
- [ ] Grant permission
- [ ] Camera video displays
- [ ] Pose detection skeleton visible

### 4. Voice/Audio
- [ ] Microphone permission prompt
- [ ] Can record and play back
- [ ] No audio crackling

### 5. API Calls
- [ ] Login/authentication works
- [ ] Can fetch patient data
- [ ] Chat appears without 30+ second delay

### 6. UI Responsiveness (Mobile)
- [ ] Buttons are large (easy to tap)
- [ ] Text is readable without zooming
- [ ] Video fills width properly
- [ ] No UI elements cut off

### 7. Offline Mode
- [ ] Disconnect internet: Emulator Tools → Uncheck "Connected"
- [ ] App shows "No connection" banner
- [ ] Can still see cached pages
- [ ] API calls fail gracefully

---

## 🐛 Debugging

### View Real-time Logs

```bash
# All logs
adb logcat

# Filter by your app
adb logcat | grep SHA2

# Filter by errors
adb logcat | grep ERROR

# Clear previous logs before testing
adb logcat -c
```

### Common Log Messages

```
[MobileApp] Initializing...          ← Mobile app starting
[MobileApp] Running in Capacitor    ← Capacitor detected
[MobileApp] Service Worker registered  ← Offline ready
Backend connection OK                ← Connected to Flask
```

### Chrome DevTools (Advanced)

```bash
# Enable debugging in Chrome
# 1. On Android device/emulator: Developer options → USB Debugging → On
# 2. On computer: chrome://inspect
# 3. Find your app and click "Inspect"
# 4. Full DevTools console appears!
```

---

## 📍 Connecting to Your Backend

### Getting the Right IP

**From inside emulator:**

Android emulator special IPs:
- `10.0.2.2` = Your computer's localhost
- `10.0.2.1` = Emulator gateway

So if Flask runs on:
- `localhost:5000` → Use `10.0.2.2:5000`
- `192.168.1.100:5000` → Use same IP

### Update Configuration

Edit `capacitor.config.json`:

```json
{
  "server": {
    "url": "http://10.0.2.2:5000",
    "androidScheme": "http",
    "cleartext": true
  }
}
```

Then rebuild:
```bash
npx cap sync
npx cap run android
```

### Verify Connection

In emulator:
1. **Settings** → **About phone** → **IP address**
2. Try to ping: `ping 10.0.2.2` (should succeed)

---

## 🎥 Recording Tests

### Take Screenshots

```bash
# Screenshots automatically go to /Pictures on your computer
adb exec-out screencap -p > screenshot.png
```

### Record Video of App

```bash
# Record 3 minutes
adb shell screenrecord --time-limit 180 /sdcard/video.mp4

# Pull to computer
adb pull /sdcard/video.mp4
```

---

## 💾 Common Emulator Tasks

### Clear App Data (Fresh Start)

```bash
adb shell pm clear com.sha2.rehabcoach
```

### Restart Emulator

```bash
# Stop
adb emu kill

# Start fresh
emulator -avd Pixel_4_API_30
```

### Check Disk Space

```bash
adb shell "df -H"
```

### Install Debug APK

```bash
adb install app-debug.apk
```

---

## ⚡ Performance Tips

### Speed Up Emulator

1. **Use API 30+** (faster than older APIs)
2. **4+ GB RAM** allocated to emulator
3. **VT-x/AMD-V** enabled in BIOS (Windows)
4. **SSD** for Android SDK folder (not USB drive)

### Reduce Build Time

```bash
# Skip unnecessary resources
export GRADLE_OPTS="-Xmx2048m -XX:MaxPermSize=512m"

# Incremental build (only changed files)
npx cap sync --incremental
```

---

## ❓ Troubleshooting

### "Device offline or not responding"

```bash
# Restart ADB
adb kill-server
adb start-server

# Reconnect
npx cap run android
```

### "App crashes on startup"

Check logs:
```bash
adb logcat | tail -50
```

Common fixes:
- Backend unreachable (check IP)
- Missing permissions (check AndroidManifest.xml)
- Service Worker error (check browser console)

### "Emulator won't start"

```bash
# List existing emulators
emulator -list-avds

# Delete and recreate
emulator -avd <name> -wipe-data

# Start with more RAM
emulator -avd <name> -memory 4096
```

### "Cannot connect to backend"

1. Verify Flask is running: `curl http://localhost:5000/`
2. Get emulator IP: `adb shell getprop ro.kernel.android.qemud`
3. Use `10.0.2.2` for localhost instead of `localhost`

---

## 🔗 Resources

- [Android Emulator Docs](https://developer.android.com/studio/run/emulator)
- [ADB Commands](https://developer.android.com/studio/command-line/adb)
- [Android Performance](https://developer.android.com/studio/profile)

---

## 📝 Testing Template

Use this for each test session:

```
Date: ____________
Tester: __________
API Level: _______
Device: __________

Tests Passed:
- [ ] App launches
- [ ] Camera works
- [ ] Backend connects
- [ ] Video responsive
- [ ] Offline mode

Issues Found:
1. ________________
2. ________________

Notes:
________________
________________
```

---

Good luck testing! 🚀
