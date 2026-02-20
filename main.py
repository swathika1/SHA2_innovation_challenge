import os
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TF"] = "0"

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from Rehab_Scorer_Coach.src.web_pipeline import WebRehabPipeline
from flask_cors import CORS # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
import uuid
try:
    from optim import get_top3_recommendations, optimize_all_patients, build_demo_data, load_dataset
    OPTIM_AVAILABLE = True
    print("[INIT] Optimization module loaded successfully")
except Exception as e:
    OPTIM_AVAILABLE = False
    print(f"[WARNING] Optimization module not available: {e}")

try:
    from merilion_client import query_merilion_sync
    from risk_engine import calculate_risk_score, REFERRAL_MESSAGES
    from exercise_advisor import get_exercise_modification
    from langdetect import detect as detect_language
    import traceback
    CHATBOT_AVAILABLE = True
    print("[INIT] Chatbot modules loaded successfully")
except Exception as e:
    CHATBOT_AVAILABLE = False
    print(f"[WARNING] Chatbot modules not available: {e}")

# main.py (top-level)
import os
import sys
import time
import socket
import subprocess
from pathlib import Path
import subprocess, sys, os, time, requests
import hashlib
import tempfile
import os
import asyncio
import edge_tts


OPENPOSE_PORT = 9001
OPENPOSE_URL = f"http://127.0.0.1:{OPENPOSE_PORT}"
OPENPOSE_LOG = Path(__file__).resolve().parent / "openpose_server.log"
OPENPOSE_PROC = None

def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_openpose_server():
    host = "127.0.0.1"
    port = 9001
    url = f"http://{host}:{port}/health"

    # If already running, do nothing
    try:
        r = requests.get(url, timeout=1.0)
        if r.status_code == 200:
            print("[OPENPOSE] already running")
            return
    except Exception:
        pass

    log_path = Path(__file__).resolve().parent / "openpose_server.log"
    server_py = Path(__file__).resolve().parent / "openpose_http_server.py"

    if not server_py.exists():
        raise RuntimeError(f"openpose_http_server.py not found at {server_py}")

    print("[OPENPOSE] starting server...")

    with open(log_path, "w") as f:
        subprocess.Popen(
            [sys.executable, str(server_py)],
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parent),
        )

    # Wait until server becomes healthy
    timeout = 20  # seconds
    start = time.time()

    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                print("[OPENPOSE] ready")
                return
        except Exception:
            pass
        time.sleep(0.5)

    raise RuntimeError(f"OpenPose server not healthy. Check {log_path}")
#from Rehab_Scorer_Coach.src.meralion_client import MeralionClient

#MERALION_API_KEY = os.environ.get("MERALION_API_KEY", "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE")
#MERALION = MeralionClient(MERALION_API_KEY) if MERALION_API_KEY else None

# Create instance folder if it doesn't exist
os.makedirs('instance', exist_ok=True)

from database import close_db, query_db, execute_db, load_optimization_data

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Required for sessions

# Register database cleanup function
app.teardown_appcontext(close_db)


@app.context_processor
def inject_user():
    """Make 'user' available in all templates when logged in."""
    user = None
    if 'user_id' in session:
        user = query_db(
            'SELECT id, name, email, role, phone, pincode, dob, created_at FROM users WHERE id = ?',
            (session['user_id'],), one=True
        )
    return dict(user=user)


# ==================== AUTHENTICATION HELPERS ====================

def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """Decorator to restrict routes to specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
            if session.get('role') != role:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('landing'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user():
    """Get the currently logged-in user from database."""
    if 'user_id' in session:
        return query_db('SELECT * FROM users WHERE id = ?', (session['user_id'],), one=True)
    return None

VOICE_MAP = {
    "English": "en-US-JennyNeural",
    "Tamil":   "ta-IN-ValluvarNeural",
    "Chinese": "zh-CN-XiaoxiaoNeural",
    "Malay":   "ms-MY-YasminNeural",
    "Thai":    "th-TH-PremwadeeNeural",
}

def _tts_cache_path(text: str, language: str) -> str:
    h = hashlib.md5(f"{language}|{text}".encode("utf-8")).hexdigest()
    cache_dir = os.path.join(tempfile.gettempdir(), "rehab_tts_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{h}.mp3")

async def _synth_to_file(text: str, voice: str, out_path: str):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)

@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(force=True) or {}

    text = (data.get("text") or "").strip()
    language = (data.get("language") or "English").strip()

    if isinstance(text, list):
        text = ". ".join(text)

    if not text:
        return jsonify({"error": "text is required"}), 400

    voice = VOICE_MAP.get(language, VOICE_MAP["English"])
    out_path = _tts_cache_path(text, language)

    try:
        if not os.path.exists(out_path):
            print("🔊 Generating new TTS file")

            # SAFE asyncio call inside Flask
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_synth_to_file(text, voice, out_path))
            loop.close()

        else:
            print("♻️ Using cached TTS")

        return send_file(out_path, mimetype="audio/mpeg", as_attachment=False)

    except Exception as e:
        print("❌ TTS ERROR:", e)
        return jsonify({"error": f"TTS failed: {type(e).__name__}: {e}"}), 500

@app.get("/health")
def health():
    return {"status": "ok"}


# ==================== AUTH ROUTES ====================

@app.route('/')
def landing():
    """Landing Page"""
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login Page"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Find user by email
        user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)
        
        if user:
            password_match = check_password_hash(user['password'], password)
            
            if password_match:
                # Login successful - store user info in session
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user['role']
                session.permanent = True  # Make session persistent
                
                # Log login to login_history table
                execute_db(
                    'INSERT INTO login_history (user_id, name, email, role) VALUES (?, ?, ?, ?)',
                    (user['id'], user['name'], user['email'], user['role'])
                )
                
                flash(f'Welcome back, {user["name"]}!', 'success')
                
                # Redirect based on role
                if user['role'] == 'doctor':
                    return redirect(url_for('clinician_dashboard'))
                elif user['role'] == 'patient':
                    return redirect(url_for('patient_dashboard'))
                elif user['role'] == 'caregiver':
                    return redirect(url_for('caregiver_dashboard'))
        
        flash('Invalid email or password.', 'error')
    
    return render_template('login.html')


# API Login endpoint (for computer_vision branch compatibility)
@app.route('/api/login', methods=['POST'])
def api_login():
    """API Login endpoint"""
    data = request.get_json()
    email = data.get('email_id') or data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400
    
    user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)
    
    if not user:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    # Check password (support both hashed and plain text for compatibility)
    password_match = False
    try:
        password_match = check_password_hash(user['password'], password)
    except:
        password_match = (user['password'] == password)
    
    if not password_match:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    # Store in session
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['role'] = user['role']
    
    # Log login to login_history table
    execute_db(
        'INSERT INTO login_history (user_id, name, email, role) VALUES (?, ?, ?, ?)',
        (user['id'], user['name'], user['email'], user['role'])
    )
    
    # Map role names for compatibility
    role_map = {'doctor': 'clinician', 'patient': 'patient', 'caregiver': 'caregiver'}
    
    return jsonify({
        'success': True,
        'role': role_map.get(user['role'], user['role']),
        'name': user['name'],
        'user_id': user['id']
    }), 200


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API Logout endpoint"""
    session.clear()
    return jsonify({'success': True}), 200

old_code = """
@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "en").strip()

    if not text:
        return jsonify({"error": "text missing"}), 400

    # Map your UI language names to Google TTS codes
    lang_map = {
        "English": "en",
        "Tamil": "ta",
        "Chinese": "zh-CN",
        "Malay": "ms",
        "Thai": "th",
    }
    glang = lang_map.get(lang, "en")

    # Google translate TTS endpoint
    q = urllib.parse.quote(text)
    url = (
        "https://translate.google.com/translate_tts"
        f"?ie=UTF-8&client=tw-ob&tl={glang}&q={q}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0"  # needed or Google blocks
    }

    r = requests.get(url, headers=headers, timeout=15)
    if not r.ok:
        return jsonify({"error": f"TTS failed HTTP {r.status_code}: {r.text[:200]}"}), 500

    # Return MP3 bytes
    return send_file(
        io.BytesIO(r.content),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="tts.mp3",
    )
"""

