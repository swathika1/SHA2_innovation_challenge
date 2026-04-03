# Mobile App Quick Reference

## 🚀 TL;DR - Get Started in 3 Steps

### Step 1: Install Dependencies
```bash
cd \\wsl.localhost\Ubuntu\home\swathika\IC26\docker\SHA2_innovation_challenge

# Windows (in PowerShell as Admin):
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
npm install

# macOS/Linux:
npm install
```

### Step 2: Start Your Backend
```bash
# In another terminal
python main.py
```

### Step 3: Run on Emulator
```bash
# First time
npm run dev         # Opens Android Studio
# Click Run ▶️ → Select Emulator → Wait 1-2 min

# Subsequent times
npx cap run android
```

---

## 📱 One-Liner Commands

| Task | Command |
|------|---------|
| **Install** | `npm install` |
| **Sync changes** | `npm run sync` |
| **Open Android Studio** | `npm run open:android` |
| **Run on emulator** | `npx cap run android` |
| **View logs** | `adb logcat \| grep SHA2` |
| **List emulators** | `emulator -list-avds` |
| **Start emulator** | `emulator -avd Pixel_4_API_30` |
| **Take screenshot** | `adb exec-out screencap -p > screen.png` |
| **Clear app cache** | `adb shell pm clear com.sha2.rehabcoach` |

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `package.json` | Node.js config for Capacitor |
| `capacitor.config.json` | Mobile app settings & backend URL |
| `android/` | Auto-generated Android project |
| `static/mobile.css` | ✨ Responsive mobile styles |
| `static/mobile-app.js` | ✨ Capacitor integration |
| `static/service-worker.js` | ✨ Offline caching |
| `templates/base.html` | Updated with mobile support |

---

## 🧪 Testing Checklist

```
[ ] App launches without crashing
[ ] Backend connection works (no "No connection" banner)
[ ] Camera permission dialog appears
[ ] Video displays without lag
[ ] Buttons are large & responsive
[ ] Text readable without zooming
[ ] Offline mode shows banner
[ ] Can navigate between screens
```

---

## 🆘 Common Issues

### "Cannot connect to backend"
```
→ Make sure Flask is running
→ Use 10.0.2.2 in capacitor.config.json (not localhost)
→ npx cap sync && npx cap run android
```

### "Build fails"
```
→ npx cap sync --force
→ cd android && ./gradlew clean && cd ..
→ npx cap run android
```

### "Emulator won't start"
```
→ emulator -list-avds
→ emulator -avd Pixel_4_API_30 &
→ Wait 2-3 min for boot
```

### "Permissions not working"
```
→ Check android/AndroidManifest.xml
→ adb shell pm list permissions
→ npx cap sync && npx cap run android
```

---

## 📂 Branch Management

```bash
# You're currently on:
git branch
# Output: * mobile-app

# View all branches
git branch -a

# Switch to original code
git checkout docker-add

# Switch back to mobile
git checkout mobile-app

# Merge mobile into main branch (when ready)
git checkout docker-add
git merge mobile-app
```

---

## 🎯 Workflow

### Daily Development
```bash
# 1. Make changes to code/CSS
# 2. Sync to Android
npm run sync

# 3. Run on emulator
npx cap run android

# 4. Test in app
# 5. Repeat
```

### Before Commit
```bash
git status
git add .
git commit -m "Describe changes"
```

### Release
```bash
# Build for Google Play
cd android
./gradlew assembleRelease

# APK location:
# android/app/build/outputs/apk/release/app-release.apk
```

---

## 📞 Support Resources

| Need | Link |
|------|------|
| **Capacitor Docs** | https://capacitorjs.com/docs |
| **Android Studio** | https://developer.android.com/studio |
| **ADB Commands** | https://developer.android.com/studio/command-line/adb |
| **Android Emulator** | https://developer.android.com/studio/run/emulator |

---

## ✨ What's New

✅ Responsive mobile design (all screen sizes)
✅ Touch-friendly buttons & controls  
✅ Offline support with Service Worker
✅ Camera & microphone permissions
✅ Device features integration
✅ Proper safe area handling (notches)
✅ Mobile navigation & layout
✅ Device orientation support

---

**Current Branch**: `mobile-app` (git branch)
**Original Code**: Safe on `docker-add` branch
**Status**: Ready to test on emulator! 🚀

For detailed setup: See `MOBILE_APP_SETUP.md`
For emulator testing: See `EMULATOR_TESTING_GUIDE.md`
