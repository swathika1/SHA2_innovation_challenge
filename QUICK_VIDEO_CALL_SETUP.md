# Video Call Multi-Device Setup - Quick Commands

## 🚀 Quick Start (Copy & Paste)

### Step 1: Find Your Local IP
```powershell
# Windows PowerShell
ipconfig
# Look for IPv4 Address like: 192.168.1.100
```

### Step 2: Enable Firewall (Windows - Run as Administrator)
```powershell
netsh advfirewall firewall add rule name="Allow Flask Port 8000" dir=in action=allow protocol=tcp localport=8000
```

### Step 3: Start Flask Server
```bash
cd path/to/SHA2_innovation_challenge
python main.py
```

### Step 4: Access from Another Laptop
```
Open browser: http://192.168.1.100:8000
(Replace 192.168.1.100 with YOUR local IP from Step 1)
```

---

## 🧪 Test Network Configuration

```bash
# Run network diagnostic
python test_video_call_network.py
```

Should show:
- ✅ Flask is listening on port 8000
- ✅ Port is responding to HTTP requests
- ✅ Firewall allows port 8000
- ✅ All API endpoints working

---

## 📞 Video Call Test Workflow

### Machine A (Doctor/Clinician):
```bash
# 1. Start Flask
python main.py

# 2. Open browser
# http://192.168.1.100:8000
# Login as doctor

# 3. Schedule appointment
Consultations > Book Patient > Set Date/Time

# 4. Join video call (after scheduled time)
Appointments > Click "Join Video Call"
```

### Machine B (Patient):
```bash
# 1. Open browser on different laptop
# http://192.168.1.100:8000
# (Use same IP as Machine A)

# 2. Login as patient

# 3. Find upcoming appointment
Appointments > Check upcoming list

# 4. Join video call at scheduled time
Appointments > Click "Join Video Call"
```

---

## 🛠️ Troubleshooting Commands

### Check if Flask is Running
```powershell
# Windows
netstat -ano | findstr :8000

# Mac/Linux
lsof -i :8000
```

### Test Network Connectivity
```bash
# Ping the other machine
ping 192.168.1.100

# Test Flask health endpoint
curl http://192.168.1.100:8000/health
```

### Check Firewall Rules (Windows)
```powershell
# Show firewall rules for port 8000
netsh advfirewall firewall show rule name="Allow Flask Port 8000"

# Remove rule if needed
netsh advfirewall firewall delete rule name="Allow Flask Port 8000"

# Re-create rule
netsh advfirewall firewall add rule name="Allow Flask Port 8000" dir=in action=allow protocol=tcp localport=8000
```

### View Flask Debug Logs
```bash
# Start Flask with debug output
python main.py

# You should see:
# WARNING: This is a development server. Do not use it in production.
# Running on http://0.0.0.0:8000
```

---

## ⚠️ Common Issues & Fixes

### Issue: "Connection refused" or "Can't reach server"
```bash
# Fix 1: Verify Flask is listening
netstat -ano | findstr :8000

# Fix 2: Check firewall
netsh advfirewall firewall show rule name="Allow Flask Port 8000"

# Fix 3: Restart Flask server
# Kill process and restart: python main.py
```

### Issue: "localhost works but IP doesn't"
```bash
# DO NOT use: http://localhost:8000
# DO use: http://192.168.1.100:8000

# Verify you're using the correct IP
ipconfig | findstr IPv4
```

### Issue: "CORS errors in browser console"
```javascript
// This means Flask can't respond to cross-origin requests
// Solution: Already fixed in main.py with CORS configuration
// Try restarting Flask: Ctrl+C then python main.py
```

### Issue: "Video/Audio not working"
```bash
# 1. Check browser permissions
# Chrome/Firefox > Settings > Privacy > Camera/Microphone > Allow

# 2. Test camera works
# Open https://www.google.com/chrome/demos/camera.html

# 3. Zoom test meeting works
# https://zoom.us/test/connection

# If Zoom works but app doesn't, it's a browser/permission issue
```

---

## 📊 Verification Checklist

Run these commands to verify setup:

```bash
# 1. Check Flask is running
netstat -ano | findstr :8000
# Expected: Shows a listening port on :8000

# 2. Test Flask endpoint
curl http://127.0.0.1:8000/health
# Expected: {"status": "ok"}

# 3. Get your local IP
ipconfig
# Expected: Shows IPv4 Address like 192.168.1.100

# 4. Test from another machine
curl http://192.168.1.100:8000/health
# Expected: {"status": "ok"}

# 5. Test session endpoint (needs login)
curl -X POST http://192.168.1.100:8000/api/current-user
# Expected: Should return JSON with user info or 401
```

---

## 📝 Network Setup Reference

### Flask Server (Machine A):
```
Local IP: 192.168.1.100  (example, use your IP)
Port: 8000
URL: http://192.168.1.100:8000
Status: Listening on 0.0.0.0:8000
```

### Client (Machine B):
```
Access: http://192.168.1.100:8000  (same as Machine A)
NOT: http://localhost:8000         (Won't work!)
NOT: http://127.0.0.1:8000         (Won't work!)
```

### Jitsi Conference:
```
Server: meet.ffmuc.net
Room: rehab-call-{appointment_id}
Max Participants: 100
Type: Public/Free
```

---

## 🔧 Advanced: Manual Flask Configuration

If needed, you can modify Flask host/port in `main.py`:

```python
# Current (Flask listens on all interfaces):
app.run(host="0.0.0.0", port=8000)

# Restrict to localhost only (NOT recommended for multi-device):
app.run(host="127.0.0.1", port=8000)

# Custom port:
app.run(host="0.0.0.0", port=9000)
```

---

## 📖 Full Documentation

For complete details, see:
- `VIDEO_CALL_FIX_SUMMARY.md` - Overview of changes
- `VIDEO_CALL_MULTIDEVICE.md` - Full setup guide
- `DOCKER_SETUP.md` - Docker containerization guide

---

**Quick Test Command:**
```bash
python test_video_call_network.py
```

This will run all checks and show you exactly what's configured correctly and what needs fixing.

---

Last Updated: March 15, 2026
Status: ✅ Ready for multi-device video calling