@app.route('/api/current-user', methods=['GET'])
def api_current_user():
    """Get current logged-in user information"""
    if 'user_id' in session:
        user = get_current_user()
        if user:
            return jsonify({
                'authenticated': True,
                'user_id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }), 200
    return jsonify({'authenticated': False}), 401


@app.route('/api/postal/search')
def postal_search():
    """Search SG postal codes for autocomplete"""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    results = query_db(
        'SELECT DISTINCT postal_code, street_name FROM sg_postal WHERE postal_code LIKE ? LIMIT 20',
        (f'{q}%',)
    )
    return jsonify([{'postal_code': r['postal_code'], 'street_name': r['street_name']} for r in results] if results else [])


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup Page"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        name = f"{first_name} {last_name}".strip() or request.form.get('name', 'User')
        role = request.form['role']
        phone = request.form.get('phone', '').strip() or None
        pincode = request.form.get('pincode', '').strip() or None
        dob = request.form.get('dob', '').strip() or None
        
        # Validate pincode against sg_postal table (if provided)
        if pincode:
            valid_postal = query_db(
                'SELECT postal_code FROM sg_postal WHERE postal_code = ? LIMIT 1',
                (pincode,), one=True
            )
            if not valid_postal:
                flash('Invalid postal code. Please choose a valid Singapore postal code from the suggestions.', 'error')
                return redirect(url_for('signup'))

        # For doctors, also validate clinic pincode
        clinic_pincode = request.form.get('clinic_pincode', '').strip()
        if role == 'doctor' and clinic_pincode:
            valid_clinic = query_db(
                'SELECT postal_code FROM sg_postal WHERE postal_code = ? LIMIT 1',
                (clinic_pincode,), one=True
            )
            if not valid_clinic:
                flash('Invalid clinic postal code. Please choose a valid Singapore postal code from the suggestions.', 'error')
                return redirect(url_for('signup'))

        # Check if email already exists
        existing_user = query_db('SELECT id FROM users WHERE email = ?', (email,), one=True)
        if existing_user:
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('login'))
        
        # Hash password and create user
        hashed_password = generate_password_hash(password)
        user_id = execute_db(
            'INSERT INTO users (email, password, name, role, phone, pincode, dob) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (email, hashed_password, name, role, phone, pincode, dob)
        )
        
        # If patient, create patients record with optimization data
        if role == 'patient':
            condition = request.form.get('condition', 'General Rehab')
            urgency = request.form.get('urgency', 'Medium')
            max_distance = float(request.form.get('max_distance', 20))
            
            # Map condition to specialty needed
            condition_to_specialty = {
                'Joint disorders': 'Orthopedic',
                'Muscle injuries': 'Sports',
                'Tendon & ligament disorders': 'Sports',
                'Spine conditions': 'MSK',
                'Nerve compression syndromes': 'Neuro',
                'Post-surgical rehabilitation': 'Post-op',
                'Sports & overuse injuries': 'Sports',
                'Degenerative conditions': 'MSK',
                'Inflammatory conditions': 'General',
                'Balance & functional decline disorders': 'Neuro',
                'Others': 'General',
                'Knee Replacement': 'Post-op',
                'Hip Replacement': 'Post-op',
                'ACL Reconstruction': 'Sports',
                'Shoulder Surgery': 'Post-op',
                'Back Pain': 'MSK',
                'Stroke Recovery': 'Neuro',
                'General Rehab': 'General'
            }
            specialty_needed = condition_to_specialty.get(condition, 'General')
            
            execute_db('''
                INSERT INTO patients (user_id, condition, urgency, max_distance, 
                                    specialty_needed, address) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, condition, urgency, max_distance, specialty_needed, pincode))
            
            # Set default availability (all timeslots available)
            timeslots = query_db('SELECT id FROM timeslots')
            for ts in timeslots:
                execute_db(
                    'INSERT INTO patient_availability (patient_id, timeslot_id, available) VALUES (?, ?, ?)',
                    (user_id, ts['id'], 1)
                )
            
            # Set default time preferences (morning preferred)
            for ts in timeslots:
                # Morning slots get higher preference
                is_morning = '_9am' in ts['id'] or '_10am' in ts['id'] or '_11am' in ts['id']
                pref_score = 0.8 if is_morning else 0.5
                execute_db(
                    'INSERT INTO patient_time_preferences (patient_id, timeslot_id, preference_score) VALUES (?, ?, ?)',
                    (user_id, ts['id'], pref_score)
                )
            
            # Assign to selected doctor, or first available if none selected
            selected_doctor_id = request.form.get('doctor_id')
            if selected_doctor_id:
                execute_db(
                    'INSERT OR IGNORE INTO doctor_patient (doctor_id, patient_id) VALUES (?, ?)',
                    (int(selected_doctor_id), user_id)
                )
                # Set as preferred doctor
                execute_db(
                    'UPDATE patients SET preferred_doctor_id = ? WHERE user_id = ?',
                    (int(selected_doctor_id), user_id)
                )
            else:
                # Fallback: assign to first available doctor
                doctor = query_db('SELECT id FROM users WHERE role = ? LIMIT 1', ('doctor',), one=True)
                if doctor:
                    execute_db(
                        'INSERT OR IGNORE INTO doctor_patient (doctor_id, patient_id) VALUES (?, ?)',
                        (doctor['id'], user_id)
                    )
        
        # If doctor, create doctor records with optimization data
        elif role == 'doctor':
            # Get specialties from form (multiple checkboxes)
            specialties = request.form.getlist('specialties')
            clinic_name = request.form.get('clinic_name', '')
            clinic_pincode = request.form.get('clinic_pincode', '')
            
            # Save doctor specialties
            if specialties:
                for specialty in specialties:
                    execute_db(
                        'INSERT INTO doctor_specialties (doctor_id, specialty) VALUES (?, ?)',
                        (user_id, specialty)
                    )
            else:
                # Default to General if no specialties selected
                execute_db(
                    'INSERT INTO doctor_specialties (doctor_id, specialty) VALUES (?, ?)',
                    (user_id, 'General')
                )
            
            # Save clinic location
            execute_db(
                'INSERT INTO doctor_locations (doctor_id, clinic_name, address) VALUES (?, ?, ?)',
                (user_id, clinic_name, clinic_pincode)
            )

            # Also store clinic pincode in users.pincode for distance calculations
            if clinic_pincode:
                execute_db(
                    'UPDATE users SET pincode = ? WHERE id = ?',
                    (clinic_pincode, user_id)
                )
            
            # Set default availability (all weekday timeslots available)
            timeslots = query_db('SELECT id FROM timeslots')
            for ts in timeslots:
                execute_db(
                    'INSERT INTO doctor_availability (doctor_id, timeslot_id, available) VALUES (?, ?, ?)',
                    (user_id, ts['id'], 1)
                )
        
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    
    # GET request - fetch available doctors for the dropdown
    doctors = query_db('SELECT id, name FROM users WHERE role = ?', ('doctor',))
    return render_template('signup.html', doctors=doctors)


@app.route('/logout')
def logout():
    """Log out the current user."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('landing'))


# ==================== PATIENT ROUTES ====================

@app.route('/patient/dashboard')
@login_required
@role_required('patient')
def patient_dashboard():
    """Patient Home Dashboard"""
    user = get_current_user()
    
    # Get patient's medical info
    patient_info = query_db(
        'SELECT * FROM patients WHERE user_id = ?',
        (session['user_id'],),
        one=True
    )
    
    # If patient record doesn't exist yet, create one with default values
    if not patient_info:
        execute_db('''
            INSERT INTO patients (user_id, condition, current_week, adherence_rate, 
                                  streak_days, avg_quality_score, avg_pain_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], 'General Rehabilitation', 1, 0, 0, 0, 0))
        
        patient_info = query_db(
            'SELECT * FROM patients WHERE user_id = ?',
            (session['user_id'],),
            one=True
        )
    
    # Get patient's workouts
    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.description
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
    ''', (session['user_id'],))
    
    # Get recent sessions (last 5) — session-level with exercise details
    import json as _json
    recent_sessions_raw = query_db('''
        SELECT s.id, s.patient_id, s.started_at, s.completed_at,
               s.pain_before, s.pain_after, s.effort_level,
               s.quality_score, s.completed_perc,
               strftime('%Y-%m-%d %H:%M', s.completed_at) as formatted_date
        FROM sessions s
        WHERE s.patient_id = ?
        AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at DESC
        LIMIT 5
    ''', (session['user_id'],))

    recent_sessions = []
    for rs in (recent_sessions_raw or []):
        # Get exercises for this session
        exs = query_db('''
            SELECT e.name, w.sets as target_sets, w.reps as target_reps,
                   se.sets_completed, se.exercise_start_time, se.exercise_end_time
            FROM session_exercises se
            JOIN workouts w ON se.workout_id = w.id
            JOIN exercises e ON w.exercise_id = e.id
            WHERE se.session_id = ?
            ORDER BY se.exercise_start_time
        ''', (rs['id'],))

        ex_list = []
        for ex in (exs or []):
            comp = _json.loads(ex['sets_completed']) if ex['sets_completed'] else {}
            sets_done = len([v for v in comp.values() if int(v) > 0])
            ex_list.append({
                'name': ex['name'],
                'target_sets': ex['target_sets'],
                'target_reps': ex['target_reps'],
                'sets_done': sets_done
            })

        # Calculate total duration
        duration_seconds = None
        if rs['started_at'] and rs['completed_at']:
            try:
                st = datetime.fromisoformat(rs['started_at'])
                en = datetime.fromisoformat(rs['completed_at'])
                duration_seconds = int((en - st).total_seconds())
            except:
                pass

        recent_sessions.append({
            'id': rs['id'],
            'formatted_date': rs['formatted_date'],
            'completed_at': rs['completed_at'],
            'quality_score': rs['quality_score'],
            'completed_perc': rs['completed_perc'],
            'pain_before': rs['pain_before'],
            'pain_after': rs['pain_after'],
            'exercises': ex_list,
            'duration_seconds': duration_seconds
        })

    # Get session history for charts (last 15 sessions, oldest first)
    chart_sessions_raw = query_db('''
        SELECT s.quality_score, s.pain_before, s.pain_after, s.effort_level,
               s.completed_at
        FROM sessions s
        WHERE s.patient_id = ?
        AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at ASC
        LIMIT 15
    ''', (session['user_id'],))
    chart_sessions = [dict(cs) for cs in chart_sessions_raw] if chart_sessions_raw else []

    # Get upcoming appointments (simpler query - just get all scheduled)
    upcoming_appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status = 'scheduled'
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 3
    ''', (session['user_id'],))
    
    # Calculate dynamic statistics from sessions
    total_sessions = query_db('''
        SELECT COUNT(DISTINCT COALESCE(session_group_id, id)) as count FROM sessions 
        WHERE patient_id = ?
    ''', (session['user_id'],), one=True)
    
    sessions_this_week = query_db('''
        SELECT COUNT(DISTINCT COALESCE(session_group_id, id)) as count FROM sessions 
        WHERE patient_id = ? 
        AND completed_at >= date('now', '-7 days')
    ''', (session['user_id'],), one=True)

    # Check today's session status — best completed_perc for today
    today_session = query_db('''
        SELECT id, completed_perc, completed_at
        FROM sessions
        WHERE patient_id = ?
        AND date(started_at) = date('now')
        ORDER BY completed_perc DESC
        LIMIT 1
    ''', (session['user_id'],), one=True)

    today_completed = False
    today_session_id = None
    today_perc = 0
    if today_session:
        today_session_id = today_session['id']
        today_perc = today_session['completed_perc'] or 0
        today_completed = (today_perc >= 100)

    # Get current caregivers for this patient
    caregivers = query_db('''
        SELECT u.name, u.email, cp.relationship
        FROM caregiver_patient cp
        JOIN users u ON cp.caregiver_id = u.id
        WHERE cp.patient_id = ?
    ''', (session['user_id'],))

    # Get pending caregiver requests for this patient
    pending_requests = query_db('''
        SELECT cr.id, u.name as caregiver_name, u.email as caregiver_email, cr.requested_at
        FROM caregiver_requests cr
        JOIN users u ON cr.caregiver_id = u.id
        WHERE cr.patient_id = ? AND cr.status = 'pending'
        ORDER BY cr.requested_at DESC
    ''', (session['user_id'],))

    return render_template('patient/dashboard.html',
                            user=user,
                            patient=patient_info,
                            workouts=workouts if workouts else [],
                            recent_sessions=recent_sessions,
                            chart_sessions=chart_sessions if chart_sessions else [],
                            upcoming_appointments=upcoming_appointments if upcoming_appointments else [],
                            caregivers=caregivers if caregivers else [],
                            pending_caregiver_requests=pending_requests if pending_requests else [],
                            total_sessions=total_sessions['count'] if total_sessions else 0,
                            sessions_this_week=sessions_this_week['count'] if sessions_this_week else 0,
                            today_completed=today_completed,
                            today_session_id=today_session_id,
                            today_perc=today_perc,
                            chat_patient_id=None)


