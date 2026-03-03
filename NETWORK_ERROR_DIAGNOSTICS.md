# 🔌 Network Error Troubleshooting Guide

## Error: "Network error reaching backend"

This error appears when the frontend JavaScript cannot reach the Flask backend API.

### Root Causes

| Cause | Symptoms | Solution |
|-------|----------|----------|
| **Flask not running** | Error appears immediately | Start Flask app |
| **Wrong port/URL** | Error on all API calls | Check API_BASE URL |
| **Firewall blocked** | Specific ports blocked | Check firewall rules |
| **CORS issues** | Browser console shows CORS error | Add CORS headers |
| **API endpoint issue** | 500 error in Flask logs | Check endpoint code |
| **Network timeout** | Slow response then error | Increase timeout |

---

## Quick Fixes ⚡

### 1. Verify Flask is Running

**Check if Flask is listening on port 5050:**
```bash
lsof -i :5050
```

**Expected output:**
```
COMMAND  PID  USER    FD   TYPE            DEVICE SIZE OFF NODE NAME
Python   123  user     6u  IPv4  0x...      0t0     TCP localhost:mmcc (LISTEN)
```

### 2. Start Flask (if not running)

**Option A: Direct start**
```bash
cd /Users/HariKrishnaD/Downloads/.../SHA2_innovation_challenge
python3 main.py
```

**Option B: Background with logs**
```bash
python3 main.py > /tmp/flask.log 2>&1 &
```

**Option C: With verbose output**
```bash
FLASK_DEBUG=1 FLASK_ENV=development python3 main.py
```

### 3. Test API Endpoints

**Test general pipeline:**
```bash
curl -X POST http://127.0.0.1:5050/api/session/start \
  -H "Content-Type: application/json" \
  -d '{"threshold": 30.0, "language": "English"}'
```

**Test KERAAL pipeline:**
```bash
curl -X POST http://127.0.0.1:5050/api/session/start/keraal \
  -H "Content-Type: application/json" \
  -d '{"language": "English"}'
```

**Expected response (200 OK):**
```json
{
  "status": "success",
  "message": "Session started"
}
```

### 4. Check Browser Console for Errors

1. Open browser DevTools: `Cmd + Option + I` (macOS)
2. Go to **Console** tab
3. Look for messages starting with:
   - ❌ (errors in red)
   - ⚠️ (warnings in orange)
   - 🚀 (info in blue)

**Example error:**
```
❌ pollFeedback error: TypeError: Failed to fetch
```

### 5. Check Flask Logs

**View live logs:**
```bash
tail -f /tmp/flask.log
```

**Look for these messages:**
- ✅ `[INIT] KeraalRehabPipeline initialized successfully` - KERAAL is ready
- ⚠️ `[WARNING] ... failed to initialize` - Component failed to load
- 🔴 `Error` or `Exception` - API error occurred

---

## Specific Error Solutions

### Error: "Connection refused"

**Cause**: Flask not running on port 5050

**Solution**:
```bash
# Kill any existing Flask processes
pkill -9 -f "python3 main.py"

# Start Flask again
cd /Users/HariKrishnaD/Downloads/.../SHA2_innovation_challenge
python3 main.py
```

### Error: "NET::ERR_CONNECTION_REFUSED"

**Same as above** - Flask not listening

### Error: "GET 127.0.0.1:5050 net::ERR_CONNECTION_TIMED_OUT"

**Cause**: Flask crashed or not responding

**Solution**:
```bash
# Check if still running
ps aux | grep "python3 main.py"

# If found, kill it
pkill -9 -f "python3 main.py"

# Check for port conflicts
lsof -i :5050

# Start fresh
python3 main.py
```

### Error: "CORS policy: Cross-origin request blocked"

**Cause**: CORS headers not set in Flask

