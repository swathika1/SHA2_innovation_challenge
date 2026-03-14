# Video Call Multi-Laptop Troubleshooting Guide

## The Problem
- ✅ Works: 2 browsers on same laptop (both use `localhost`)
- ❌ Doesn't work: Different laptops on local network (can't access `localhost` from another machine)

## Solution: Use Local IP Address Instead

### Step 1: Find Your Machine's Local IP

**On Windows (where Flask is running):**
```powershell
# Open PowerShell and run:
ipconfig

# Look for IPv4 Address under your network adapter, e.g.:
# 192.168.1.100
# 10.0.0.50
# etc.
```

**On Mac/Linux (where Flask is running):**
```bash
ifconfig
# Look for inet address like 192.168.x.x
```

### Step 2: Access from Another Laptop

Instead of:
```
http://localhost:8000
```

Use:
```
http://192.168.1.100:8000  # Use YOUR local IP address
http://[your-ip]:8000
```

### Step 3: Ensure Firewall Allows Port 8000

**Windows Firewall:**
```powershell
# PowerShell as Administrator
netsh advfirewall firewall add rule name="Allow Flask Port 8000" dir=in action=allow protocol=tcp localport=8000
```

**Mac:**
```bash
# System Preferences > Security & Privacy > Firewall Options
# Add Flask to allowed apps
```

**Linux:**
```bash
sudo ufw allow 8000
```

### Step 4: Verify Network Connectivity

From the other laptop, test connectivity:
```bash
# Windows/Mac/Linux
ping 192.168.1.100  # Replace with your IP

# Or try accessing Flask directly
curl http://192.168.1.100:8000/
```

## Full Video Call Test Across Laptops

1. **Laptop A (Doctor):** Start Flask app
   ```bash
   python main.py
   # Find the local IP: xxx.xxx.xxx.xxx
   ```

2. **Laptop A:** Access at `http://192.168.1.100:8000` (use your IP)
   - Login as Doctor
   - Schedule a video call with a patient
   - Copy the appointment link

3. **Laptop B (Patient):** Access Flask from the other laptop
   ```
   http://192.168.1.100:8000  # Same IP as Laptop A
   ```
   - Login as Patient
   - Join the video call from the appointment

4. **Test the video call:**
   - Should see each other in Jitsi Meet
   - Audio/video should work
   - Both should appear as "participants"

## Common Issues & Fixes

### Issue: "Connection refused" or "Can't reach the server"
**Fix:** Check if Flask is running on `0.0.0.0`
```python
# In main.py, should be:
app.run(host="0.0.0.0", port=8000, debug=True)
# NOT: app.run(host="localhost", port=8000)
```

### Issue: Page loads but video call doesn't connect
**Possible Causes:**
- Firewall blocking port 8000
- Both users in wrong room ID
- Network connectivity issue

**Fix:**
```bash
# Check if port is listening
netstat -an | grep 8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows
```

### Issue: CORS errors in browser console
**Error:** "Access to XMLHttpRequest blocked by CORS policy"

**Fix Applied:** CORS is now enabled in Flask for cross-machine requests

## Technical Details

### Room ID Generation
The room ID for Jitsi is generated in `main.py`:
```python
room_id = appointment['room_id'] if appointment['room_id'] else f"rehab-call-{appointment_id}"
```

Both users must have the SAME appointment ID to join the same room.

### Jitsi Configuration
The application uses `meet.ffmuc.net` which is a public Jitsi instance.
- No server setup needed
- Works across different networks  
- Supports up to 100 participants per room
- Free and open-source

## Network Requirements

✅ Both laptops must be on the same network (WiFi/LAN)
✅ Direct internet access for Jitsi Meet (meet.ffmuc.net)
❌ VPN might interfere - try disabling first

## WSL / Docker Note

If running Flask in WSL:
```bash
# Get your WSL IP
wsl hostname -I

# Use that IP to access from other laptops
http://[wsl-ip]:8000
```

## Testing Checklist

- [ ] Find local IP of Flask machine
- [ ] Access Flask from another laptop using IP (not localhost)
- [ ] Firewall allows port 8000
- [ ] Both laptops can ping each other
- [ ] Schedule appointment from one laptop
- [ ] Join call from other laptop
- [ ] See participant in Jitsi Meet
- [ ] Audio/Video working both ways