@app.route('/patient/session')
@login_required
@role_required('patient')
def rehab_session():
    """Rehab Session Screen"""
    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.description, e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
    ''', (session['user_id'],))
    
    return render_template('patient/session.html', workouts=workouts if workouts else [])


@app.route('/patient/checkin', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def pain_checkin():
    """Pain & Effort Check-In — now handled via JS API calls. Keep route for direct access."""
    return render_template('patient/checkin.html')


@app.route('/patient/summary')
@app.route('/patient/summary/<int:session_id>')
@login_required
@role_required('patient')
def session_summary(session_id=None):
    """Session Summary Screen — loads data dynamically via API."""
    import json
    if session_id is None:
        # Fallback: get latest session for this patient
        latest = query_db('''
            SELECT id FROM sessions
            WHERE patient_id = ? AND completed_at IS NOT NULL
            ORDER BY completed_at DESC LIMIT 1
        ''', (session['user_id'],), one=True)
        session_id = latest['id'] if latest else None

    # Pre-load data server-side for the template
    sess = None
    exercises_list = []
    overall_duration = None
    if session_id:
        sess = query_db('SELECT * FROM sessions WHERE id = ? AND patient_id = ?',
                         (session_id, session['user_id']), one=True)
        if sess:
            exercises = query_db('''
                SELECT se.*, COALESCE(se.exercise_name, e.name) as exercise_name
                FROM session_exercises se
                LEFT JOIN workouts w ON se.workout_id = w.id
                LEFT JOIN exercises e ON w.exercise_id = e.id
                WHERE se.session_id = ?
                ORDER BY se.exercise_start_time
            ''', (session_id,))
            for ex in (exercises or []):
                req = json.loads(ex['sets_required']) if ex['sets_required'] else {}
                comp = json.loads(ex['sets_completed']) if ex['sets_completed'] else {}
                total_req = sum(int(v) for v in req.values())
                total_comp = sum(int(v) for v in comp.values())
                ex_perc = round(total_comp / total_req * 100, 1) if total_req > 0 else 0
                ex_duration = None
                if ex['exercise_start_time'] and ex['exercise_end_time']:
                    try:
                        st = datetime.fromisoformat(ex['exercise_start_time'])
                        en = datetime.fromisoformat(ex['exercise_end_time'])
                        ex_duration = int((en - st).total_seconds())
                    except:
                        pass
                exercises_list.append({
                    "exercise_name": ex['exercise_name'],
                    "quality_score": ex['quality_score'],
                    "sets_required": req,
                    "sets_completed": comp,
                    "completion_perc": ex_perc,
                    "duration_seconds": ex_duration
                })
            if sess['started_at'] and sess['completed_at']:
                try:
                    s = datetime.fromisoformat(sess['started_at'])
                    e = datetime.fromisoformat(sess['completed_at'])
                    overall_duration = int((e - s).total_seconds())
                except:
                    pass

    return render_template('patient/summary.html',
                         session_data=sess,
                         exercises=exercises_list,
                         overall_duration=overall_duration,
                         session_id=session_id)


@app.route('/patient/profile')
@login_required
@role_required('patient')
def patient_profile():
    """Personal Details page"""
    user_info = query_db(
        'SELECT id, name, email, role, phone, pincode, dob, created_at FROM users WHERE id = ?',
        (session['user_id'],), one=True
    )
    patient_info = query_db(
        'SELECT * FROM patients WHERE user_id = ?',
        (session['user_id'],), one=True
    )
    doctor = query_db('''
        SELECT u.name, u.email, u.phone, dp.assigned_date
        FROM doctor_patient dp
        JOIN users u ON dp.doctor_id = u.id
        WHERE dp.patient_id = ?
    ''', (session['user_id'],), one=True)
    caregiver = query_db('''
        SELECT u.name, u.email, u.phone, cp.relationship
        FROM caregiver_patient cp
        JOIN users u ON cp.caregiver_id = u.id
        WHERE cp.patient_id = ?
    ''', (session['user_id'],), one=True)

    # Compute age from dob
    age = None
    if user_info and user_info['dob']:
        dob = date.fromisoformat(user_info['dob'])
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    return render_template('patient/profile.html',
                         user_info=user_info,
                         patient=patient_info,
                         doctor=doctor,
                         caregiver=caregiver,
                         age=age,
                         active_tab='personal')


@app.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile fields (email, phone, pincode) — works for all roles"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    user_id = session['user_id']
    allowed_fields = {'email', 'phone', 'pincode'}
    updates = []
    values = []

    for field in allowed_fields:
        if field in data:
            val = data[field].strip() if data[field] else ''
            # Email validation
            if field == 'email':
                if not val or '@' not in val:
                    return jsonify({'success': False, 'error': 'Invalid email address'}), 400
                # Check uniqueness
                existing = query_db(
                    'SELECT id FROM users WHERE email = ? AND id != ?',
                    (val, user_id), one=True
                )
                if existing:
                    return jsonify({'success': False, 'error': 'Email already in use'}), 400
            updates.append(f'{field} = ?')
            values.append(val if val else None)

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

    values.append(user_id)
    execute_db(
        f'UPDATE users SET {", ".join(updates)} WHERE id = ?',
        tuple(values)
    )

    return jsonify({'success': True, 'message': 'Profile updated successfully'})


@app.route('/patient/progress')
@login_required
@role_required('patient')
def progress_history():
    """Progress & History Screen"""
    all_sessions = query_db('''
        SELECT s.*,
               (SELECT GROUP_CONCAT(DISTINCT e.name)
                FROM session_exercises se
                JOIN workouts w ON se.workout_id = w.id
                JOIN exercises e ON w.exercise_id = e.id
                WHERE se.session_id = s.id) as exercise_name
        FROM sessions s
        WHERE s.patient_id = ?
        AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at DESC
    ''', (session['user_id'],))
    
    patient_info = query_db(
        'SELECT * FROM patients WHERE user_id = ?',
        (session['user_id'],),
        one=True
    )
    
    return render_template('patient/progress.html',
                         sessions=all_sessions if all_sessions else [],
                         patient=patient_info)


@app.route('/patient/appointments')
@login_required
@role_required('patient')
def patient_appointments():
    """Patient's Appointments View"""
    # Get all upcoming appointments
    appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status = 'scheduled'
        ORDER BY a.appointment_date, a.appointment_time
    ''', (session['user_id'],))
    
    # Get past appointments
    past_appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND (a.status = 'completed' OR a.status = 'cancelled')
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 10
    ''', (session['user_id'],))
    
    # Get patient scheduling preferences
    patient_prefs = query_db(
        'SELECT * FROM patients WHERE user_id = ?',
        (session['user_id'],),
        one=True
    )
    
    return render_template('patient/appointments.html',
                         appointments=appointments if appointments else [],
                         past_appointments=past_appointments if past_appointments else [],
                         patient_prefs=patient_prefs)


@app.route('/patient/book-appointment', methods=['POST'])
@login_required
@role_required('patient')
def patient_book_appointment():
    """Patient books an appointment with a recommended doctor."""
    doctor_name = request.form.get('doctor_name', '').strip()
    appointment_date = request.form['appointment_date']
    appointment_time = request.form['appointment_time']
    duration = request.form.get('duration', 30)
    notes = request.form.get('notes', '')

    # Find doctor by name
    doctor = query_db(
        "SELECT id FROM users WHERE role = 'doctor' AND name LIKE ?",
        (f'%{doctor_name}%',), one=True
    )
    if not doctor:
        doctor_name_clean = doctor_name.replace('Dr.', '').strip()
        doctor = query_db(
            "SELECT id FROM users WHERE role = 'doctor' AND name LIKE ?",
            (f'%{doctor_name_clean}%',), one=True
        )

    if not doctor:
        flash('Doctor not found. Please try again.', 'error')
        return redirect(url_for('patient_appointments'))

    doctor_id = doctor['id']
    patient_id = session['user_id']
    room_id = f"rehab-{doctor_id}-{patient_id}-{uuid.uuid4().hex[:8]}"

    try:
        execute_db('''
            INSERT INTO appointments
            (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled')
        ''', (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id))
        flash('Appointment booked successfully! Your doctor will be notified.', 'success')
    except Exception as e:
        flash('Failed to book appointment. Please try again.', 'error')
        print(f'[ERROR] Patient book appointment failed: {e}')

    return redirect(url_for('patient_appointments'))


# ==================== CLINICIAN ROUTES ====================

@app.route('/clinician/profile')
@login_required
@role_required('doctor')
def clinician_profile():
    """Clinician Profile - personal details + all patients with their caregivers"""
    doctor_id = session['user_id']

    # Doctor's own info
    user_info = query_db(
        'SELECT id, name, email, role, phone, pincode, dob, created_at FROM users WHERE id = ?',
        (doctor_id,), one=True
    )

    # All patients assigned to this doctor, with their caregiver info
    patients_with_caregivers = query_db('''
        SELECT 
            u.id, u.name, u.email, u.phone,
            p.condition, p.surgery_date, p.current_week,
            p.adherence_rate, p.avg_pain_level, p.completed_sessions,
            dp.assigned_date,
            cg_u.name  AS caregiver_name,
            cg_u.email AS caregiver_email,
            cg_u.phone AS caregiver_phone,
            cp.relationship AS caregiver_relationship
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON p.user_id = dp.patient_id
        LEFT JOIN caregiver_patient cp ON u.id = cp.patient_id
        LEFT JOIN users cg_u ON cp.caregiver_id = cg_u.id
        WHERE dp.doctor_id = ?
        ORDER BY u.name
    ''', (doctor_id,))

    patients_with_caregivers = patients_with_caregivers if patients_with_caregivers else []

    # Summary stats
    total_patients = len(patients_with_caregivers)
    patients_with_cg = sum(1 for p in patients_with_caregivers if p['caregiver_name'])
    avg_adherence = round(
        sum(p['adherence_rate'] for p in patients_with_caregivers) / total_patients, 1
    ) if total_patients > 0 else 0

    # Compute age from dob
    age = None
    if user_info and user_info['dob']:
        dob = date.fromisoformat(user_info['dob'])
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    return render_template('clinician/profile.html',
                         user_info=user_info,
                         patients=patients_with_caregivers,
                         total_patients=total_patients,
                         patients_with_cg=patients_with_cg,
                         avg_adherence=avg_adherence,
                         age=age)


@app.route('/clinician/dashboard')
@login_required
@role_required('doctor')
def clinician_dashboard():
    """Clinician Dashboard"""
    # Get patients assigned to this doctor
    patients = query_db('''
        SELECT 
            u.id, u.name, u.email,
            p.condition, p.current_week, p.adherence_rate, 
            p.avg_pain_level, p.avg_quality_score, p.completed_sessions
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON p.user_id = dp.patient_id
        WHERE dp.doctor_id = ?
        ORDER BY p.adherence_rate ASC
    ''', (session['user_id'],))
    
    # If no assigned patients, show ALL patients (for demo/new doctors)
    if not patients:
        patients = query_db('''
            SELECT 
                u.id, u.name, u.email,
                p.condition, p.current_week, p.adherence_rate, 
                p.avg_pain_level, p.avg_quality_score, p.completed_sessions
            FROM users u
            JOIN patients p ON u.id = p.user_id
            ORDER BY p.adherence_rate ASC
        ''')
    
    patients = patients if patients else []
    total_patients = len(patients)
    needs_attention = sum(1 for p in patients if p['adherence_rate'] < 50 or p['avg_pain_level'] > 6)
    avg_adherence = sum(p['adherence_rate'] for p in patients) / total_patients if total_patients > 0 else 0
    
    appointments = query_db('''
        SELECT a.*, u.name as patient_name
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ? AND a.status = 'scheduled'
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 5
    ''', (session['user_id'],))
    
    return render_template('clinician/dashboard.html',
                         patients=patients,
                         total_patients=total_patients,
                         needs_attention=needs_attention,
                         avg_adherence=round(avg_adherence),
                         upcoming_appointments=len(appointments) if appointments else 0)


@app.route('/clinician/patient/<int:patient_id>')
@login_required
@role_required('doctor')
def patient_detail(patient_id):
    """Patient Detail View"""
    patient = query_db('''
        SELECT u.*, p.*
        FROM users u
        JOIN patients p ON u.id = p.user_id
        WHERE u.id = ?
    ''', (patient_id,), one=True)
    
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('clinician_dashboard'))
    
    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
    ''', (patient_id,))
    
    sessions = query_db('''
        SELECT s.*,
               (SELECT GROUP_CONCAT(DISTINCT e.name)
                FROM session_exercises se
                JOIN workouts w ON se.workout_id = w.id
                JOIN exercises e ON w.exercise_id = e.id
                WHERE se.session_id = s.id) as exercise_name
        FROM sessions s
        WHERE s.patient_id = ?
        AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at DESC
        LIMIT 10
    ''', (patient_id,))
    
    # Get clinician notes for this patient
    notes = query_db('''
        SELECT cn.*, u.name as doctor_name
        FROM clinician_notes cn
        JOIN users u ON cn.doctor_id = u.id
        WHERE cn.patient_id = ?
        ORDER BY cn.created_at DESC
        LIMIT 20
    ''', (patient_id,))

    # Get current caregivers for this patient
    caregivers = query_db('''
        SELECT u.name, u.email, cp.relationship
        FROM caregiver_patient cp
        JOIN users u ON cp.caregiver_id = u.id
        WHERE cp.patient_id = ?
    ''', (patient_id,))

    # Get pending caregiver requests for this patient
    pending_requests = query_db('''
        SELECT cr.id, u.name as caregiver_name, u.email as caregiver_email, cr.requested_at
        FROM caregiver_requests cr
        JOIN users u ON cr.caregiver_id = u.id
        WHERE cr.patient_id = ? AND cr.status = 'pending'
        ORDER BY cr.requested_at DESC
    ''', (patient_id,))

    return render_template('clinician/patient_detail.html',
                         patient=patient,
                         patient_id=patient_id,
                         workouts=workouts if workouts else [],
                         sessions=sessions if sessions else [],
                         notes=notes if notes else [],
                         caregivers=caregivers if caregivers else [],
                         pending_caregiver_requests=pending_requests if pending_requests else [])


@app.route('/clinician/patient/<int:patient_id>/add-note', methods=['POST'])
@login_required
@role_required('doctor')
def add_clinician_note(patient_id):
    """Add a clinician note for a patient."""
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    execute_db('''
        INSERT INTO clinician_notes (doctor_id, patient_id, note_text)
        VALUES (?, ?, ?)
    ''', (session['user_id'], patient_id, note_text))

    flash('Note added successfully.', 'success')
    return redirect(url_for('patient_detail', patient_id=patient_id))


@app.route('/clinician/plan-editor', methods=['GET'])
@login_required
@role_required('doctor')
def plan_editor():
    """Rehab Plan Editor — all patients' plans in one view"""
    # Get patients assigned to this doctor
    patients = query_db('''
        SELECT u.id, u.name, p.condition
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON p.user_id = dp.patient_id
        WHERE dp.doctor_id = ?
    ''', (session['user_id'],))

    # If no assigned patients, show ALL patients
    if not patients:
        patients = query_db('''
            SELECT u.id, u.name, p.condition
            FROM users u
            JOIN patients p ON u.id = p.user_id
        ''')

    patients = [dict(p) for p in patients] if patients else []

    # For every patient, fetch their active workouts
    for pat in patients:
        workouts = query_db('''
            SELECT w.id, w.exercise_id, w.sets, w.reps, w.frequency,
                   w.instructions, e.name AS exercise_name, e.category,
                   e.description AS exercise_desc
            FROM workouts w
            JOIN exercises e ON w.exercise_id = e.id
            WHERE w.patient_id = ? AND w.is_active = 1
            ORDER BY w.id
        ''', (pat['id'],))
        pat['workouts'] = [dict(w) for w in workouts] if workouts else []

    exercises = query_db('SELECT * FROM exercises ORDER BY category, name')
    exercises = [dict(e) for e in exercises] if exercises else []

    return render_template('clinician/plan_editor.html',
                           patients=patients,
                           exercises=exercises)