**Solution**: Already handled - Flask response should include:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, GET, OPTIONS
```

### Error: "503 Service Unavailable"

**Cause**: Pipeline not initialized or failed

**Solution**:
1. Check Flask logs for pipeline initialization errors
2. Verify model files exist:
   ```bash
   ls -la Rehab_Scorer_Coach/models/keraal*.keras
   ```
3. Restart Flask

---

## Network Diagnostic Steps

### Step 1: Check Network Connectivity

**Can you reach the Flask server?**
```bash
curl -v http://127.0.0.1:5050/
```

**Expected**: Should return HTML (200 OK) or redirect

### Step 2: Check Specific Endpoints

**General pipeline start:**
```bash
curl -X POST http://127.0.0.1:5050/api/session/start \
  -H "Content-Type: application/json" \
  -d '{"threshold": 30.0, "language": "English"}' \
  -w "\nHTTP Status: %{http_code}\n"
```

**KERAAL pipeline start:**
```bash
curl -X POST http://127.0.0.1:5050/api/session/start/keraal \
  -H "Content-Type: application/json" \
  -d '{"language": "English"}' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Feedback endpoint (general):**
```bash
curl -X POST http://127.0.0.1:5050/api/live_feedback \
  -H "Content-Type: application/json" \
  -d '{
    "frame_b64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "language": "English",
    "mode": "auto"
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Feedback endpoint (KERAAL):**
```bash
curl -X POST http://127.0.0.1:5050/api/live_feedback_keraal \
  -H "Content-Type: application/json" \
  -d '{
    "frame_b64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "language": "English"
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

### Step 3: Check Frontend Configuration

**Verify API_BASE is correct:**
1. Open browser console
2. Type: `console.log(API_BASE)`
3. Should show: `http://127.0.0.1:5050` or your domain

**Verify pipeline type:**
1. Type: `console.log(selectedPipelineType)`
2. Should show: `general` or `keraal`

### Step 4: Monitor Network Activity

1. Open DevTools: `Cmd + Option + I`
2. Go to **Network** tab
3. Perform action (e.g., click "Start Session")
4. Look for failed requests (red text)
5. Click on request to see:
   - **Status**: 200 (OK), 404 (not found), 500 (server error), etc.
   - **Response**: JSON response from server
   - **Headers**: Request/response headers

---

## Full Debugging Workflow

### Scenario: KERAAL pipeline showing "Network error"

**Step 1: Stop Flask and view startup logs**
```bash
pkill -9 -f "python3 main.py"
sleep 2
cd /Users/HariKrishnaD/Downloads/.../SHA2_innovation_challenge
python3 main.py 2>&1 | head -50
```

**Check for:**
- ✅ `✅ KERAAL Models Ready` - Models loaded
- ✅ `[INIT] KeraalRehabPipeline initialized successfully` - Pipeline ready
- ⚠️ `[WARNING] ... failed to initialize` - Problem detected

**Step 2: If models not found**
```bash
# Check model files exist
ls -la Rehab_Scorer_Coach/models/keraal*.keras

# Verify file paths
file Rehab_Scorer_Coach/models/keraal_exercise_detection.keras
file Rehab_Scorer_Coach/models/keraal_model_v1.keras
```

**Step 3: Test endpoint directly**
```bash
# While Flask is running in another terminal:
curl -X POST http://127.0.0.1:5050/api/session/start/keraal \
  -H "Content-Type: application/json" \
  -d '{"language": "English"}'
```

**Step 4: Check Flask logs for errors**
```bash
# Terminal where Flask is running - look for error messages
# Or check the log file if running in background
tail -100 /tmp/flask.log | grep -i "error\|exception\|warn"
```

**Step 5: Check browser console**
1. Open browser to: `http://127.0.0.1:5050/patient/session`
2. Click "Start Session"
3. Select "Low Back Pain"
4. Open DevTools (Cmd + Option + I)
5. Look for network errors in Console and Network tabs

---

## Recovery Commands

### Restart Everything