# ---------- Plan-Editor API endpoints (JSON) ----------

@app.route('/api/plan/add-exercise', methods=['POST'])
@login_required
@role_required('doctor')
def api_plan_add_exercise():
    """Add an exercise to a patient's plan (AJAX)"""
    data = request.get_json()
    patient_id = data.get('patient_id')
    exercise_id = data.get('exercise_id')
    sets = data.get('sets', 3)
    reps = data.get('reps', 10)
    frequency = data.get('frequency', 'Daily')
    instructions = data.get('instructions', '')

    if not patient_id or not exercise_id:
        return jsonify({'error': 'Missing patient_id or exercise_id'}), 400

    execute_db('''
        INSERT INTO workouts
        (patient_id, exercise_id, sets, reps, frequency, instructions)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (patient_id, exercise_id, sets, reps, frequency, instructions))

    # Return the newly-created workout
    new_w = query_db('''
        SELECT w.id, w.exercise_id, w.sets, w.reps, w.frequency,
               w.instructions, e.name AS exercise_name, e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
        ORDER BY w.id DESC LIMIT 1
    ''', (patient_id,), one=True)

    return jsonify({'ok': True, 'workout': dict(new_w) if new_w else {}})


@app.route('/api/plan/update-workout/<int:workout_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_plan_update_workout(workout_id):
    """Update sets/reps/frequency/instructions for a workout"""
    data = request.get_json()
    sets = data.get('sets')
    reps = data.get('reps')
    frequency = data.get('frequency')
    instructions = data.get('instructions')

    execute_db('''
        UPDATE workouts
        SET sets = COALESCE(?, sets),
            reps = COALESCE(?, reps),
            frequency = COALESCE(?, frequency),
            instructions = COALESCE(?, instructions)
        WHERE id = ?
    ''', (sets, reps, frequency, instructions, workout_id))

    return jsonify({'ok': True})


@app.route('/api/plan/remove-workout/<int:workout_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_plan_remove_workout(workout_id):
    """Soft-delete a workout from a patient's plan"""
    execute_db('UPDATE workouts SET is_active = 0 WHERE id = ?', (workout_id,))
    return jsonify({'ok': True})


@app.route('/clinician/consultation', methods=['GET', 'POST'])
@login_required
@role_required('doctor')
def consultation():
    """Consultation & Scheduling Screen"""
    if request.method == 'POST':
        patient_id = request.form['patient_id']
        appointment_date = request.form['appointment_date']
        appointment_time = request.form['appointment_time']
        duration = request.form.get('duration', 30)
        notes = request.form.get('notes', '')
        
        # Generate unique room ID for video call
        room_id = f"rehab-{session['user_id']}-{patient_id}-{uuid.uuid4().hex[:8]}"
        
        execute_db('''
            INSERT INTO appointments 
            (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], patient_id, appointment_date, appointment_time, duration, notes, room_id))
        
        flash('Appointment scheduled successfully!', 'success')
        return redirect(url_for('consultation'))
    
    # Get patients assigned to this doctor
    patients = query_db('''
        SELECT u.id, u.name
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON p.user_id = dp.patient_id
        WHERE dp.doctor_id = ?
    ''', (session['user_id'],))

    # If no assigned patients, show ALL patients (for demo/new doctors)
    if not patients or len(patients) == 0:
        patients = query_db('''
            SELECT u.id, u.name
            FROM users u
            JOIN patients p ON u.id = p.user_id
        ''')

    print('[DEBUG] Consultation patients:', patients)

    appointments = query_db('''
        SELECT a.*, u.name as patient_name, p.condition, p.adherence_rate, p.avg_pain_level, p.avg_quality_score
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        LEFT JOIN patients p ON u.id = p.user_id
        WHERE a.doctor_id = ? AND a.status = 'scheduled'
        ORDER BY a.appointment_date, a.appointment_time
    ''', (session['user_id'],))

    # Past completed/cancelled appointments
    past_appointments = query_db('''
        SELECT a.*, u.name as patient_name, p.condition
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        LEFT JOIN patients p ON u.id = p.user_id
        WHERE a.doctor_id = ? AND a.status IN ('completed', 'cancelled')
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 15
    ''', (session['user_id'],))

    return render_template('clinician/consultation.html',
                         patients=patients if patients else [],
                         appointments=appointments if appointments else [],
                         past_appointments=past_appointments if past_appointments else [])


# ==================== VIDEO CALL ROUTES ====================

@app.route('/video-call/<int:appointment_id>')
@login_required
def video_call(appointment_id):
    """Video Call Room"""
    appointment = query_db('''
        SELECT a.*, 
               doc.name as doctor_name,
               pat.name as patient_name,
               p.condition, p.adherence_rate, p.avg_pain_level, p.avg_quality_score
        FROM appointments a
        JOIN users doc ON a.doctor_id = doc.id
        JOIN users pat ON a.patient_id = pat.id
        LEFT JOIN patients p ON pat.id = p.user_id
        WHERE a.id = ?
    ''', (appointment_id,), one=True)
    
    if not appointment:
        flash('Appointment not found.', 'error')
        return redirect(url_for('landing'))
    
    # Check if user is authorized (must be doctor or patient of this appointment)
    if session['user_id'] != appointment['doctor_id'] and session['user_id'] != appointment['patient_id']:
        flash('You are not authorized to join this call.', 'error')
        return redirect(url_for('landing'))
    
    # Get or generate room_id
    room_id = appointment['room_id'] if appointment['room_id'] else f"rehab-call-{appointment_id}"
    
    # Update room_id if it wasn't set
    if not appointment['room_id']:
        execute_db('UPDATE appointments SET room_id = ? WHERE id = ?', (room_id, appointment_id))
    
    return render_template('video_call.html',
                         appointment=appointment,
                         room_id=room_id,
                         user_name=session['user_name'],
                         is_doctor=(session['role'] == 'doctor'))


@app.route('/video-call/quick/<int:patient_id>')
@login_required
@role_required('doctor')
def quick_call(patient_id):
    """Start a quick video call without scheduling"""
    patient = query_db('SELECT * FROM users WHERE id = ?', (patient_id,), one=True)
    
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('clinician_dashboard'))
    
    # Create an instant appointment
    room_id = f"quick-call-{session['user_id']}-{patient_id}-{uuid.uuid4().hex[:8]}"
    today = date.today().isoformat()
    now = datetime.now().strftime('%H:%M')
    
    appointment_id = execute_db('''
        INSERT INTO appointments 
        (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled')
    ''', (session['user_id'], patient_id, today, now, 30, 'Quick call', room_id))
    
    return redirect(url_for('video_call', appointment_id=appointment_id))


# ==================== CAREGIVER ROUTES ====================

@app.route('/caregiver/dashboard')
@login_required
@role_required('caregiver')
def caregiver_dashboard():
    """Caregiver Dashboard"""
    monitored_patients = query_db('''
        SELECT 
            u.id, u.name,
            p.condition, p.adherence_rate, p.avg_pain_level, 
            p.avg_quality_score, p.streak_days,
            cp.relationship
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN caregiver_patient cp ON u.id = cp.patient_id
        WHERE cp.caregiver_id = ?
    ''', (session['user_id'],))
    
    patient_ids = [p['id'] for p in monitored_patients] if monitored_patients else []
    recent_sessions = []
    if patient_ids:
        placeholders = ','.join('?' * len(patient_ids))
        recent_sessions = query_db(f'''
            SELECT s.*, u.name as patient_name,
                   (SELECT GROUP_CONCAT(DISTINCT e.name)
                    FROM session_exercises se
                    JOIN workouts w ON se.workout_id = w.id
                    JOIN exercises e ON w.exercise_id = e.id
                    WHERE se.session_id = s.id) as exercise_name
            FROM sessions s
            JOIN users u ON s.patient_id = u.id
            WHERE s.patient_id IN ({placeholders})
            AND s.completed_at IS NOT NULL
            ORDER BY s.completed_at DESC
            LIMIT 10
        ''', patient_ids)
    
    # Build alerts from real session data
    alerts = []
    if recent_sessions:
        for s in recent_sessions:
            if s['pain_after'] and s['pain_after'] >= 7:
                alerts.append({
                    'type': 'danger',
                    'title': 'Pain Spike Reported',
                    'message': f"{s['patient_name']} reported pain level {s['pain_after']}/10 after {s['exercise_name']}",
                    'time': s['completed_at']
                })
            if s['quality_score'] is not None and s['quality_score'] < 50:
                alerts.append({
                    'type': 'warning',
                    'title': 'Low Quality Session',
                    'message': f"{s['patient_name']}'s form quality dropped to {int(s['quality_score'])} during {s['exercise_name']}",
                    'time': s['completed_at']
                })

    # Check for low adherence across monitored patients
    if monitored_patients:
        for p in monitored_patients:
            if p['adherence_rate'] is not None and p['adherence_rate'] < 40:
                alerts.append({
                    'type': 'danger',
                    'title': 'Low Adherence Alert',
                    'message': f"{p['name']}'s adherence rate is {int(p['adherence_rate'])}% — needs encouragement",
                    'time': None
                })
            elif p['adherence_rate'] is not None and p['adherence_rate'] < 60:
                alerts.append({
                    'type': 'warning',
                    'title': 'Adherence Declining',
                    'message': f"{p['name']}'s adherence rate is {int(p['adherence_rate'])}%",
                    'time': None
                })

    # Get caregiver's pending requests
    my_pending_requests = query_db('''
        SELECT cr.id, cr.status, cr.requested_at, u.name as patient_name
        FROM caregiver_requests cr
        JOIN users u ON cr.patient_id = u.id
        WHERE cr.caregiver_id = ?
        ORDER BY cr.requested_at DESC
        LIMIT 10
    ''', (session['user_id'],))

    # Build data for chatbot
    patients_list = monitored_patients if monitored_patients else []
    first_patient_id = patients_list[0]['id'] if patients_list else None
    caregiver_patient_list = [{'id': p['id'], 'name': p['name']} for p in patients_list]

    return render_template('caregiver/dashboard.html',
                         patients=patients_list,
                         recent_sessions=recent_sessions if recent_sessions else [],
                         alerts=alerts,
                         my_requests=my_pending_requests if my_pending_requests else [],
                         chat_patient_id=first_patient_id,
                         caregiver_patient_list=caregiver_patient_list)


# ==================== CAREGIVER ACCESS MANAGEMENT ====================

@app.route('/patient/add-caregiver', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_caregiver():
    """Patient directly grants caregiver access by email."""
    caregiver_email = request.form.get('caregiver_email', '').strip()
    if not caregiver_email:
        flash('Please enter a caregiver email.', 'error')
        return redirect(url_for('patient_dashboard'))

    caregiver = query_db(
        "SELECT id, name FROM users WHERE email = ? AND role = 'caregiver'",
        (caregiver_email,), one=True
    )
    if not caregiver:
        flash('No caregiver account found with that email. They need to sign up as a caregiver first.', 'error')
        return redirect(url_for('patient_dashboard'))

    # Check if already linked
    existing = query_db(
        'SELECT id FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
        (caregiver['id'], session['user_id']), one=True
    )
    if existing:
        flash(f'{caregiver["name"]} is already your caregiver.', 'error')
        return redirect(url_for('patient_dashboard'))

    execute_db(
        'INSERT OR IGNORE INTO caregiver_patient (caregiver_id, patient_id, relationship) VALUES (?, ?, ?)',
        (caregiver['id'], session['user_id'], 'Authorized by Patient')
    )

    # Also clear any pending request from this caregiver for this patient
    execute_db(
        "UPDATE caregiver_requests SET status = 'approved', resolved_at = CURRENT_TIMESTAMP, resolved_by = ? WHERE caregiver_id = ? AND patient_id = ? AND status = 'pending'",
        (session['user_id'], caregiver['id'], session['user_id'])
    )

    flash(f'{caregiver["name"]} has been added as your caregiver.', 'success')
    return redirect(url_for('patient_dashboard'))


@app.route('/clinician/patient/<int:patient_id>/add-caregiver', methods=['POST'])
@login_required
@role_required('doctor')
def doctor_add_caregiver(patient_id):
    """Doctor grants caregiver access for a patient by email."""
    caregiver_email = request.form.get('caregiver_email', '').strip()
    if not caregiver_email:
        flash('Please enter a caregiver email.', 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    caregiver = query_db(
        "SELECT id, name FROM users WHERE email = ? AND role = 'caregiver'",
        (caregiver_email,), one=True
    )
    if not caregiver:
        flash('No caregiver account found with that email. They need to sign up as a caregiver first.', 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    existing = query_db(
        'SELECT id FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
        (caregiver['id'], patient_id), one=True
    )
    if existing:
        flash(f'{caregiver["name"]} is already a caregiver for this patient.', 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

    execute_db(
        'INSERT OR IGNORE INTO caregiver_patient (caregiver_id, patient_id, relationship) VALUES (?, ?, ?)',
        (caregiver['id'], patient_id, 'Authorized by Doctor')
    )

    # Clear any pending request
    execute_db(
        "UPDATE caregiver_requests SET status = 'approved', resolved_at = CURRENT_TIMESTAMP, resolved_by = ? WHERE caregiver_id = ? AND patient_id = ? AND status = 'pending'",
        (session['user_id'], caregiver['id'], patient_id)
    )

    flash(f'{caregiver["name"]} has been added as caregiver for this patient.', 'success')
    return redirect(url_for('patient_detail', patient_id=patient_id))


@app.route('/caregiver/request-monitor', methods=['POST'])
@login_required
@role_required('caregiver')
def caregiver_request_monitor():
    """Caregiver requests to monitor a patient by email."""
    patient_email = request.form.get('patient_email', '').strip()
    if not patient_email:
        flash('Please enter a patient email.', 'error')
        return redirect(url_for('caregiver_dashboard'))

    patient = query_db(
        "SELECT id, name FROM users WHERE email = ? AND role = 'patient'",
        (patient_email,), one=True
    )
    if not patient:
        flash('No patient account found with that email.', 'error')
        return redirect(url_for('caregiver_dashboard'))

    # Check if already monitoring
    existing = query_db(
        'SELECT id FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
        (session['user_id'], patient['id']), one=True
    )
    if existing:
        flash(f'You are already monitoring {patient["name"]}.', 'error')
        return redirect(url_for('caregiver_dashboard'))

    # Check if request already pending
    pending = query_db(
        "SELECT id FROM caregiver_requests WHERE caregiver_id = ? AND patient_id = ? AND status = 'pending'",
        (session['user_id'], patient['id']), one=True
    )
    if pending:
        flash(f'You already have a pending request for {patient["name"]}.', 'error')
        return redirect(url_for('caregiver_dashboard'))

    execute_db(
        'INSERT INTO caregiver_requests (caregiver_id, patient_id) VALUES (?, ?)',
        (session['user_id'], patient['id'])
    )

    flash(f'Request sent to monitor {patient["name"]}. Waiting for approval from patient or their doctor.', 'success')
    return redirect(url_for('caregiver_dashboard'))


@app.route('/api/caregiver-request/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_caregiver_request(request_id):
    """Approve a caregiver monitoring request. Can be done by patient or their doctor."""
    req = query_db('SELECT * FROM caregiver_requests WHERE id = ? AND status = ?', (request_id, 'pending'), one=True)
    if not req:
        flash('Request not found or already resolved.', 'error')
        return redirect(request.referrer or url_for('landing'))

    # Verify the approver is either the patient or the patient's doctor
    user_id = session['user_id']
    role = session.get('role')
    patient_id = req['patient_id']

    authorized = False
    if role == 'patient' and user_id == patient_id:
        authorized = True
    elif role == 'doctor':
        assignment = query_db(
            'SELECT id FROM doctor_patient WHERE doctor_id = ? AND patient_id = ?',
            (user_id, patient_id), one=True
        )
        if assignment:
            authorized = True

    if not authorized:
        flash('You are not authorized to approve this request.', 'error')
        return redirect(request.referrer or url_for('landing'))

    # Approve: update request and create caregiver_patient link
    execute_db(
        "UPDATE caregiver_requests SET status = 'approved', resolved_at = CURRENT_TIMESTAMP, resolved_by = ? WHERE id = ?",
        (user_id, request_id)
    )
    execute_db(
        'INSERT OR IGNORE INTO caregiver_patient (caregiver_id, patient_id, relationship) VALUES (?, ?, ?)',
        (req['caregiver_id'], patient_id, 'Approved Request')
    )

    flash('Caregiver request approved.', 'success')
    return redirect(request.referrer or url_for('landing'))


@app.route('/api/caregiver-request/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_caregiver_request(request_id):
    """Reject a caregiver monitoring request."""
    req = query_db('SELECT * FROM caregiver_requests WHERE id = ? AND status = ?', (request_id, 'pending'), one=True)
    if not req:
        flash('Request not found or already resolved.', 'error')
        return redirect(request.referrer or url_for('landing'))

    user_id = session['user_id']
    role = session.get('role')
    patient_id = req['patient_id']

    authorized = False
    if role == 'patient' and user_id == patient_id:
        authorized = True
    elif role == 'doctor':
        assignment = query_db(
            'SELECT id FROM doctor_patient WHERE doctor_id = ? AND patient_id = ?',
            (user_id, patient_id), one=True
        )
        if assignment:
            authorized = True

    if not authorized:
        flash('You are not authorized to reject this request.', 'error')
        return redirect(request.referrer or url_for('landing'))

    execute_db(
        "UPDATE caregiver_requests SET status = 'rejected', resolved_at = CURRENT_TIMESTAMP, resolved_by = ? WHERE id = ?",
        (user_id, request_id)
    )

    flash('Caregiver request rejected.', 'success')
    return redirect(request.referrer or url_for('landing'))


# ==================== ROLE SELECTION ====================

@app.route('/select-role')
def select_role():
    """Role Selection Screen"""
    return render_template('role_select.html')


# ==================== API ROUTES ====================

@app.route('/api/appointments', methods=['GET'])
@login_required
def get_appointments():
    """Get appointments for current user"""
    if session['role'] == 'doctor':
        appointments = query_db('''
            SELECT a.*, u.name as patient_name
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = ? AND a.status = 'scheduled'
            ORDER BY a.appointment_date, a.appointment_time
        ''', (session['user_id'],))
    else:
        appointments = query_db('''
            SELECT a.*, u.name as doctor_name
            FROM appointments a
            JOIN users u ON a.doctor_id = u.id
            WHERE a.patient_id = ? AND a.status = 'scheduled'
            ORDER BY a.appointment_date, a.appointment_time
        ''', (session['user_id'],))
    
    return jsonify([dict(a) for a in appointments] if appointments else [])


@app.route('/api/appointments', methods=['POST'])
@login_required
@role_required('doctor')
def create_appointment():
    """Create a new appointment"""
    data = request.get_json()
    
    patient_id = data.get('patient_id')
    appointment_date = data.get('appointment_date')
    appointment_time = data.get('appointment_time')
    duration = data.get('duration', 30)
    notes = data.get('notes', '')
    
    if not all([patient_id, appointment_date, appointment_time]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    room_id = f"rehab-{session['user_id']}-{patient_id}-{uuid.uuid4().hex[:8]}"
    
    appointment_id = execute_db('''
        INSERT INTO appointments 
        (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], patient_id, appointment_date, appointment_time, duration, notes, room_id))
    
    return jsonify({
        'success': True,
        'appointment_id': appointment_id,
        'room_id': room_id
    })


@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
@login_required
def cancel_appointment_api(appointment_id):
    """Cancel an appointment"""
    execute_db("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/complete', methods=['POST'])
@login_required
def complete_appointment(appointment_id):
    """Mark appointment as completed"""
    execute_db("UPDATE appointments SET status = 'completed' WHERE id = ?", (appointment_id,))
    
    # Check if this is an API call or form submission
    if request.is_json:
        return jsonify({'success': True})
    else:
        flash('Appointment marked as completed.', 'success')
        return redirect(url_for('consultation'))


@app.route('/api/remove-workout/<int:workout_id>', methods=['POST'])
@login_required
@role_required('doctor')
def remove_workout(workout_id):
    """Remove a workout from patient's plan"""
    execute_db('UPDATE workouts SET is_active = 0 WHERE id = ?', (workout_id,))
    flash('Exercise removed from plan.', 'success')
    return redirect(request.referrer or url_for('plan_editor'))


@app.route('/api/cancel-appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    """Cancel an appointment (form-based)"""
    execute_db("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    flash('Appointment cancelled.', 'success')
    return redirect(request.referrer or url_for('consultation'))


# ==================== OPTIMIZATION API (from computer_vision branch) ====================

@app.route('/api/optimize', methods=['POST'])
@login_required
def api_optimize():
    """Run appointment optimization for a single patient."""
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503
    
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    patient_id = data.get("patient_id")
    patients = data.get("patients")
    doctors = data.get("doctors")
    timeslots = data.get("timeslots")
    weights = data.get("weights")

    if not all([patient_id, patients, doctors, timeslots]):
        return jsonify({
            "error": "Missing required fields: patient_id, patients, doctors, timeslots"
        }), 400

    recs, notification = get_top3_recommendations(
        patient_id=patient_id,
        patients=patients,
        doctors=doctors,
        timeslots=timeslots,
        weights=weights,
    )

    return jsonify({
        "patient_id": patient_id,
        "recommendations": recs,
        "notification": notification,
    })


@app.route('/api/optimize/all', methods=['POST'])
@login_required
def api_optimize_all():
    """Run appointment optimization for all patients."""
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503
    
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    patients = data.get("patients")
    doctors = data.get("doctors")
    timeslots = data.get("timeslots")
    weights = data.get("weights")

    if not all([patients, doctors, timeslots]):
        return jsonify({
            "error": "Missing required fields: patients, doctors, timeslots"
        }), 400

    results = optimize_all_patients(
        patients=patients,
        doctors=doctors,
        timeslots=timeslots,
        weights=weights,
    )

    return jsonify({"results": results})


@app.route('/api/optimize/demo', methods=['GET'])
def api_optimize_demo():
    """Run optimization with real database data."""
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503
    
    patients, doctors, timeslots = load_optimization_data()
    results = optimize_all_patients(patients, doctors, timeslots)
    return jsonify({"results": results})


@app.route('/api/optim/status', methods=['GET'])
def api_optim_status():
    """Health check endpoint to see optimization data status."""
    try:
        from database import load_optimization_data
        patients, doctors, timeslots = load_optimization_data()
        
        return jsonify({
            "status": "ok",
            "patients_count": len(patients),
            "doctors_count": len(doctors),
            "timeslots_count": len(timeslots),
            "sample_patient": patients[0] if patients else None,
            "sample_doctor": doctors[0] if doctors else None,
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500



@app.route('/api/optimize/consultation', methods=['GET'])
@login_required
def api_optimize_consultation():
    """Return patient list + per-patient optimization results for the
    consultation scheduling page.

    Uses real database data from registered users.
    """
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503

    try:
        # Get current doctor info
        doctor_user = get_current_user()
        if doctor_user['role'] != 'doctor':
            return jsonify({"error": "Only doctors can access this endpoint"}), 403
        
        doctor_id = session['user_id']
        
        # Load real data from database
        patients, doctors, timeslots = load_optimization_data()
        
        print(f"[CONSULTATION API] Doctor {doctor_id} loading recommendations")
        print(f"[CONSULTATION API] Loaded {len(patients)} patients, {len(doctors)} doctors, {len(timeslots)} timeslots")
        
        # Get current doctor's info
        current_doctor = None
        for d in doctors:
            if int(d['id']) == doctor_id:
                current_doctor = d
                break
        
        if not current_doctor:
            print(f"[CONSULTATION API] ERROR: Doctor {doctor_id} not found in doctors list")
            return jsonify({
                "error": "Doctor not found",
                "debug": f"Doctor {doctor_id} has not completed their profile (missing specialties or location)"
            }), 400
        
        print(f"[CONSULTATION API] Current doctor: {current_doctor['label']} with specialties {current_doctor.get('specialties')}")
        
        # Check if we have minimal required data
        if not patients or not doctors or not timeslots:
            error_msg = "Not enough data to generate recommendations"
            print(f"[CONSULTATION API] ERROR: {error_msg} - patients:{len(patients)}, doctors:{len(doctors)}, timeslots:{len(timeslots)}")
            return jsonify({
                "error": error_msg,
                "debug": {
                    "patients_count": len(patients),
                    "doctors_count": len(doctors),
                    "timeslots_count": len(timeslots),
                    "message": "Please ensure doctors and patients are registered with their locations set"
                }
            }), 400

        print(f"[CONSULTATION API] Running optimize_all_patients for {len(patients)} patients...")
        results = optimize_all_patients(patients, doctors, timeslots)
        
        # Count how many patients got recommendations
        recs_count = sum(1 for r in results.values() if r.get("recommendations") and len(r["recommendations"]) > 0)
        print(f"[CONSULTATION API] Complete: {recs_count}/{len(patients)} patients got recommendations")
        
        # Filter results to only show recommendations where current doctor is assigned
        filtered_results = {}
        for patient_id, result in results.items():
            recs = result.get("recommendations", [])
            # Filter recommendations to only those assigned to current doctor
            filtered_recs = [r for r in recs if int(r.get("doctor_id")) == doctor_id]
            if filtered_recs:
                filtered_results[patient_id] = {
                    "recommendations": filtered_recs,
                    "notification": result.get("notification")
                }
        
        print(f"[CONSULTATION API] After filtering: {len(filtered_results)} patients have recommendations for doctor {doctor_id}")

        patient_list = [
            {"id": p["id"], "label": p["label"], "score": p["score"]}
            for p in patients
        ]

        return jsonify({
            "patients": patient_list,
            "results": filtered_results,  # Only show this doctor's assignments
            "doctor_info": {
                "id": current_doctor["id"],
                "label": current_doctor["label"],
                "specialties": current_doctor.get("specialties", [])
            }
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] /api/optimize/consultation failed: {e}")
        print(traceback.format_exc())
        return jsonify({
            "error": "Failed to generate recommendations",
            "debug": str(e)
        }), 500


@app.route('/api/optimize/patient/<int:patient_id>', methods=['GET'])
@login_required
@role_required('doctor')
def api_optimize_patient(patient_id):
    """Return top 3 optimization suggestions for a specific patient."""
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503

    # Load real data from database
    patients, doctors, timeslots = load_optimization_data()
    # Find the patient
    patient = next((p for p in patients if p['id'] == str(patient_id)), None)
    if not patient:
        return jsonify({"error": "Patient not found in optimization data"}), 404

    recs, notification = get_top3_recommendations(
        patient_id=str(patient_id),
        patients=patients,
        doctors=doctors,
        timeslots=timeslots,
        weights=None
    )
    return jsonify({
        "patient_id": patient_id,
        "recommendations": recs,
        "notification": notification
    })


@app.route('/api/patient/recommendations', methods=['GET'])
@login_required
@role_required('patient')
def api_patient_recommendations():
    """Return optimized doctor/appointment recommendations for the logged-in patient."""
    if not OPTIM_AVAILABLE:
        return jsonify({"error": "Optimization module not available"}), 503

    try:
        patient_id = session['user_id']

        patient_data = query_db(
            'SELECT * FROM patients WHERE user_id = ?',
            (patient_id,),
            one=True
        )

        if not patient_data:
            return jsonify({"error": "Patient profile not found"}), 404

        # Load real data from database
        patients, doctors, timeslots = load_optimization_data()
        
        # Debug logging
        print(f"\n[DEBUG] Loaded {len(patients)} patients, {len(doctors)} doctors, {len(timeslots)} timeslots")
        print(f"[DEBUG] Looking for patient ID: {patient_id}")
        print(f"[DEBUG] Available patient IDs: {[p['id'] for p in patients]}")
        print(f"[DEBUG] Available doctors: {[(d['id'], d['label'], d['specialties']) for d in doctors]}")

        # Find the actual patient in the optimization data
        patient = next((p for p in patients if p['id'] == str(patient_id)), None)
        if not patient:
            return jsonify({
                "error": "Patient not found in system",
                "debug": {
                    "patient_id": str(patient_id),
                    "available_patients": [p['id'] for p in patients]
                }
            }), 404
        
        print(f"[DEBUG] Patient data: specialty_need={patient.get('specialty_need')}, max_dist={patient.get('max_dist')}")

        recs, notification = get_top3_recommendations(
            patient_id=str(patient_id),
            patients=patients,
            doctors=doctors,
            timeslots=timeslots,
            weights=None
        )
        
        print(f"[DEBUG] Got {len(recs)} recommendations")
        if recs:
            print(f"[DEBUG] First rec: {recs[0]}")

        return jsonify({
            "recommendations": recs,
            "notification": notification
        })
    except Exception as e:
        import traceback
        print(f'[ERROR] Patient recommendations failed: {e}')
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/patient/update-preferences', methods=['POST'])
@login_required
@role_required('patient')
def api_patient_update_preferences():
    """Update patient scheduling preferences."""
    try:
        data = request.get_json()
        patient_id = session['user_id']
        
        urgency = data.get('urgency', 'Medium')
        max_distance = float(data.get('max_distance', 20))
        pincode = data.get('pincode', '')
        time_prefs = data.get('time_preferences', [])
        
        # Update patient record
        execute_db('''
            UPDATE patients 
            SET urgency = ?, max_distance = ?, address = ?
            WHERE user_id = ?
        ''', (urgency, max_distance, pincode, patient_id))
        
        # Update time preferences based on selection
        # Get all timeslots
        timeslots = query_db('SELECT id FROM timeslots')
        
        for ts in timeslots:
            ts_id = ts['id']
            # Determine preference score based on time of day
            pref_score = 0.5  # Default
            
            if 'morning' in time_prefs:
                if '_9am' in ts_id or '_10am' in ts_id or '_11am' in ts_id:
                    pref_score = 0.9
            
            if 'afternoon' in time_prefs:
                if '_1pm' in ts_id or '_2pm' in ts_id or '_3pm' in ts_id or '_4pm' in ts_id:
                    pref_score = 0.9
            
            # Update or insert preference
            execute_db('''
                INSERT INTO patient_time_preferences (patient_id, timeslot_id, preference_score)
                VALUES (?, ?, ?)
                ON CONFLICT(patient_id, timeslot_id) 
                DO UPDATE SET preference_score = ?
            ''', (patient_id, ts_id, pref_score, pref_score))
        
        return jsonify({
            "success": True,
            "message": "Preferences updated successfully"
        })
    except Exception as e:
        print(f'[ERROR] Update preferences failed: {e}')
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ==================== CV/ML LIVE FEEDBACK API (from computer_vision branch) ====================

# Global/session state for CV feedback
SESSION_STATE = {
    "scores": [],
    "threshold": 30.0,
    "cooldown_until": 0
}

# Initialize the CV pipeline
try:
    PIPELINE = WebRehabPipeline()
    print("[INIT] WebRehabPipeline initialized successfully")
except Exception as e:
    PIPELINE = None
    print(f"[WARNING] WebRehabPipeline failed to initialize: {e}")


# ==================== SESSION LIFECYCLE APIs ====================

@app.route('/api/session/create', methods=['POST'])
@login_required
@role_required('patient')
def api_session_create():
    """Create a new session record. Returns the session_id."""
    import json as _json
    data = request.get_json(force=True) or {}
    pain_before = int(data.get('pain_before', 0))

    # Create a unique session_group_id so we can group exercises
    group_id = str(uuid.uuid4())

    execute_db('''
        INSERT INTO sessions (patient_id, session_group_id, pain_before, started_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (session['user_id'], group_id, pain_before))

    row = query_db(
        'SELECT id FROM sessions WHERE patient_id = ? AND session_group_id = ?',
        (session['user_id'], group_id), one=True
    )
    if not row:
        return jsonify({'ok': False, 'error': 'Failed to create session'}), 500

    return jsonify({'ok': True, 'session_id': row['id']})


@app.route('/api/session/exercise/save', methods=['POST'])
@login_required
@role_required('patient')
def api_session_exercise_save():
    """Save data for one exercise within a session."""
    import json as _json
    data = request.get_json(force=True) or {}

    session_id = data.get('session_id')
    workout_id = data.get('workout_id')
    if not session_id or not workout_id:
        return jsonify({'ok': False, 'error': 'session_id and workout_id are required'}), 400

    quality_score = float(data.get('quality_score', 0))
    exercise_name = data.get('exercise_name', '')  # Get user-selected exercise name
    sets_required = _json.dumps(data.get('sets_required', {}))
    sets_completed = _json.dumps(data.get('sets_completed', {}))
    exercise_start_time = data.get('exercise_start_time')
    exercise_end_time = data.get('exercise_end_time')

    execute_db('''
        INSERT INTO session_exercises
            (session_id, patient_id, workout_id, exercise_name, exercise_start_time, exercise_end_time,
             quality_score, sets_required, sets_completed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, session['user_id'], workout_id, exercise_name,
          exercise_start_time, exercise_end_time,
          quality_score, sets_required, sets_completed))

    return jsonify({'ok': True})


@app.route('/api/session/complete', methods=['POST'])
@login_required
@role_required('patient')
def api_session_complete():
    """Complete a session — save post-session data and update patient stats."""
    import json as _json
    data = request.get_json(force=True) or {}

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'ok': False, 'error': 'session_id is required'}), 400

    pain_after = int(data.get('pain_after', 0))
    effort_level = int(data.get('effort_level', 5))
    notes = data.get('notes', '')

    # Calculate overall quality from exercise scores
    exercises = query_db(
        'SELECT quality_score, sets_required, sets_completed FROM session_exercises WHERE session_id = ?',
        (session_id,)
    )
    total_quality = 0
    total_req = 0
    total_comp = 0
    count = 0
    for ex in (exercises or []):
        total_quality += float(ex['quality_score'] or 0)
        count += 1
        req = _json.loads(ex['sets_required']) if ex['sets_required'] else {}
        comp = _json.loads(ex['sets_completed']) if ex['sets_completed'] else {}
        total_req += sum(int(v) for v in req.values())
        total_comp += sum(int(v) for v in comp.values())

    avg_quality = round(total_quality / count, 1) if count > 0 else 0
    completed_perc = round(total_comp / total_req * 100, 1) if total_req > 0 else 0

    execute_db('''
        UPDATE sessions
        SET pain_after = ?, effort_level = ?, notes = ?,
            quality_score = ?, completed_perc = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ? AND patient_id = ?
    ''', (pain_after, effort_level, notes, avg_quality, completed_perc,
          session_id, session['user_id']))

    # Update patient stats
    try:
        stats = query_db('''
            SELECT AVG(quality_score) as avg_q, AVG(pain_after) as avg_p, COUNT(*) as cnt
            FROM sessions
            WHERE patient_id = ? AND completed_at IS NOT NULL
        ''', (session['user_id'],), one=True)
        if stats:
            execute_db('''
                UPDATE patients
                SET avg_quality_score = ?, avg_pain_level = ?
                WHERE user_id = ?
            ''', (round(float(stats['avg_q'] or 0), 1),
                  round(float(stats['avg_p'] or 0), 1),
                  session['user_id']))
    except Exception as e:
        print(f"[WARN] Could not update patient stats: {e}")

    return jsonify({'ok': True, 'session_id': session_id})


old_route = """
@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    data = request.get_json(force=True) or {}
    threshold = float(data.get("threshold", 30.0))
    exercise_name = data.get("exercise_name", "exercise")
    cooldown_seconds = float(data.get("cooldown_seconds", 10.0))

    PIPELINE.reset(threshold=threshold, exercise_name=exercise_name, cooldown_seconds=cooldown_seconds)
    return jsonify({"ok": True, "threshold": threshold, "exercise_name": exercise_name})
"""

@app.route("/api/session/start_v1", methods=["POST"])
def api_session_start_v1():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True) or {}

    # Normalize language (frontend can send "English", "en", etc.)
    lang = (data.get("language") or "en").strip()
    if lang.lower() in ["english", "en-us", "en-gb"]:
        lang = "en"

    threshold = float(data.get("threshold", 30.0))
    cooldown = float(data.get("cooldown_seconds", 10.0))

    # If you still want to keep session info for UI/debug
    SESSION_STATE["language"] = lang
    SESSION_STATE["exercise_name"] = "AUTO"   # server will detect per-frame

    # IMPORTANT: reset without exercise_name
    PIPELINE.reset(
        threshold=threshold,
        cooldown_seconds=cooldown,
        language=lang,
    )

    return jsonify({
        "ok": True,
        "threshold": threshold,
        "cooldown_seconds": cooldown,
        "language": lang,
        "exercise_name": "AUTO"
    })



@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    target_reps = data.get("target_reps", 10)
    target_sets = data.get("target_sets", 3)
    
    PIPELINE.reset(
        threshold=data.get("threshold", 30.0),
        cooldown_seconds=data.get("cooldown_seconds", 10.0),
        language=data.get("language", "English"),
    )
    
    # Set the target reps and sets for rep counting
    PIPELINE.target_reps = target_reps
    PIPELINE.target_sets = target_sets
    PIPELINE.current_rep_count = 0
    PIPELINE.current_set_count = 1
    
    print(f"🎯 Session started with target_reps={target_reps}, target_sets={target_sets}")
    return jsonify({"ok": True})

@app.route("/api/session/start_old", methods=["POST"])
def api_session_start_old():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    #data = request.get_json(force=True) or {}
    #threshold = float(data.get("threshold", 25.0))

    #exercise_name = data.get("exercise_name", "exercise")
    #cooldown_seconds = float(data.get("cooldown_seconds", 10.0))
    #language = data.get("language", "en")
    #exercise_name = data.get("exercise_name", "squat")
    
    #PIPELINE.start_session(threshold=threshold, exercise_name=exercise_name, cooldown_seconds=cooldown_seconds, language=language)

    #PIPELINE.reset(threshold=threshold, exercise_name=exercise_name, cooldown_seconds=cooldown_seconds)
    #return jsonify({"ok": True, "threshold": threshold, "exercise_name": exercise_name, "cooldown_seconds": cooldown_seconds})
    data = request.get_json(force=True) or {}
    SESSION_STATE["language"] = data.get("language", "English")
    SESSION_STATE["exercise_name"] = data.get("exercise_name", "idle")

    PIPELINE.reset(
        threshold=data.get("threshold", 30.0),
        #exercise_name=data.get("exercise_name", "exercise"),
        cooldown_seconds=data.get("cooldown_seconds", 10.0),
        language=data.get("language", "english")
    )
    return jsonify({"ok": True})

old_routes = """
@app.route("/api/live_feedback", methods=["POST"])
def api_live_feedback():
    data = request.get_json(force=True) or {}
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"error": "frame_b64 missing"}), 400

    out = PIPELINE.process_frame_dataurl(frame_b64)
    return jsonify(out)
"""

old_code = """
@app.route("/api/live_feedback", methods=["POST"])
def api_live_feedback():
    #Input: { "frame_b64": "data:image/jpeg;base64,...." }
    #Output: score + form status + feedback list
    
    data = request.get_json(force=True)
    frame_b64 = data["frame_b64"]

    # 1) decode frame -> np array (BGR)
    # Extract base64 string from data URL
    header, encoded = frame_b64.split(',', 1)
    frame_data = base64.b64decode(encoded)
    frame_array = np.frombuffer(frame_data, np.uint8)
    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

        # 2) extract pose -> features
        X = pose_to_kimore_like_features(frame)

        # 3) model predict -> score in 0..50
        score = float(model_predict_score(X))
        SESSION_STATE["scores"].append(score)

        # 4) form status
        status = "CORRECT" if score >= SESSION_STATE["threshold"] else "WRONG"

        # 5) LLM feedback only if wrong
        feedback = []
        if status == "WRONG":
            feedback = get_llm_feedback(frame)

        return jsonify({
            "frame_score": round(score, 2),
            "form_status": status,
            "llm_feedback": feedback
        })
    except ImportError:
        # CV modules not available - return mock response for testing
        return jsonify({
            "frame_score": 35.0,
            "form_status": "CORRECT",
            "llm_feedback": [],
            "warning": "CV modules not installed - returning mock data"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
"""

# ==================== MERILION CHATBOT API ====================

@app.route('/api/chat/clear', methods=['POST'])
@login_required
def api_chat_clear():
    """Clear chat history from server session."""
    session.pop('chat_history', None)
    session.modified = True
    return jsonify({"ok": True})


@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """MeriLion AI chatbot endpoint for patient/caregiver use."""
    if not CHATBOT_AVAILABLE:
        return jsonify({"error": "Chatbot modules not available"}), 503

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Missing 'message' field"}), 400

    message = data['message']

    # Use server-side session to persist conversation history across page navigations
    if 'chat_history' not in session:
        session['chat_history'] = []
    conversation_history = session['chat_history']
    role = session.get('role')
    user_id = session['user_id']

    # Determine which patient we're chatting about
    if role == 'patient':
        patient_id = user_id
    elif role == 'caregiver':
        # Caregiver must specify which patient they're asking about
        patient_id = data.get('patient_id')
        if not patient_id:
            return jsonify({"error": "Caregiver must specify patient_id"}), 400
        # Verify caregiver has access to this patient
        access = query_db(
            'SELECT id FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
            (user_id, patient_id), one=True
        )
        if not access:
            return jsonify({"error": "You do not have access to this patient"}), 403
    else:
        return jsonify({"error": "Chat is available for patients and caregivers only"}), 403

    try:
        # 1. Detect language
        try:
            lang = detect_language(message)
            # langdetect returns 'id' for Malay/Indonesian — treat as Malay
            if lang in ("id", "ms"):
                lang_key = "ms"
            elif "zh" in lang:
                lang_key = "zh"
            elif lang == "ta":
                lang_key = "ta"
            else:
                lang_key = "en"
        except Exception:
            lang_key = "en"

        # 2. Build patient context from rehab_coach.db
        patient_user = query_db('SELECT * FROM users WHERE id = ?', (patient_id,), one=True)
        patient_info = query_db('SELECT * FROM patients WHERE user_id = ?', (patient_id,), one=True)
        recent_sessions_db = query_db('''
            SELECT s.*, e.name as exercise_name
            FROM sessions s
            JOIN session_exercises se ON se.session_id = s.id
            JOIN workouts w ON se.workout_id = w.id
            JOIN exercises e ON w.exercise_id = e.id
            WHERE s.patient_id = ?
            ORDER BY s.completed_at DESC
            LIMIT 5
        ''', (patient_id,))

        # Build context string for MeriLion
        patient_context = "New patient - no history available."
        if patient_user and patient_info:
            patient_context = f"""
Name: {patient_user['name']}
Condition: {patient_info['condition']}
Week: {patient_info['current_week']}
Adherence Rate: {patient_info['adherence_rate']}%
Avg Pain Level: {patient_info['avg_pain_level']}/10
Avg Quality Score: {patient_info['avg_quality_score']}/100
"""
            if recent_sessions_db:
                patient_context += "\nRecent Sessions:\n"
                for s in recent_sessions_db:
                    patient_context += f"- {s['exercise_name']}: Quality {s['quality_score']}, Pain {s['pain_after']}/10 ({s['completed_at']})\n"

        # Get workouts for exercise plan context
        workouts = query_db('''
            SELECT e.name FROM workouts w
            JOIN exercises e ON w.exercise_id = e.id
            WHERE w.patient_id = ? AND w.is_active = 1
        ''', (patient_id,))
        current_plan = ", ".join([w['name'] for w in workouts]) if workouts else "general fitness plan"

        # 3. Risk scoring - build simple session objects for the risk engine
        class SimpleSession:
            def __init__(self, pain):
                self.pain_reported = pain

        risk_sessions = []
        if recent_sessions_db:
            for s in recent_sessions_db[:3]:
                pain_val = s['pain_after']
                risk_sessions.append(SimpleSession(str(pain_val) if pain_val and pain_val > 3 else "none"))

        risk = calculate_risk_score(message, lang_key, risk_sessions)

        # 4. If high risk — return referral immediately
        if risk["should_refer"]:
            referral_msg = REFERRAL_MESSAGES.get(lang_key, REFERRAL_MESSAGES["en"])
            session['chat_history'] = conversation_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": referral_msg}
            ]
            session.modified = True
            return jsonify({
                "response": referral_msg,
                "risk_score": risk["score"],
                "referred": True,
                "language": lang_key
            })

        # 5. Check for pain + exercise context
        pain_keywords = ["pain", "hurts", "sore", "ache", "sakit", "疼", "வலி"]
        exercise_keywords = ["exercise", "workout", "training", "latihan", "运动", "உடற்பயிற்சி"]
        message_lower = message.lower()

        if any(p in message_lower for p in pain_keywords) and any(e in message_lower for e in exercise_keywords):
            body_parts = ["knee", "back", "shoulder", "ankle", "hip", "neck", "wrist", "elbow"]
            pain_area = "general"
            for part in body_parts:
                if part in message_lower:
                    pain_area = part
                    break
            modification = get_exercise_modification(pain_area, current_plan)
            conversation_history.append({"role": "system", "content": f"Exercise context: {modification}"})

        # 6. Add caregiver context if applicable
        if role == 'caregiver':
            patient_context += f"\n[Note: This conversation is with a caregiver, not the patient directly. Provide information appropriate for a family caregiver.]"

        # 6.5. RAG retrieval — enrich with rehabilitation knowledge
        rag_context = ""
        try:
            from rag_engine import retrieve
            rag_context = retrieve(message, top_k=3)
        except Exception as rag_err:
            print(f"[WARN] RAG retrieval skipped: {rag_err}")

        # 7. Query MeriLion
        full_history = conversation_history + [{"role": "user", "content": message}]
        response_text = query_merilion_sync(full_history, patient_context, rag_context, lang_key)

        # 8. Save conversation to server-side session (keep last 20 messages)
        session['chat_history'] = conversation_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_text}
        ]
        if len(session['chat_history']) > 20:
            session['chat_history'] = session['chat_history'][-20:]
        session.modified = True

        return jsonify({
            "response": response_text,
            "risk_score": risk["score"],
            "referred": False,
            "language": lang_key
        })

    except Exception as e:
        print(f"[ERROR] Chat API failed: {traceback.format_exc()}")
        return jsonify({"error": f"Chat service error: {str(e)}"}), 500


# ==================== DATABASE INITIALIZATION ====================

@app.cli.command('init-db')
def init_db_command():
    """CLI command to initialize database: flask init-db"""
    from database import init_db
    init_db(app)
    print('Database initialized!')


def ensure_tables_exist():
    """Create tables if they don't exist (safe - no data loss)"""
    import sqlite3
    conn = sqlite3.connect('rehab_coach.db')
    cursor = conn.cursor()
    
    # Create tables only if they don't exist (preserves existing data)
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('doctor', 'patient', 'caregiver')),
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            condition TEXT NOT NULL,
            surgery_date DATE,
            current_week INTEGER DEFAULT 1,
            adherence_rate REAL DEFAULT 0,
            avg_pain_level REAL DEFAULT 0,
            avg_quality_score REAL DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS doctor_patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            assigned_date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            UNIQUE(doctor_id, patient_id)
        );
        
        CREATE TABLE IF NOT EXISTS caregiver_patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            relationship TEXT,
            FOREIGN KEY (caregiver_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            UNIQUE(caregiver_id, patient_id)
        );
        
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            difficulty INTEGER DEFAULT 1,
            video_url TEXT
        );
        
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            sets INTEGER DEFAULT 3,
            reps INTEGER DEFAULT 10,
            frequency TEXT DEFAULT 'Daily',
            instructions TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            session_group_id TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            pain_before INTEGER DEFAULT 0,
            pain_after INTEGER DEFAULT 0,
            effort_level INTEGER DEFAULT 5,
            quality_score REAL DEFAULT 0,
            completed_perc REAL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS session_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            workout_id INTEGER NOT NULL,
            exercise_start_time TIMESTAMP,
            exercise_end_time TIMESTAMP,
            quality_score REAL DEFAULT 0,
            sets_required TEXT DEFAULT '{}',
            sets_completed TEXT DEFAULT '{}',
            exercise_name TEXT DEFAULT '',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (workout_id) REFERENCES workouts(id)
        );
        
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TEXT NOT NULL,
            duration INTEGER DEFAULT 30,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            room_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS clinician_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            note_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS caregiver_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolved_by INTEGER,
            FOREIGN KEY (caregiver_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (resolved_by) REFERENCES users(id)
        );
    ''')
    conn.commit()
    
    # --- Migrations for existing databases ---
    # Add new columns to sessions table if upgrading from old schema
    migrations = [
        ("sessions", "session_group_id", "TEXT"),
        ("sessions", "started_at", "TIMESTAMP"),
        ("sessions", "completed_perc", "REAL DEFAULT 0"),
    ]
    for table, col, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Create session_exercises table if it doesn't exist (for upgrades)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            workout_id INTEGER NOT NULL,
            exercise_start_time TIMESTAMP,
            exercise_end_time TIMESTAMP,
            quality_score REAL DEFAULT 0,
            sets_required TEXT DEFAULT '{}',
            sets_completed TEXT DEFAULT '{}',
            exercise_name TEXT DEFAULT '',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (workout_id) REFERENCES workouts(id)
        )
    ''')
    
    # Create optimization tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timeslots (
            id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            time TEXT NOT NULL,
            time_index INTEGER NOT NULL,
            label TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_specialties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            specialty TEXT NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            UNIQUE(doctor_id, specialty)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            timeslot_id TEXT NOT NULL,
            available INTEGER DEFAULT 1,
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
            UNIQUE(doctor_id, timeslot_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL UNIQUE,
            clinic_name TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (doctor_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            timeslot_id TEXT NOT NULL,
            available INTEGER DEFAULT 1,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
            UNIQUE(patient_id, timeslot_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_time_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            timeslot_id TEXT NOT NULL,
            preference_score REAL DEFAULT 0.5,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
            UNIQUE(patient_id, timeslot_id)
        )
    ''')
    
    # Add optimization columns to patients table if they don't exist
    optimization_columns = [
        ("patients", "urgency", "TEXT DEFAULT 'Medium' CHECK(urgency IN ('Low', 'Medium', 'High'))"),
        ("patients", "max_distance", "REAL DEFAULT 20.0"),
        ("patients", "specialty_needed", "TEXT"),
        ("patients", "preferred_doctor_id", "INTEGER REFERENCES users(id)"),
        ("patients", "address", "TEXT"),
        ("patients", "latitude", "REAL"),
        ("patients", "longitude", "REAL"),
    ]
    for table, col, col_type in optimization_columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Initialize timeslots if empty
    cursor.execute("SELECT COUNT(*) as cnt FROM timeslots")
    count_result = cursor.fetchone()
    timeslot_count = count_result[0] if count_result else 0
    if timeslot_count == 0:
        print("[INIT] Initializing timeslots...")
        timeslot_data = [
            ('mon_9am', 'Monday', '9:00 AM', 0, 'Mon 9:00 AM'),
            ('mon_10am', 'Monday', '10:00 AM', 1, 'Mon 10:00 AM'),
            ('mon_11am', 'Monday', '11:00 AM', 2, 'Mon 11:00 AM'),
            ('mon_1pm', 'Monday', '1:00 PM', 3, 'Mon 1:00 PM'),
            ('mon_2pm', 'Monday', '2:00 PM', 4, 'Mon 2:00 PM'),
            ('mon_3pm', 'Monday', '3:00 PM', 5, 'Mon 3:00 PM'),
            ('mon_4pm', 'Monday', '4:00 PM', 6, 'Mon 4:00 PM'),
            ('tue_9am', 'Tuesday', '9:00 AM', 7, 'Tue 9:00 AM'),
            ('tue_10am', 'Tuesday', '10:00 AM', 8, 'Tue 10:00 AM'),
            ('tue_11am', 'Tuesday', '11:00 AM', 9, 'Tue 11:00 AM'),
            ('tue_1pm', 'Tuesday', '1:00 PM', 10, 'Tue 1:00 PM'),
            ('tue_2pm', 'Tuesday', '2:00 PM', 11, 'Tue 2:00 PM'),
            ('tue_3pm', 'Tuesday', '3:00 PM', 12, 'Tue 3:00 PM'),
            ('tue_4pm', 'Tuesday', '4:00 PM', 13, 'Tue 4:00 PM'),
            ('wed_9am', 'Wednesday', '9:00 AM', 14, 'Wed 9:00 AM'),
            ('wed_10am', 'Wednesday', '10:00 AM', 15, 'Wed 10:00 AM'),
            ('wed_11am', 'Wednesday', '11:00 AM', 16, 'Wed 11:00 AM'),
            ('wed_1pm', 'Wednesday', '1:00 PM', 17, 'Wed 1:00 PM'),
            ('wed_2pm', 'Wednesday', '2:00 PM', 18, 'Wed 2:00 PM'),
            ('wed_3pm', 'Wednesday', '3:00 PM', 19, 'Wed 3:00 PM'),
            ('wed_4pm', 'Wednesday', '4:00 PM', 20, 'Wed 4:00 PM'),
            ('thu_9am', 'Thursday', '9:00 AM', 21, 'Thu 9:00 AM'),
            ('thu_10am', 'Thursday', '10:00 AM', 22, 'Thu 10:00 AM'),
            ('thu_11am', 'Thursday', '11:00 AM', 23, 'Thu 11:00 AM'),
            ('thu_1pm', 'Thursday', '1:00 PM', 24, 'Thu 1:00 PM'),
            ('thu_2pm', 'Thursday', '2:00 PM', 25, 'Thu 2:00 PM'),
            ('thu_3pm', 'Thursday', '3:00 PM', 26, 'Thu 3:00 PM'),
            ('thu_4pm', 'Thursday', '4:00 PM', 27, 'Thu 4:00 PM'),
            ('fri_9am', 'Friday', '9:00 AM', 28, 'Fri 9:00 AM'),
            ('fri_10am', 'Friday', '10:00 AM', 29, 'Fri 10:00 AM'),
            ('fri_11am', 'Friday', '11:00 AM', 30, 'Fri 11:00 AM'),
            ('fri_1pm', 'Friday', '1:00 PM', 31, 'Fri 1:00 PM'),
            ('fri_2pm', 'Friday', '2:00 PM', 32, 'Fri 2:00 PM'),
            ('fri_3pm', 'Friday', '3:00 PM', 33, 'Fri 3:00 PM'),
            ('fri_4pm', 'Friday', '4:00 PM', 34, 'Fri 4:00 PM'),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO timeslots (id, day, time, time_index, label) VALUES (?, ?, ?, ?, ?)",
            timeslot_data
        )
        print(f"[INIT] Created {len(timeslot_data)} timeslots")
    
    conn.commit()
    conn.close()


# Ensure tables exist on startup
ensure_tables_exist()

@app.route("/api/live_feedback_old", methods=["POST"])
def api_live_feedback_old():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    language = data.get("language", "en")
    exercise_name = data.get("exercise_name", "squat")
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"error": "frame_b64 missing"}), 400

    #out = PIPELINE.process_frame_dataurl(frame_b64)
    out = PIPELINE.process_frame_dataurl(frame_b64, language=language, exercise_name=exercise_name)
    return jsonify(out)

@app.route("/api/live_feedback_v1", methods=["POST"])
def api_live_feedback_v1():  # sourcery skip: use-contextlib-suppress
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True, silent=True) or {}

    # ---- 1) Inputs (body overrides server/session defaults) ----
    # If you have a SESSION_STATE dict from /api/session/start, use it.
    # Otherwise these fallbacks are fine.
    language = (data.get("language") or "").strip()
    exercise = (data.get("exercise") or "").strip()
    frame_b64 = data.get("frame_b64") or ""

    # Optional: fall back to session state if you maintain it
    try:
        if not language and "SESSION_STATE" in globals():
            language = (SESSION_STATE.get("language") or "").strip()
        if not exercise_name and "SESSION_STATE" in globals():
            exercise = (SESSION_STATE.get("exercise") or "").strip()
    except Exception:
        pass

    # Defaults
    if not exercise:
        exercise_name = "squat"
    if not language:
        language = "English"

    # ---- 2) Normalize language ----
    lang_map = {
        "en": "English",
        "english": "English",
        "ta": "Tamil",
        "tamil": "Tamil",
        "hi": "Hindi",
        "hindi": "Hindi",
        "ms": "Malay",
        "malay": "Malay",
        "zh": "Chinese",
        "chinese": "Chinese",
    }
    lang_key = language.lower()
    language = lang_map.get(lang_key, language)  # keep custom names too

    # ---- 3) Validate frame payload ----
    if not frame_b64 or not isinstance(frame_b64, str):
        return jsonify({"error": "frame_b64 missing"}), 400

    # Must look like: data:image/jpeg;base64,....
    if not frame_b64.startswith("data:image/"):
        return jsonify({"error": "frame_b64 must be a data URL like data:image/jpeg;base64,..."}), 400

    # ---- 4) Run pipeline safely ----
    try:
        # Your pipeline should accept these args (as you already changed)
        out = PIPELINE.process_frame_dataurl(
            frame_b64,
            language=language,
            exercise=exercise
        )

        # Ensure response always contains these keys so frontend doesn't break
        if "llm_feedback" not in out:
            out["llm_feedback"] = []
        if "form_status" not in out:
            out["form_status"] = "PROCESSING"
        if "frame_score" not in out:
            out["frame_score"] = 0

        out["language"] = language
        out["exercise"] = exercise
        return jsonify(out)

    except Exception as e:
        # Return 200 so UI polling doesn't die; surface error in feedback panel
        return jsonify({
            "form_status": "ERROR",
            "frame_score": 0,
            "llm_feedback": [f"Backend error: {type(e).__name__}: {str(e)}"],
            "language": language,
            "exercise": exercise
        })

@app.route("/api/live_feedback_v2", methods=["POST"])
def api_live_feedback_v2():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True, silent=True) or {}

    language = (data.get("language") or "English").strip()
    frame_b64 = data.get("frame_b64") or ""

    if not frame_b64 or not isinstance(frame_b64, str):
        return jsonify({"error": "frame_b64 missing"}), 400

    if not frame_b64.startswith("data:image/"):
        return jsonify({"error": "frame_b64 must be a data URL like data:image/jpeg;base64,..."}), 400

    # normalize language
    lang_map = {
        "en": "English", "english": "English",
        "ta": "Tamil", "tamil": "Tamil",
        "hi": "Hindi", "hindi": "Hindi",
        "ms": "Malay", "malay": "Malay",
        "zh": "Chinese", "chinese": "Chinese",
    }
    language = lang_map.get(language.lower(), language)

    try:
        # ✅ exercise is auto-detected inside pipeline
        out = PIPELINE.process_frame_dataurl(frame_b64, language=language)

        # make response stable for UI
        out.setdefault("llm_feedback", [])
        out.setdefault("form_status", "PROCESSING")
        out.setdefault("frame_score", 0)
        out["language"] = language

        # IMPORTANT: pipeline should set this
        out.setdefault("exercise_name", "idle")

        return jsonify(out)

    except Exception as e:
        return jsonify({
            "form_status": "ERROR",
            "frame_score": 0,
            "llm_feedback": [f"Backend error: {type(e).__name__}: {str(e)}"],
            "language": language,
            "exercise_name": "idle",
        })

@app.route("/api/live_feedback_v3", methods=["POST"])
def api_live_feedback_v3():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    language = data.get("language", "en")
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"error": "frame_b64 missing"}), 400

    # Pipeline should infer exercise_name internally and return it in output
    out = PIPELINE.process_frame_dataurl(frame_b64, language=language)

    return jsonify(out)