```bash
# Kill all Flask processes
pkill -9 -f "python3 main.py"

# Wait
sleep 2

# Start fresh
cd /Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge

# Option 1: Direct start (see logs in terminal)
python3 main.py

# Option 2: Background start (logs go to file)
python3 main.py > /tmp/flask.log 2>&1 &

# Verify it's running
lsof -i :5050
sleep 2
curl -s http://127.0.0.1:5050/ | head -20
```

### Clear Browser Cache

If frontend is cached:
1. **Hard refresh**: Cmd + Shift + R
2. **DevTools → Network → Disable cache**
3. **DevTools → Storage → Clear All**

### Reset Entire System

```bash
# Kill Flask
pkill -9 -f "python3 main.py"

# Clear logs
rm -f /tmp/flask.log

# Clear browser cache (in browser)
# Use Cmd + Shift + Delete

# Start fresh
python3 main.py
```

---

## Common Test Flow

1. **Start Flask**
   ```bash
   python3 main.py
   ```

2. **Open browser to session page**
   ```
   http://127.0.0.1:5050/patient/session
   ```

3. **Click "Start Session"**
   - Should show modal with two options

4. **Select "Low Back Pain"**
   - Modal closes
   - Session initializes
   - Video should start

5. **Look for feedback**
   - Should see form status (CORRECT/INCORRECT)
   - Should see rep counter updating
   - Should see feedback text

6. **If error appears**
   - Check DevTools Console (Cmd + Option + I)
   - Check Network tab for failed requests
   - Check Flask terminal for error messages
   - Compare against troubleshooting guide above

---

## Performance Monitoring

### Check Response Times

**In browser console:**
```javascript
// Measure API response time
performance.mark('api-start');
await fetch('/api/live_feedback_keraal', {...});
performance.mark('api-end');
console.log(performance.measure('api-call', 'api-start', 'api-end'));
```

**Expected times:**
- `/api/session/start/*`: < 200ms
- `/api/live_feedback*`: 30-50ms (KERAAL) or 50-100ms (general)
- `/api/session/stop/*`: < 100ms

### Monitor Network Activity

**Check in DevTools Network tab:**
- **Size**: Frame size (usually 10-50KB)
- **Time**: Response time (see above)
- **Status**: Should always be 200 OK

---

## Still Having Issues?

### Collect Debug Information

```bash
# Flask startup output
python3 main.py 2>&1 | tee /tmp/flask_startup.log

# Wait, then collect logs
# (Ctrl+C after app starts)

# Package debug info
mkdir -p /tmp/debug
cp /tmp/flask_startup.log /tmp/debug/
cp /tmp/flask.log /tmp/debug/ 2>/dev/null || true
lsof -i :5050 > /tmp/debug/network.txt
ps aux | grep python > /tmp/debug/processes.txt
ls -la Rehab_Scorer_Coach/models/keraal* > /tmp/debug/models.txt

# View collected info
cat /tmp/debug/*
```

### Key Files to Check

| File | Purpose |
|------|---------|
| `main.py` | Flask app entry point |
| `Rehab_Scorer_Coach/src/keraal_pipeline.py` | KERAAL backend logic |
| `templates/patient/session.html` | Frontend session page |
| `static/session_manager.js` | Frontend JS session manager |

---

## Status Checklist

Before testing, verify:

- [ ] Flask is running: `lsof -i :5050` shows Python process
- [ ] Port 5050 is available: No other process using it
- [ ] KERAAL models exist: `ls -la Rehab_Scorer_Coach/models/keraal*.keras`
- [ ] Backend endpoints exist: `grep -n "api/live_feedback_keraal" main.py`
- [ ] Browser at correct URL: `http://127.0.0.1:5050`
- [ ] API_BASE correct: DevTools console shows correct URL
- [ ] DevTools Network tab shows requests
- [ ] Response status codes are 200 or 201

---

**Last Updated**: February 23, 2026  
**Status**: ✅ Ready  
**Severity**: Low (easily recoverable)