@app.route("/api/live_feedback", methods=["POST"])
def api_live_feedback():
    if PIPELINE is None:
        return jsonify({"error": "CV pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"error": "frame_b64 missing"}), 400

    # language comes from frontend/session
    language = data.get("language", "English")
    mode = data.get("mode", "auto")
    manual_exercise = data.get("manual_exercise", None)
    
    PIPELINE.language = language  # keep it simple
    
    try:
        out = PIPELINE.process_frame_dataurl(
            frame_b64,
            language=language,
            mode=mode,
            manual_exercise=manual_exercise
        )
        return jsonify(out)
    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({
            "frame_score": 0.0,
            "form_status": "ERROR",
            "llm_feedback": [f"Backend error: {str(e)}"],
            "exercise_name": "error",
            "exercise_confidence": 0.0,
            "rep_info": {
                "rep_now": 0,
                "rep_target": 10,
                "set_now": 1,
                "set_target": 3,
                "rep_incremented": False,
                "set_completed": False,
                "exercise_completed": False,
            },
        }), 500

@app.post("/api/session/stop")
def api_session_stop():  # sourcery skip: use-contextlib-suppress
    global PIPELINE
    if PIPELINE is None:
        return jsonify({"ok": True, "warning": "CV pipeline not available"})
    try:
        PIPELINE.reset()  # if you have it
    except Exception:
        pass
    return jsonify({"ok": True})

if __name__ == '__main__':
    #start_openpose_server()
    print("Database tables verified via ensure_tables_exist().")
    app.run(host="127.0.0.1", port=5050, debug=True)