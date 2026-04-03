import os
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TF"] = "0"
os.environ["KERAS_BACKEND"] = "torch"  # Use PyTorch backend (TF not supported on Python 3.14)
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Fall back to CPU for unsupported MPS ops

# Load environment variables from .env file (explicit path to ensure it loads)
from pathlib import Path
from dotenv import load_dotenv

# Load from explicit .env path in current directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Verify critical keys are loaded
_groq_key = os.environ.get("GROQ_API_KEY", "")
_meralion_key = os.environ.get("MERILION_API_KEY", "")
if not _groq_key:
    print("⚠️  WARNING: GROQ_API_KEY not found in .env - AI feedback may not work")
if not _meralion_key:
    print("⚠️  WARNING: MERILION_API_KEY not found in .env - Meralion API may not work")

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from Rehab_Scorer_Coach.src.web_pipeline import WebRehabPipeline
from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
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
    from merilion_client import query_merilion_sync, transcribe_audio, translate_text_sync
    from risk_engine import calculate_risk_score, REFERRAL_MESSAGES
    from exercise_advisor import get_exercise_modification
    from langdetect import detect as detect_language
    import traceback
    CHATBOT_AVAILABLE = True
    print("[INIT] Chatbot modules loaded successfully")
except Exception as e:
    CHATBOT_AVAILABLE = False
    print(f"[WARNING] Chatbot modules not available: {e}")

try:
    from whisper_transcriber import transcribe as whisper_transcribe
    WHISPER_AVAILABLE = True
    print("[INIT] Whisper STT (fal-ai) available")
except Exception as e:
    WHISPER_AVAILABLE = False
    print(f"[WARNING] Whisper STT not available: {e}")

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

try:
    from report_generator import generate_session_report
    REPORT_AVAILABLE = True
    print("[INIT] PDF report generator loaded")
except Exception as _re:
    REPORT_AVAILABLE = False
    print(f"[WARNING] PDF report generator not available: {_re}")

# ── Email notifications ──────────────────────────────────────────────────────
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_SENDER = os.environ.get("NOTIFY_EMAIL_SENDER", "spaamkumar81@gmail.com")
EMAIL_PASSWORD = os.environ.get("NOTIFY_EMAIL_PASSWORD", "")
EMAIL_ENABLED = bool(EMAIL_PASSWORD)

def _send_email(to_address: str, subject: str, body: str):
    """Send a plain-text email via Gmail SMTP. Silently skips if not configured."""
    if not EMAIL_ENABLED:
        print(f"[EMAIL] Skipped (no password configured): {subject} → {to_address}")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_address, msg.as_string())
        print(f"[EMAIL] Sent '{subject}' → {to_address}")
    except Exception as _e:
        print(f"[EMAIL] Failed to send to {to_address}: {_e}")

try:
    from reinjury_risk import analyze_patient_risk
    REINJURY_RISK_AVAILABLE = True
    print("[INIT] Re-injury risk engine loaded")
except Exception as _rr:
    REINJURY_RISK_AVAILABLE = False
    print(f"[WARNING] Re-injury risk engine not available: {_rr}")

try:
    from recovery_predictor import predict_recovery
    RECOVERY_PREDICTOR_AVAILABLE = True
    print("[INIT] Recovery timeline predictor loaded")
except Exception as _rp:
    RECOVERY_PREDICTOR_AVAILABLE = False
    print(f"[WARNING] Recovery predictor not available: {_rp}")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    print("[INIT] gTTS (Google TTS) loaded successfully")
except ImportError:
    GTTS_AVAILABLE = False
    print("[WARNING] gTTS not installed, only edge_tts available")


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
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Required for sessions

# ==================== CONDITIONS & EXERCISE MAPPING ====================

MSK_CONDITIONS = [
    'General Rehabilitation',
    'Spine & MSK',
    'Post-Surgical Recovery',
    'Sports Injury',
    'Neurological Rehab',
    'Orthopaedic Rehab',
]

# Doctor specialties use the same vocabulary as patient conditions
DOCTOR_SPECIALTIES = MSK_CONDITIONS

CONDITION_EXERCISE_MAP = {
    'Spine & MSK': [
        'Lateral Trunk Tilt',
        'Trunk Rotation',
        'Forward Flexion',
        'Flank Stretch',
        'Torso Rotation',
        'Trunk Rotation & Target Touch',
    ],
    'Orthopaedic Rehab': [
        'Squat',
        'Pelvis Rotation',
        'Lifting of Arms',
    ],
    'Post-Surgical Recovery': [
        'Lifting of Arms',
        'Squat',
        'Pelvis Rotation',
        'Trunk Rotation',
    ],
    'Sports Injury': [
        'Squat',
        'Pelvis Rotation',
        'Lifting of Arms',
    ],
    'General Rehabilitation': [
        'Lateral Trunk Tilt',
        'Trunk Rotation',
        'Torso Rotation',
        'Flank Stretch',
    ],
    'Neurological Rehab': [
        'Trunk Rotation & Target Touch',
        'Trunk Rotation',
        'Forward Flexion',
    ],
}

# Global dict to store latest landmarks for frontend polling
LATEST_LANDMARKS = {}

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


def get_primary_doctor_id_for_patient(patient_id: int):
    """Return the assigned doctor_id for a patient (if any)."""
    row = query_db(
        '''
        SELECT doctor_id
        FROM doctor_patient
        WHERE patient_id = ?
        ORDER BY assigned_date DESC, id DESC
        LIMIT 1
        ''',
        (patient_id,),
        one=True,
    )
    return row['doctor_id'] if row else None


def create_adaptive_suggestion(
    patient_id: int,
    source: str,
    reason: str,
    suggested_change: str,
    doctor_id_override=None,
    severity: str = "medium",
    session_id=None,
    workout_id=None,
    suggested_sets=None,
    suggested_reps=None,
    suggested_frequency=None,
    patient_note: str = "",
    app_confidence=None,
):
    """Create a pending adaptive rehab suggestion for doctor review."""
    doctor_id = doctor_id_override or get_primary_doctor_id_for_patient(patient_id)
    if not doctor_id:
        return None

    # Avoid flooding duplicates from repeated auto triggers
    duplicate = query_db(
        '''
        SELECT id
        FROM adaptive_plan_suggestions
        WHERE patient_id = ?
          AND doctor_id = ?
          AND source = ?
          AND reason = ?
          AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (patient_id, doctor_id, source, reason),
        one=True,
    )
    if duplicate:
        return duplicate['id']

    suggestion_id = execute_db(
        '''
        INSERT INTO adaptive_plan_suggestions (
            patient_id, doctor_id, session_id, workout_id,
            source, reason, suggested_change, severity,
            suggested_sets, suggested_reps, suggested_frequency,
            patient_note, app_confidence, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''',
        (
            patient_id,
            doctor_id,
            session_id,
            workout_id,
            source,
            reason,
            suggested_change,
            severity,
            suggested_sets,
            suggested_reps,
            suggested_frequency,
            patient_note,
            app_confidence,
        ),
    )
    return suggestion_id

# ── Edge-TTS voice maps (Microsoft Neural voices) ──
# Male voices for avatar & chatbot
EDGE_VOICE_MAP_MALE = {
    "English": "en-US-GuyNeural",
    "Singlish": "en-US-GuyNeural",
    "Tamil":   "ta-IN-ValluvarNeural",
    "Chinese": "zh-CN-YunxiNeural",
    "Malay":   "ms-MY-OsmanNeural",
    "Thai":    "th-TH-NiwatNeural",
}
# Female voices for session coaching prompts
EDGE_VOICE_MAP_FEMALE = {
    "English": "en-US-JennyNeural",
    "Singlish": "en-US-JennyNeural",
    "Tamil":   "ta-IN-PallaviNeural",
    "Chinese": "zh-CN-XiaoxiaoNeural",
    "Malay":   "ms-MY-YasminNeural",
    "Thai":    "th-TH-PremwadeeNeural",
}
# Default map (male) — kept for backward compat
EDGE_VOICE_MAP = EDGE_VOICE_MAP_MALE

# ── gTTS language codes (Google TTS) ──
GTTS_LANG_MAP = {
    "English": "en",
    "Singlish": "en",
    "Tamil":   "ta",
    "Chinese": "zh-CN",
    "Malay":   "ms",  # Malay not natively in gTTS, but 'ms' may work; fallback to 'id' (Indonesian) if needed
    "Thai":    "th",
}

def _tts_cache_path(text: str, language: str, engine: str = "edge") -> str:
    h = hashlib.md5(f"{engine}|{language}|{text}".encode("utf-8")).hexdigest()
    cache_dir = os.path.join(tempfile.gettempdir(), "rehab_tts_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{h}.mp3")

async def _edge_synth(text: str, voice: str, out_path: str):
    """Synthesise with Microsoft Edge neural voice."""
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)

def _gtts_synth(text: str, lang_code: str, out_path: str):
    """Synthesise with Google TTS (gTTS). Works offline-ish, very reliable for CJK + Tamil."""
    tts = gTTS(text=text, lang=lang_code, slow=False)
    tts.save(out_path)

@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(force=True) or {}

    text = (data.get("text") or "").strip()
    language = (data.get("language") or "English").strip()
    gender = (data.get("gender") or "male").strip().lower()   # "male" for avatar/chatbot, "female" for sessions

    if isinstance(text, list):
        text = ". ".join(text)

    if not text:
        return jsonify({"error": "text is required"}), 400

    # Translate if the TTS language differs from the source language
    source_language = (data.get("source_language") or "").strip()
    if source_language and source_language != language and CHATBOT_AVAILABLE:
        try:
            translated = translate_text_sync(text, language)
            if translated and translated.strip():
                text = translated.strip()
                print(f"[TTS] Translated from {source_language} to {language}")
        except Exception as e:
            print(f"[TTS] Translation failed, using original text: {e}")

    # ── Strategy: try edge_tts first → gTTS fallback → error ──
    # Step 1: Try edge_tts (higher quality neural voices)
    voice_map = EDGE_VOICE_MAP_FEMALE if gender == "female" else EDGE_VOICE_MAP_MALE
    edge_voice = voice_map.get(language, voice_map["English"])
    edge_path = _tts_cache_path(text, language + "_" + gender, "edge")

    if os.path.exists(edge_path):
        print(f"♻️  Cached edge TTS ({language})")
        return send_file(edge_path, mimetype="audio/mpeg", as_attachment=False)

    try:
        print(f"🔊 Edge-TTS generating: {language} ({edge_voice})")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            asyncio.wait_for(_edge_synth(text, edge_voice, edge_path), timeout=8.0)
        )
        loop.close()
        print(f"✅ Edge-TTS done for {language}")
        return send_file(edge_path, mimetype="audio/mpeg", as_attachment=False)
    except Exception as edge_err:
        print(f"⚠️  Edge-TTS failed ({language}): {edge_err}")
        # Clean up partial file if any
        if os.path.exists(edge_path):
            try: os.remove(edge_path)
            except: pass

    # Step 2: Fallback to gTTS (Google TTS) — especially reliable for non-English
    if GTTS_AVAILABLE:
        gtts_lang = GTTS_LANG_MAP.get(language, "en")
        gtts_path = _tts_cache_path(text, language, "gtts")

        if os.path.exists(gtts_path):
            print(f"♻️  Cached gTTS ({language})")
            return send_file(gtts_path, mimetype="audio/mpeg", as_attachment=False)

        try:
            print(f"🔊 gTTS generating: {language} (lang={gtts_lang})")
            _gtts_synth(text, gtts_lang, gtts_path)
            print(f"✅ gTTS done for {language}")
            return send_file(gtts_path, mimetype="audio/mpeg", as_attachment=False)
        except Exception as gtts_err:
            print(f"❌ gTTS also failed ({language}): {gtts_err}")
            if os.path.exists(gtts_path):
                try: os.remove(gtts_path)
                except: pass

    print(f"❌ All TTS engines failed for {language}")
    return jsonify({"error": "TTS service temporarily unavailable"}), 503


def _tts_to_base64(text: str, language: str = "English", gender: str = "male") -> str:
    """
    Generate TTS audio and return as base64-encoded MP3.
    Used for avatar voice responses.
    
    Args:
        text: Text to synthesize
        language: Language (English, Chinese, Malay, Tamil, Singlish)
        gender: Voice gender (male/female)
    
    Returns:
        Base64-encoded MP3 audio or error message
    """
    try:
        # Try edge_tts first
        voice_map = EDGE_VOICE_MAP_FEMALE if gender == "female" else EDGE_VOICE_MAP_MALE
        edge_voice = voice_map.get(language, voice_map["English"])
        edge_path = _tts_cache_path(text, language + "_" + gender, "edge")
        
        if os.path.exists(edge_path):
            with open(edge_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                asyncio.wait_for(_edge_synth(text, edge_voice, edge_path), timeout=8.0)
            )
            loop.close()
            
            with open(edge_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        except Exception as edge_err:
            print(f"[TTS] Edge-TTS failed: {edge_err}")
            if os.path.exists(edge_path):
                try: os.remove(edge_path)
                except: pass
        
        # Fallback to gTTS
        if GTTS_AVAILABLE:
            gtts_lang = GTTS_LANG_MAP.get(language, "en")
            gtts_path = _tts_cache_path(text, language, "gtts")
            
            if os.path.exists(gtts_path):
                with open(gtts_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            
            _gtts_synth(text, gtts_lang, gtts_path)
            with open(gtts_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        
        return ""  # Failed to generate TTS
    
    except Exception as e:
        print(f"[TTS-BASE64] Error: {e}")
        return ""


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
                # Login successful — clear any stale data from previous user first
                session.clear()
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
    
    # Store in session — clear stale data from previous user first
    session.clear()
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
            condition = request.form.get('condition', '').strip()
            # If no condition selected, assign a random one
            if not condition or condition not in MSK_CONDITIONS:
                condition = random.choice(MSK_CONDITIONS)
            urgency = request.form.get('urgency', 'Medium')
            max_distance = float(request.form.get('max_distance', 20))
            
            # Map condition to specialty needed
            condition_to_specialty = {
                'Joint disorders': 'Orthopedic',
                'Spine conditions': 'MSK',
                'Post-surgical rehab': 'Post-op',
                'Sports injuries': 'Sports',
                'Postural disorders': 'MSK',
                'Muscle tightness': 'General',
                'Neuromuscular rehab': 'Neuro',
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
                # No doctor selected — patient waits to be claimed by a specialist
                pass
            
            # Exercises NOT auto-assigned; doctor assigns via Plan Editor.
        
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
        
        # Patients go through the medical history step before the dashboard.
        # All other roles go to login as before.
        if role == 'patient':
            session['user_id'] = user_id
            session['role'] = role
            session['user_name'] = name
            flash('Account created! Tell us a bit about your medical history (optional).', 'info')
            return redirect(url_for('signup_medical_history'))

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
    
    # Get patient's workouts — only exercises actively assigned/enabled for this patient
    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.description
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        JOIN patient_exercises pe ON pe.patient_id = w.patient_id AND pe.exercise_id = w.exercise_id
        WHERE w.patient_id = ? AND w.is_active = 1 AND pe.enabled = 1
    ''', (session['user_id'],))

    # If no rows in workouts, build the list from patient_exercises (condition-based)
    if not workouts:
        workouts = query_db('''
            SELECT pe.id, pe.patient_id, pe.exercise_id,
                   e.name AS exercise_name, e.description,
                   3 AS sets, 10 AS reps,
                   'Daily' AS frequency,
                   e.description AS instructions,
                   1 AS is_active
            FROM patient_exercises pe
            JOIN exercises e ON pe.exercise_id = e.id
            WHERE pe.patient_id = ? AND pe.enabled = 1
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

    # Get upcoming appointments — future only
    upcoming_appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status = 'scheduled'
          AND a.appointment_date >= date('now')
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 3
    ''', (session['user_id'],))

    # Recent past appointments for dashboard (last 5)
    recent_past_appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status IN ('completed', 'missed', 'cancelled')
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 5
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

    adaptive_suggestions = query_db('''
        SELECT aps.*, u.name AS doctor_name
        FROM adaptive_plan_suggestions aps
        LEFT JOIN users u ON aps.doctor_id = u.id
        WHERE aps.patient_id = ?
        ORDER BY aps.created_at DESC
        LIMIT 10
    ''', (session['user_id'],))

    exercises_assigned = bool(workouts)

    return render_template('patient/dashboard.html',
                            user=user,
                            patient=patient_info,
                            exercises_assigned=exercises_assigned,
                            workouts=workouts if workouts else [],
                            recent_sessions=recent_sessions,
                            chart_sessions=chart_sessions if chart_sessions else [],
                            upcoming_appointments=upcoming_appointments if upcoming_appointments else [],
                            caregivers=caregivers if caregivers else [],
                            pending_caregiver_requests=pending_requests if pending_requests else [],
                            session_user_id=session['user_id'],
                            total_sessions=total_sessions['count'] if total_sessions else 0,
                            sessions_this_week=sessions_this_week['count'] if sessions_this_week else 0,
                            today_completed=today_completed,
                            today_session_id=today_session_id,
                            today_perc=today_perc,
                            adaptive_suggestions=adaptive_suggestions if adaptive_suggestions else [],
                            recent_past_appointments=recent_past_appointments if recent_past_appointments else [],
                            chat_patient_id=None)


@app.route('/patient/session')
@login_required
@role_required('patient')
def rehab_session():
    """Rehab Session Screen"""
    patient_id = session['user_id']

    # Auto-sync: ensure every enabled patient_exercise has a corresponding workouts row
    # (Workouts rows hold the clinician-set sets/reps; if none exists yet, create with defaults)
    assigned_pe = query_db('''
        SELECT pe.exercise_id FROM patient_exercises pe
        WHERE pe.patient_id = ? AND pe.enabled = 1
    ''', (patient_id,))
    assigned_ex_ids = [a['exercise_id'] for a in assigned_pe] if assigned_pe else []

    existing_workout_exids = query_db('''
        SELECT exercise_id FROM workouts
        WHERE patient_id = ? AND is_active = 1
    ''', (patient_id,))
    existing_ids = set(e['exercise_id'] for e in existing_workout_exids) if existing_workout_exids else set()

    for ex_id in assigned_ex_ids:
        if ex_id not in existing_ids:
            execute_db('''
                INSERT INTO workouts
                (patient_id, exercise_id, assigned_by_doctor_id, sets, reps, frequency, instructions, is_active)
                VALUES (?, ?, NULL, 3, 10, 'Daily', '', 1)
            ''', (patient_id, ex_id))

    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.description, e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        JOIN patient_exercises pe ON pe.patient_id = w.patient_id AND pe.exercise_id = w.exercise_id
        WHERE w.patient_id = ? AND w.is_active = 1 AND pe.enabled = 1
    ''', (patient_id,))

    # Get exercises assigned to this patient via patient_exercises
    assigned_exercises = query_db('''
        SELECT e.id, e.name as exercise_name, e.category, e.description
        FROM patient_exercises pe
        JOIN exercises e ON pe.exercise_id = e.id
        WHERE pe.patient_id = ? AND pe.enabled = 1
        ORDER BY e.category, e.name
    ''', (patient_id,))
    assigned_exercises = [dict(e) for e in assigned_exercises] if assigned_exercises else []

    # Get patient condition for the personalized plan card
    patient_info = query_db(
        'SELECT condition FROM patients WHERE user_id = ?',
        (patient_id,), one=True
    )
    patient_condition = patient_info['condition'] if patient_info and patient_info['condition'] else 'Your Condition'
    
    resp = make_response(render_template('patient/session.html',
                                         workouts=workouts if workouts else [],
                                         assigned_exercises=assigned_exercises,
                                         patient_condition=patient_condition))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/api/patient/exercises', methods=['GET'])
@login_required
@role_required('patient')
def api_patient_exercises():
    """Return the exercises assigned to the current patient."""
    exercises = query_db('''
        SELECT e.id, e.name as exercise_name, e.category, pe.enabled
        FROM patient_exercises pe
        JOIN exercises e ON pe.exercise_id = e.id
        WHERE pe.patient_id = ?
        ORDER BY e.category, e.name
    ''', (session['user_id'],))
    return jsonify([dict(e) for e in exercises] if exercises else [])


@app.route('/api/patient/exercises/toggle', methods=['POST'])
@login_required
@role_required('patient')
def api_toggle_patient_exercise():
    """Toggle an exercise enabled/disabled for the current patient."""
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    enabled = data.get('enabled', 1)
    if not exercise_id:
        return jsonify({'error': 'exercise_id required'}), 400
    execute_db(
        'UPDATE patient_exercises SET enabled = ? WHERE patient_id = ? AND exercise_id = ?',
        (1 if enabled else 0, session['user_id'], exercise_id)
    )
    return jsonify({'ok': True})


@app.route('/patient/checkin', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def pain_checkin():
    """Pain & Effort Check-In — now handled via JS API calls. Keep route for direct access."""
    return render_template('patient/checkin.html')


@app.route('/cam-test')
def cam_test():
    """Standalone camera diagnostic page"""
    return render_template('cam_test.html')


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

    # ── Recovery prediction ──
    recovery_data = None
    if RECOVERY_PREDICTOR_AVAILABLE:
        try:
            recovery_data = predict_recovery(session['user_id'], query_db)
        except Exception as _rp_err:
            print(f"[WARNING] Recovery prediction failed: {_rp_err}")

    return render_template('patient/summary.html',
                         session_data=sess,
                         exercises=exercises_list,
                         overall_duration=overall_duration,
                         session_id=session_id,
                         recovery=recovery_data)


# ==================== PDF SESSION REPORT DOWNLOAD ====================

@app.route('/api/session/report/<int:session_id>')
@login_required
@role_required('patient')
def api_session_report(session_id):
    """Generate and return a downloadable PDF report for a completed session."""
    import json as _json

    if not REPORT_AVAILABLE:
        return jsonify({"error": "PDF report module not available (install reportlab)"}), 503

    patient_id = session['user_id']

    # ── session metadata ────────────────────────────────────────────────
    sess = query_db(
        'SELECT * FROM sessions WHERE id = ? AND patient_id = ?',
        (session_id, patient_id), one=True,
    )
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    # ── patient info ────────────────────────────────────────────────────
    user_row = query_db('SELECT name FROM users WHERE id = ?', (patient_id,), one=True)
    patient_name = user_row['name'] if user_row else 'Patient'
    pat_row = query_db('SELECT condition FROM patients WHERE user_id = ?', (patient_id,), one=True)
    patient_condition = pat_row['condition'] if pat_row else 'General'

    # ── exercises ───────────────────────────────────────────────────────
    exercises_raw = query_db('''
        SELECT se.*, COALESCE(se.exercise_name, e.name) as exercise_name
        FROM session_exercises se
        LEFT JOIN workouts w ON se.workout_id = w.id
        LEFT JOIN exercises e ON w.exercise_id = e.id
        WHERE se.session_id = ?
        ORDER BY se.exercise_start_time
    ''', (session_id,))

    exercises_list = []
    for ex in (exercises_raw or []):
        req = _json.loads(ex['sets_required']) if ex['sets_required'] else {}
        comp = _json.loads(ex['sets_completed']) if ex['sets_completed'] else {}
        total_req = sum(int(v) for v in req.values())
        total_comp = sum(int(v) for v in comp.values())
        ex_perc = round(total_comp / total_req * 100, 1) if total_req > 0 else 0
        ex_duration = None
        if ex['exercise_start_time'] and ex['exercise_end_time']:
            try:
                st = datetime.fromisoformat(ex['exercise_start_time'])
                en = datetime.fromisoformat(ex['exercise_end_time'])
                ex_duration = int((en - st).total_seconds())
            except Exception:
                pass
        exercises_list.append({
            "exercise_name": ex['exercise_name'],
            "quality_score": ex['quality_score'],
            "completion_perc": ex_perc,
            "sets_required": req,
            "sets_completed": comp,
            "duration_seconds": ex_duration,
        })

    # ── overall duration ────────────────────────────────────────────────
    overall_duration = None
    if sess['started_at'] and sess['completed_at']:
        try:
            s = datetime.fromisoformat(sess['started_at'])
            e = datetime.fromisoformat(sess['completed_at'])
            overall_duration = int((e - s).total_seconds())
        except Exception:
            pass

    # ── frame-level telemetry ──────────────────────────────────────────
    frames_raw = query_db(
        'SELECT * FROM session_frames WHERE session_id = ? ORDER BY timestamp',
        (session_id,),
    )

    # Pass ALL frames to the report generator — the CV model may classify
    # the exercise differently from the user-selected name (e.g. "squat"
    # instead of "lifting_of_arms").  The report already handles skipping
    # idle/no_pose frames and merges DB scores from session_exercises.
    frames = list(frames_raw or [])

    # ── generate PDF ────────────────────────────────────────────────────
    pdf_bytes = generate_session_report(
        patient_name=patient_name,
        patient_condition=patient_condition,
        session_data=dict(sess),
        exercises=exercises_list,
        frames=frames,
        overall_duration=overall_duration,
    )

    response = make_response(pdf_bytes)
    fname = f"rehab_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


@app.route('/api/session/report/doctor/<int:session_id>')
@login_required
@role_required('doctor')
def api_session_report_doctor(session_id):
    """Generate an enhanced PDF clinician report for the assigned doctor."""
    import json as _json, io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.graphics.shapes import Drawing, Line, String, Rect, Circle
    from reportlab.graphics import renderPDF

    doctor_id = session['user_id']

    # ── Auth ────────────────────────────────────────────────────────────────
    sess = query_db('SELECT * FROM sessions WHERE id = ?', (session_id,), one=True)
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    patient_id = sess['patient_id']
    assigned = query_db(
        'SELECT 1 FROM doctor_patient WHERE doctor_id = ? AND patient_id = ?',
        (doctor_id, patient_id), one=True
    )
    if not assigned:
        return jsonify({"error": "Not authorised to view this patient's report"}), 403

    # ── Patient info ─────────────────────────────────────────────────────────
    user_row = query_db('SELECT name, email, dob FROM users WHERE id = ?', (patient_id,), one=True)
    pat_row  = query_db(
        'SELECT condition, current_week, adherence_rate, streak_days, completed_sessions, avg_pain_level FROM patients WHERE user_id = ?',
        (patient_id,), one=True
    )
    patient_name      = user_row['name'] if user_row else 'Patient'
    patient_condition = pat_row['condition'] if pat_row else 'General'
    current_week      = pat_row['current_week'] if pat_row else 1
    adherence         = float(pat_row['adherence_rate'] or 0) if pat_row else 0
    streak_days       = int(pat_row['streak_days'] or 0) if pat_row else 0
    total_sessions    = int(pat_row['completed_sessions'] or 0) if pat_row else 0
    avg_pain          = float(pat_row['avg_pain_level'] or 0) if pat_row else 0

    # Age from DOB
    patient_age = '—'
    if user_row and user_row['dob']:
        try:
            dob = date.fromisoformat(user_row['dob'])
            patient_age = str((date.today() - dob).days // 365)
        except Exception:
            pass

    # ── This session's exercises ──────────────────────────────────────────────
    exercises_raw = query_db('''
        SELECT se.*, COALESCE(se.exercise_name, e.name) as exercise_name
        FROM session_exercises se
        LEFT JOIN workouts w ON se.workout_id = w.id
        LEFT JOIN exercises e ON w.exercise_id = e.id
        WHERE se.session_id = ?
        ORDER BY se.exercise_start_time
    ''', (session_id,))

    exercise_rows = []
    for ex in (exercises_raw or []):
        req  = _json.loads(ex['sets_required'])  if ex['sets_required']  else {}
        comp = _json.loads(ex['sets_completed']) if ex['sets_completed'] else {}
        total_req  = sum(int(v) for v in req.values())
        total_comp = sum(int(v) for v in comp.values())
        qs = int(ex['quality_score'] or 0)
        exercise_rows.append([
            ex['exercise_name'] or '—',
            str(total_req),
            str(total_comp),
            f"{qs}/100",
        ])

    # ── Historical sessions (last 10) for trend charts ───────────────────────
    history = query_db('''
        SELECT quality_score, completed_perc, pain_before, pain_after,
               effort_level, completed_at
        FROM sessions
        WHERE patient_id = ? AND completed_at IS NOT NULL
        ORDER BY completed_at DESC LIMIT 10
    ''', (patient_id,))
    history = list(reversed(history or []))   # oldest → newest

    trend_quality  = [float(r['quality_score']  or 0) for r in history]
    trend_pain_b   = [float(r['pain_before']    or 0) for r in history]
    trend_pain_a   = [float(r['pain_after']     or 0) for r in history]
    trend_labels   = [(r['completed_at'] or '')[:10]   for r in history]

    # ── Re-injury risk ────────────────────────────────────────────────────────
    risk = None
    if REINJURY_RISK_AVAILABLE:
        try:
            risk = analyze_patient_risk(patient_id, query_db)
        except Exception:
            pass

    # ── Pending adaptive plan suggestions ────────────────────────────────────
    pending_suggestions = query_db('''
        SELECT aps.suggested_change, aps.reason, aps.severity,
               aps.suggested_sets, aps.suggested_reps, aps.suggested_frequency,
               e.name as exercise_name
        FROM adaptive_plan_suggestions aps
        LEFT JOIN workouts w ON aps.workout_id = w.id
        LEFT JOIN exercises e ON w.exercise_id = e.id
        WHERE aps.patient_id = ? AND aps.status = \'pending\'
        ORDER BY aps.severity DESC, aps.created_at DESC
        LIMIT 5
    ''', (patient_id,))

    # ── Recent clinician notes ────────────────────────────────────────────────
    clinician_notes = query_db('''
        SELECT cn.note_text, cn.created_at, u.name as doctor_name
        FROM clinician_notes cn
        JOIN users u ON cn.doctor_id = u.id
        WHERE cn.patient_id = ?
        ORDER BY cn.created_at DESC LIMIT 3
    ''', (patient_id,))

    # ── AI clinical summary via Groq ─────────────────────────────────────────
    ai_summary = ""
    try:
        from groq import Groq as _Groq
        _groq = _Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        ex_names   = ", ".join(r[0] for r in exercise_rows) or "general exercises"
        risk_line  = f"Re-injury risk: {risk['risk_label']} ({risk['risk_score']}/12). " if risk and risk.get('has_data') else ""
        _resp = _groq.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content":
                f"Write a 2-sentence clinical summary for a doctor reviewing a rehab session. "
                f"Patient: {patient_name}, Condition: {patient_condition}, Week {current_week}. "
                f"Session quality: {int(sess['quality_score'] or 0)}/100, "
                f"Pain before: {sess['pain_before']}/10, Pain after: {sess['pain_after']}/10, "
                f"Adherence: {int(adherence)}%, Streak: {streak_days} days. "
                f"{risk_line}"
                f"Exercises: {ex_names}. No markdown, no bullet points."}],
            max_tokens=120,
        )
        ai_summary = _resp.choices[0].message.content.strip()
    except Exception:
        pass

    # ════════════════════════════════════════════════════════════════════════
    # PDF BUILD
    # ════════════════════════════════════════════════════════════════════════
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()

    NAVY   = colors.HexColor('#1e3a5f')
    BLUE_L = colors.HexColor('#f0f4f8')
    GRID_C = colors.HexColor('#d0d8e0')
    STRIPE = colors.HexColor('#f7f9fb')

    h1  = ParagraphStyle('H1',  parent=styles['Heading1'], fontSize=17, textColor=NAVY, spaceAfter=2)
    h3  = ParagraphStyle('H3',  parent=styles['Heading3'], fontSize=11, textColor=NAVY, spaceBefore=4, spaceAfter=2)
    sm  = ParagraphStyle('Sm',  parent=styles['Normal'],   fontSize=8.5, textColor=colors.grey)
    nrm = ParagraphStyle('Nrm', parent=styles['Normal'],   fontSize=10)
    ctr = ParagraphStyle('Ctr', parent=styles['Normal'],   fontSize=10, alignment=TA_CENTER)

    def section(title):
        return [Paragraph(title, h3), HRFlowable(width='100%', thickness=0.5, color=GRID_C, spaceAfter=3)]

    def kv_table(rows, col_w=None):
        col_w = col_w or [40*mm, 55*mm, 40*mm, 38*mm]
        t = Table(rows, colWidths=col_w)
        t.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 0), (-1, -1), 10),
            ('FONTNAME',      (0, 0), (0, -1),  'Helvetica-Bold'),
            ('FONTNAME',      (2, 0), (2, -1),  'Helvetica-Bold'),
            ('ROWBACKGROUNDS',(0, 0), (-1, -1),  [BLUE_L, colors.white]),
            ('GRID',          (0, 0), (-1, -1),  0.4, GRID_C),
            ('TOPPADDING',    (0, 0), (-1, -1),  4),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
            ('LEFTPADDING',   (0, 0), (-1, -1),  6),
        ]))
        return t

    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("Clinician Session Report", h1))
    story.append(Spacer(1, 1*mm))

    # ── Patient & session meta ────────────────────────────────────────────────
    session_date = (sess['completed_at'] or sess['started_at'] or '')[:10]
    meta = [
        ["Patient",       patient_name,                    "Date",          session_date],
        ["Age",           patient_age,                     "Condition",     patient_condition],
        ["Recovery Week", str(current_week),               "Total Sessions",str(total_sessions)],
        ["Pain Before",   f"{sess['pain_before']}/10",     "Pain After",    f"{sess['pain_after']}/10"],
        ["Quality Score", f"{int(sess['quality_score'] or 0)}/100",
         "Adherence",     f"{int(adherence)}%"],
        ["Streak",        f"{streak_days} days",           "Avg Pain (all)",f"{avg_pain:.1f}/10"],
    ]
    story.append(kv_table(meta))
    story.append(Spacer(1, 5*mm))

    # ── Exercise breakdown ────────────────────────────────────────────────────
    if exercise_rows:
        story += section("Exercise Breakdown")
        hdr = [["Exercise", "Sets Required", "Sets Completed", "Quality"]]
        ex_t = Table(hdr + exercise_rows, colWidths=[78*mm, 33*mm, 36*mm, 26*mm])
        ex_t.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 10),
            ('BACKGROUND',    (0, 0), (-1, 0),   NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.white),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1),  [colors.white, STRIPE]),
            ('GRID',          (0, 0), (-1, -1),  0.4, GRID_C),
            ('ALIGN',         (1, 0), (-1, -1),  'CENTER'),
            ('TOPPADDING',    (0, 0), (-1, -1),  4),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
            ('LEFTPADDING',   (0, 0), (-1, -1),  6),
        ]))
        story.append(ex_t)
        story.append(Spacer(1, 5*mm))

    # ── Quality score trend chart (last 10 sessions) ──────────────────────────
    if len(trend_quality) >= 2:
        story += section("Quality Score Trend (Last 10 Sessions)")
        chart_w, chart_h = 173*mm, 45*mm
        d = Drawing(chart_w, chart_h)

        # axes
        pad_l, pad_r, pad_b, pad_t = 8*mm, 4*mm, 6*mm, 4*mm
        plot_w = chart_w - pad_l - pad_r
        plot_h = chart_h - pad_b - pad_t

        # background
        d.add(Rect(pad_l, pad_b, plot_w, plot_h,
                   fillColor=colors.HexColor('#f8fafc'), strokeColor=GRID_C, strokeWidth=0.5))

        # horizontal gridlines at 0, 25, 50, 75, 100
        for yv in [0, 25, 50, 75, 100]:
            y_px = pad_b + (yv / 100.0) * plot_h
            d.add(Line(pad_l, y_px, pad_l + plot_w, y_px,
                       strokeColor=GRID_C, strokeWidth=0.4))
            d.add(String(pad_l - 1*mm, y_px - 1.5*mm, str(yv),
                         fontSize=6, fillColor=colors.grey, textAnchor='end'))

        n = len(trend_quality)
        xs = [pad_l + i / max(n - 1, 1) * plot_w for i in range(n)]
        ys = [pad_b + (v / 100.0) * plot_h for v in trend_quality]

        # fill area under line
        from reportlab.graphics.shapes import Polygon
        poly_pts = [pad_l, pad_b]
        for x, y in zip(xs, ys):
            poly_pts += [x, y]
        poly_pts += [xs[-1], pad_b]
        d.add(Polygon(poly_pts,
                      fillColor=colors.HexColor('#dbeafe'), strokeColor=None, strokeWidth=0))

        # line segments
        for i in range(n - 1):
            clr = colors.HexColor('#2563eb') if trend_quality[i + 1] >= trend_quality[i] else colors.HexColor('#ef4444')
            d.add(Line(xs[i], ys[i], xs[i + 1], ys[i + 1],
                       strokeColor=clr, strokeWidth=1.5))

        # dots + value labels
        for i, (x, y, v) in enumerate(zip(xs, ys, trend_quality)):
            dot_color = colors.HexColor('#1d4ed8')
            if i == n - 1:   # current session highlighted
                dot_color = colors.HexColor('#16a34a') if v >= 60 else colors.HexColor('#dc2626')
            d.add(Circle(x, y, 2.2*mm, fillColor=dot_color, strokeColor=colors.white, strokeWidth=0.8))
            d.add(String(x, y + 3*mm, str(int(v)),
                         fontSize=6.5, fillColor=NAVY, textAnchor='middle'))

        # x-axis date labels (every other label if many)
        step = 2 if n > 6 else 1
        for i in range(0, n, step):
            lbl = trend_labels[i][5:] if len(trend_labels[i]) >= 10 else trend_labels[i]
            d.add(String(xs[i], pad_b - 4*mm, lbl,
                         fontSize=6, fillColor=colors.grey, textAnchor='middle'))

        story.append(d)
        story.append(Spacer(1, 4*mm))

    # ── Pain trend table ──────────────────────────────────────────────────────
    if len(history) >= 2:
        story += section("Pain Trend (Last Sessions)")
        pain_hdr = [["Date", "Pain Before", "Pain After", "Change", "Quality"]]
        pain_rows = []
        for r in history[-6:]:
            pb  = int(r['pain_before']  or 0)
            pa  = int(r['pain_after']   or 0)
            qs  = int(r['quality_score']or 0)
            chg = pa - pb
            chg_str = (f"↓ {abs(chg)}" if chg < 0 else (f"↑ {chg}" if chg > 0 else "—"))
            pain_rows.append([
                (r['completed_at'] or '')[:10],
                f"{pb}/10", f"{pa}/10", chg_str, f"{qs}/100"
            ])
        pain_t = Table(pain_hdr + pain_rows, colWidths=[36*mm, 30*mm, 30*mm, 28*mm, 28*mm])
        pain_t.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9.5),
            ('BACKGROUND',    (0, 0), (-1, 0),   NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.white),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1),  [colors.white, STRIPE]),
            ('GRID',          (0, 0), (-1, -1),  0.4, GRID_C),
            ('ALIGN',         (1, 0), (-1, -1),  'CENTER'),
            ('TOPPADDING',    (0, 0), (-1, -1),  4),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
            ('LEFTPADDING',   (0, 0), (-1, -1),  6),
        ]))
        story.append(pain_t)
        story.append(Spacer(1, 5*mm))

    # ── Re-injury risk ────────────────────────────────────────────────────────
    if risk and risk.get('has_data'):
        story += section("Re-Injury Risk Assessment")
        level  = risk['risk_level']
        label  = risk['risk_label']
        score  = risk['risk_score']
        RISK_COLORS = {
            'green':  colors.HexColor('#dcfce7'),
            'yellow': colors.HexColor('#fef9c3'),
            'orange': colors.HexColor('#ffedd5'),
            'red':    colors.HexColor('#fee2e2'),
        }
        RISK_TEXT = {
            'green':  colors.HexColor('#166534'),
            'yellow': colors.HexColor('#854d0e'),
            'orange': colors.HexColor('#9a3412'),
            'red':    colors.HexColor('#991b1b'),
        }
        risk_bg   = RISK_COLORS.get(level, BLUE_L)
        risk_text = RISK_TEXT.get(level,  NAVY)

        risk_row = Table(
            [[Paragraph(f"<b>{label}</b>  (Score: {score}/12)", ParagraphStyle('R', parent=styles['Normal'], fontSize=11, textColor=risk_text))]],
            colWidths=[173*mm]
        )
        risk_row.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), risk_bg),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS',[3]),
        ]))
        story.append(risk_row)
        story.append(Spacer(1, 2*mm))

        # Signal details
        if risk.get('signal_details'):
            for sig in risk['signal_details']:
                story.append(Paragraph(f"• {sig}", ParagraphStyle('Sig', parent=styles['Normal'], fontSize=9.5, leftIndent=6)))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(risk.get('explanation', ''), nrm))
        story.append(Spacer(1, 5*mm))

    # ── Pending adaptive suggestions ─────────────────────────────────────────
    if pending_suggestions:
        story += section(f"Pending Adaptive Plan Suggestions ({len(pending_suggestions)})")
        sug_hdr = [["Exercise", "Severity", "Suggested Change"]]
        sug_rows = []
        for s in pending_suggestions:
            sev = (s['severity'] or '').capitalize()
            change = s['suggested_change'] or s['reason'] or '—'
            if len(change) > 70:
                change = change[:70] + '…'
            sug_rows.append([s['exercise_name'] or '—', sev, change])
        sug_t = Table(sug_hdr + sug_rows, colWidths=[42*mm, 24*mm, 107*mm])
        sug_t.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9.5),
            ('BACKGROUND',    (0, 0), (-1, 0),   NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.white),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1),  [colors.white, STRIPE]),
            ('GRID',          (0, 0), (-1, -1),  0.4, GRID_C),
            ('TOPPADDING',    (0, 0), (-1, -1),  4),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
            ('LEFTPADDING',   (0, 0), (-1, -1),  6),
            ('WORDWRAP',      (2, 0), (2, -1),   'LTR'),
        ]))
        story.append(sug_t)
        story.append(Spacer(1, 5*mm))

    # ── Recent clinician notes ────────────────────────────────────────────────
    if clinician_notes:
        story += section("Recent Clinician Notes")
        for note in clinician_notes:
            ts  = (note['created_at'] or '')[:16]
            doc_name = note['doctor_name'] or 'Unknown'
            story.append(Paragraph(
                f"<b>{doc_name}</b> <font size='8' color='grey'>— {ts}</font>",
                ParagraphStyle('NoteHdr', parent=styles['Normal'], fontSize=9.5)
            ))
            story.append(Paragraph(note['note_text'], ParagraphStyle('NoteTxt', parent=styles['Normal'], fontSize=9.5, leftIndent=6)))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))

    # ── AI clinical summary ───────────────────────────────────────────────────
    if ai_summary:
        story += section("Clinical Summary (AI-Assisted)")
        story.append(Paragraph(ai_summary, nrm))
        story.append(Spacer(1, 4*mm))

    # ── Disclaimer ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRID_C))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "This report is auto-generated for clinical reference only. "
        "Always apply clinical judgement when reviewing patient progress. "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        sm
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    response = make_response(pdf_bytes)
    fname = f"clinician_report_{patient_name.replace(' ','_')}_session{session_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


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
    # Real-time: mark any appointments whose time has now passed as 'missed'
    _mark_missed_appointments()

    # Upcoming — only future appointments (real-time: exclude today's past-time slots too)
    appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status = 'scheduled'
          AND (
            a.appointment_date > date('now')
            OR (a.appointment_date = date('now')
                AND a.appointment_time > strftime('%H:%M', 'now', 'localtime'))
          )
        ORDER BY a.appointment_date, a.appointment_time
    ''', (session['user_id'],))

    # Past appointments — completed, missed, cancelled
    past_appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.status IN ('completed', 'missed', 'cancelled')
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 20
    ''', (session['user_id'],))

    # Get patient scheduling preferences
    patient_prefs = query_db(
        'SELECT * FROM patients WHERE user_id = ?',
        (session['user_id'],),
        one=True
    )

    # Plain-dict calendar events for JSON serialisation in template
    cal_events = (
        [{'date': r['appointment_date'], 'status': 'upcoming'} for r in (appointments or [])] +
        [{'date': r['appointment_date'], 'status': r['status']} for r in (past_appointments or [])]
    )

    return render_template('patient/appointments.html',
                         appointments=appointments if appointments else [],
                         past_appointments=past_appointments if past_appointments else [],
                         patient_prefs=patient_prefs,
                         cal_events=cal_events)


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


# ==================== AVATAR ROUTES ====================

@app.route('/patient/avatar')
@login_required
@role_required('patient')
def avatar_page():
    """Avatar interaction page - Speak to Jimmy"""
    user = get_current_user()
    return render_template('patient/avatar.html', user=user)


@app.route('/patient/avatar/chat', methods=['POST'])
@login_required
@role_required('patient')
def avatar_chat():
    """Handle avatar chat requests"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        history = data.get('history', [])
        language = (data.get('language') or 'English').strip()
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Import avatar service
        from meralion_avatar import get_avatar
        
        avatar = get_avatar()
        
        # Get avatar response with RAG and patient context
        response = avatar.query_jimmy(
            patient_id=session['user_id'],
            user_message=user_message,
            conversation_history=history,
            include_rag=True,
            include_performance=True,
            preferred_language=language
        )
        
        return jsonify({
            'response': response,
            'status': 'success'
        })
    
    except Exception as e:
        print(f"[AVATAR] Error in avatar_chat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@app.route('/patient/avatar/voice', methods=['POST'])
@login_required
@role_required('patient')
def avatar_voice():
    """
    Real-time voice interaction with Jimmy avatar.
    Handles:
    1. Voice activity detection (knows when you stop talking)
    2. Automatic transcription
    3. Jimmy response generation
    4. Text-to-speech response audio
    
    Expects JSON:
    {
        "audio": "base64-encoded 16-bit PCM audio at 16kHz",
        "language": "English|Chinese|Malay|Tamil|Singlish",
        "history": [previous conversation messages]
    }
    
    Returns JSON:
    {
        "transcribed_text": "what you said",
        "response": "what Jimmy says",
        "response_audio": "base64-encoded MP3 audio",
        "status": "success|error"
    }
    """
    try:
        data = request.get_json()
        audio_b64 = data.get('audio', '').strip()
        language = (data.get('language') or 'English').strip()
        history = data.get('history', [])
        
        if not audio_b64:
            return jsonify({'error': 'No audio provided'}), 400
        
        # Check if webrtcvad is available
        try:
            import webrtcvad
            vad_available = True
        except ImportError:
            vad_available = False
            print("[AVATAR-VOICE] webrtcvad not installed - installing...")
            # Try to install
            import subprocess
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'webrtcvad', '-q'])
                vad_available = True
            except:
                vad_available = False
        
        # Process audio with voice activity detection
        from avatar_voice_processor import process_avatar_audio_stream
        
        transcribed_text, jimmy_response, response_audio = process_avatar_audio_stream(
            audio_base64=audio_b64,
            patient_id=session['user_id'],
            language=language,
            history=history
        )
        
        if not jimmy_response:
            return jsonify({
                'error': response_audio or 'Could not process audio',
                'status': 'error'
            }), 400
        
        return jsonify({
            'transcribed_text': transcribed_text,
            'response': jimmy_response,
            'response_audio': response_audio,  # Base64-encoded MP3
            'vad_available': vad_available,
            'status': 'success'
        })
    
    except Exception as e:
        print(f"[AVATAR-VOICE] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


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

    # Doctor's specialties
    spec_rows = query_db('SELECT specialty FROM doctor_specialties WHERE doctor_id = ?', (doctor_id,))
    doctor_specialties = [dict(r)['specialty'] for r in spec_rows] if spec_rows else []

    return render_template('clinician/profile.html',
                         user_info=user_info,
                         patients=patients_with_caregivers,
                         total_patients=total_patients,
                         patients_with_cg=patients_with_cg,
                         avg_adherence=avg_adherence,
                         age=age,
                         doctor_specialties=doctor_specialties,
                         all_specialties=DOCTOR_SPECIALTIES)


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
          AND a.appointment_date >= date('now')
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 5
    ''', (session['user_id'],))

    pending_adaptive_suggestions = query_db('''
        SELECT aps.*, u.name AS patient_name
        FROM adaptive_plan_suggestions aps
        JOIN users u ON aps.patient_id = u.id
        WHERE aps.doctor_id = ? AND aps.status = 'pending'
        ORDER BY aps.created_at DESC
        LIMIT 20
    ''', (session['user_id'],))

    pending_patient_concerns = query_db('''
        SELECT aps.*, u.name AS patient_name
        FROM adaptive_plan_suggestions aps
        JOIN users u ON aps.patient_id = u.id
        WHERE aps.doctor_id = ?
          AND aps.status = 'pending'
          AND aps.source = 'patient_feedback'
        ORDER BY aps.created_at DESC
        LIMIT 20
    ''', (session['user_id'],))
    
    # ── Specialty-matched new patients ──────────────────────────────────────
    doc_spec_rows = query_db(
        'SELECT specialty FROM doctor_specialties WHERE doctor_id = ?',
        (session['user_id'],)
    )
    doctor_specialties_list = [dict(r)['specialty'] for r in doc_spec_rows] if doc_spec_rows else []
    no_specialties_set = not bool(doctor_specialties_list)

    if doctor_specialties_list:
        _ph = ','.join('?' * len(doctor_specialties_list))
        new_matched_patients = query_db(f'''
            SELECT u.id, u.name, u.email, p.condition, p.specialty_needed
            FROM users u
            JOIN patients p ON u.id = p.user_id
            WHERE p.specialty_needed IN ({_ph})
              AND u.id NOT IN (SELECT patient_id FROM doctor_patient WHERE doctor_id = ?)
            ORDER BY u.name
        ''', doctor_specialties_list + [session['user_id']])
    else:
        # No specialties set → show ALL unassigned patients so doctor can claim them
        new_matched_patients = query_db('''
            SELECT u.id, u.name, u.email, p.condition, p.specialty_needed
            FROM users u
            JOIN patients p ON u.id = p.user_id
            WHERE u.id NOT IN (SELECT patient_id FROM doctor_patient)
            ORDER BY u.name
        ''')

    new_matched_patients = [dict(r) for r in new_matched_patients] if new_matched_patients else []

    return render_template('clinician/dashboard.html',
                         patients=patients,
                         total_patients=total_patients,
                         needs_attention=needs_attention,
                         avg_adherence=round(avg_adherence),
                         upcoming_appointments=len(appointments) if appointments else 0,
                         pending_adaptive_suggestions=pending_adaptive_suggestions if pending_adaptive_suggestions else [],
                         pending_patient_concerns=pending_patient_concerns if pending_patient_concerns else [],
                         new_matched_patients=new_matched_patients,
                         no_specialties_set=no_specialties_set,
                         doctor_specialties=doctor_specialties_list,
                         all_specialties=DOCTOR_SPECIALTIES)
    difficulty = int(data.get('difficulty', 7))
    note = (data.get('note') or '').strip()

    if not workout_id:
        return jsonify({'ok': False, 'error': 'workout_id is required'}), 400

    workout = query_db('''
        SELECT w.*, e.name AS exercise_name
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.id = ? AND w.patient_id = ?
    ''', (workout_id, session['user_id']), one=True)
    if not workout:
        return jsonify({'ok': False, 'error': 'Workout not found'}), 404
    workout = dict(workout)

    # Suggest lighter progression when difficulty is high.
    suggested_sets = max(1, int(workout['sets']) - 1) if difficulty >= 8 else int(workout['sets'])
    suggested_reps = max(5, int(workout['reps']) - 2) if difficulty >= 7 else int(workout['reps'])
    suggested_frequency = '3x per week' if difficulty >= 8 else workout['frequency']

    reason = f"Patient reported '{issue_type}' (difficulty {difficulty}/10)"
    suggested_change = (
        f"{workout['exercise_name']}: adjust to {suggested_sets} sets × {suggested_reps} reps"
        f"; frequency {suggested_frequency}."
    )

    target_doctor_id = workout.get('assigned_by_doctor_id')
    if not target_doctor_id:
        # Legacy rows may not have workout ownership; pick most recently assigned doctor on this patient's active plan.
        owner_row = query_db('''
            SELECT assigned_by_doctor_id
            FROM workouts
            WHERE patient_id = ?
              AND is_active = 1
              AND assigned_by_doctor_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
        ''', (session['user_id'],), one=True)
        owner_row = dict(owner_row) if owner_row else None
        if owner_row and owner_row.get('assigned_by_doctor_id'):
            target_doctor_id = owner_row.get('assigned_by_doctor_id')

    if target_doctor_id and not workout.get('assigned_by_doctor_id'):
        execute_db('''
            UPDATE workouts
            SET assigned_by_doctor_id = ?
            WHERE id = ? AND patient_id = ?
        ''', (target_doctor_id, workout_id, session['user_id']))

    suggestion_id = create_adaptive_suggestion(
        patient_id=session['user_id'],
        source='patient_feedback',
        reason=reason,
        suggested_change=suggested_change,
        doctor_id_override=target_doctor_id,
        severity='high' if difficulty >= 8 else 'medium',
        workout_id=workout_id,
        suggested_sets=suggested_sets,
        suggested_reps=suggested_reps,
        suggested_frequency=suggested_frequency,
        patient_note=note,
        app_confidence=0.75,
    )

    if not suggestion_id:
        return jsonify({'ok': False, 'error': 'No assigned doctor found for this patient'}), 400

    return jsonify({'ok': True, 'suggestion_id': suggestion_id})


@app.route('/api/adaptive-suggestions/<int:suggestion_id>/approve', methods=['POST'])
@login_required
@role_required('doctor')
def api_approve_adaptive_suggestion(suggestion_id):
    """Doctor approves app/patient adaptive plan suggestion and applies workout updates."""
    payload = request.get_json(silent=True) or {}
    review_note = (payload.get('review_note') or '').strip()

    suggestion = query_db('''
        SELECT * FROM adaptive_plan_suggestions
        WHERE id = ? AND doctor_id = ?
    ''', (suggestion_id, session['user_id']), one=True)

    if not suggestion:
        return jsonify({'ok': False, 'error': 'Suggestion not found'}), 404
    if suggestion['status'] != 'pending':
        return jsonify({'ok': False, 'error': 'Suggestion already reviewed'}), 400

    if suggestion['workout_id']:
        execute_db('''
            UPDATE workouts
            SET sets = COALESCE(?, sets),
                reps = COALESCE(?, reps),
                frequency = COALESCE(?, frequency)
            WHERE id = ? AND patient_id = ?
        ''', (
            suggestion['suggested_sets'],
            suggestion['suggested_reps'],
            suggestion['suggested_frequency'],
            suggestion['workout_id'],
            suggestion['patient_id'],
        ))

    execute_db('''
        UPDATE adaptive_plan_suggestions
        SET status = 'approved',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?,
            review_note = ?
        WHERE id = ?
    ''', (session['user_id'], review_note, suggestion_id))

    return jsonify({'ok': True})


@app.route('/api/adaptive-suggestions/<int:suggestion_id>/reject', methods=['POST'])
@login_required
@role_required('doctor')
def api_reject_adaptive_suggestion(suggestion_id):
    """Doctor rejects adaptive plan suggestion."""
    payload = request.get_json(silent=True) or {}
    review_note = (payload.get('review_note') or '').strip()

    suggestion = query_db('''
        SELECT id, status
        FROM adaptive_plan_suggestions
        WHERE id = ? AND doctor_id = ?
    ''', (suggestion_id, session['user_id']), one=True)

    if not suggestion:
        return jsonify({'ok': False, 'error': 'Suggestion not found'}), 404
    if suggestion['status'] != 'pending':
        return jsonify({'ok': False, 'error': 'Suggestion already reviewed'}), 400

    execute_db('''
        UPDATE adaptive_plan_suggestions
        SET status = 'rejected',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?,
            review_note = ?
        WHERE id = ?
    ''', (session['user_id'], review_note, suggestion_id))

    return jsonify({'ok': True})


@app.route('/clinician/patient/<int:patient_id>')
@login_required
@role_required('doctor')
def patient_detail(patient_id):
    """Patient Detail View — comprehensive profile page"""
    patient = query_db('''
        SELECT u.*, p.*,
               u.id as user_id, u.name as name, u.email as email,
               u.phone as phone, u.pincode as pincode, u.dob as dob,
               p.condition as condition, p.surgery_date as surgery_date,
               p.current_week as current_week, p.adherence_rate as adherence_rate,
               p.avg_pain_level as avg_pain_level, p.avg_quality_score as avg_quality_score,
               p.completed_sessions as completed_sessions, p.streak_days as streak_days
        FROM users u
        JOIN patients p ON u.id = p.user_id
        WHERE u.id = ?
    ''', (patient_id,), one=True)

    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('clinician_dashboard'))

    # ── Assigned exercises (from patient_exercises, synced to workouts) ──
    assigned_exercises = query_db('''
        SELECT pe.id as pe_id, pe.enabled, e.id as exercise_id,
               e.name as exercise_name, e.category, e.description
        FROM patient_exercises pe
        JOIN exercises e ON pe.exercise_id = e.id
        WHERE pe.patient_id = ? AND pe.enabled = 1
        ORDER BY e.category, e.name
    ''', (patient_id,))
    assigned_exercises = [dict(e) for e in assigned_exercises] if assigned_exercises else []

    # Workouts with sets/reps details
    workouts = query_db('''
        SELECT w.*, e.name as exercise_name, e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
    ''', (patient_id,))
    workouts = [dict(w) for w in workouts] if workouts else []

    # ── Session history (all completed sessions) ──
    sessions = query_db('''
        SELECT s.id, s.quality_score, s.pain_before, s.pain_after,
               s.effort_level, s.completed_perc, s.started_at, s.completed_at,
               s.session_group_id,
               (SELECT GROUP_CONCAT(DISTINCT se.exercise_name)
                FROM session_exercises se
                WHERE se.session_id = s.id) as exercise_names
        FROM sessions s
        WHERE s.patient_id = ? AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at DESC
    ''', (patient_id,))
    sessions = [dict(s) for s in sessions] if sessions else []

    # ── Session dates for calendar view (distinct dates) ──
    session_dates = []
    for s in sessions:
        if s.get('completed_at'):
            try:
                dt = s['completed_at'][:10]  # YYYY-MM-DD
                if dt not in session_dates:
                    session_dates.append(dt)
            except:
                pass

    # ── Clinician notes ──
    notes = query_db('''
        SELECT cn.*, u.name as doctor_name
        FROM clinician_notes cn
        JOIN users u ON cn.doctor_id = u.id
        WHERE cn.patient_id = ?
        ORDER BY cn.created_at DESC
        LIMIT 20
    ''', (patient_id,))

    # ── Caregivers ──
    caregivers = query_db('''
        SELECT u.name, u.email, u.phone, cp.relationship
        FROM caregiver_patient cp
        JOIN users u ON cp.caregiver_id = u.id
        WHERE cp.patient_id = ?
    ''', (patient_id,))

    # ── Pending caregiver requests ──
    pending_requests = query_db('''
        SELECT cr.id, u.name as caregiver_name, u.email as caregiver_email, cr.requested_at
        FROM caregiver_requests cr
        JOIN users u ON cr.caregiver_id = u.id
        WHERE cr.patient_id = ? AND cr.status = 'pending'
        ORDER BY cr.requested_at DESC
    ''', (patient_id,))

    # ── Consultation / Appointment history ──
    appointments = query_db('''
        SELECT a.*, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 10
    ''', (patient_id,))
    appointments = [dict(a) for a in appointments] if appointments else []

    # ── Patient preferred consultation time ──
    time_prefs = query_db('''
        SELECT t.day, t.time, t.label, pt.preference_score
        FROM patient_time_preferences pt
        JOIN timeslots t ON pt.timeslot_id = t.id
        WHERE pt.patient_id = ?
        ORDER BY pt.preference_score DESC
        LIMIT 5
    ''', (patient_id,))
    time_prefs = [dict(t) for t in time_prefs] if time_prefs else []

    # ── Distance from clinician ──
    distance_info = None
    patient_pincode = patient['pincode']
    if patient_pincode:
        # Get patient lat/lon from sg_postal
        patient_loc = query_db(
            'SELECT lat, lon FROM sg_postal WHERE postal_code = ? LIMIT 1',
            (patient_pincode,), one=True
        )
        # Get clinician's pincode and lat/lon
        doctor_pincode = query_db(
            'SELECT pincode FROM users WHERE id = ?',
            (session['user_id'],), one=True
        )
        if doctor_pincode and doctor_pincode['pincode']:
            doctor_loc = query_db(
                'SELECT lat, lon FROM sg_postal WHERE postal_code = ? LIMIT 1',
                (doctor_pincode['pincode'],), one=True
            )
            if patient_loc and doctor_loc and patient_loc['lat'] and doctor_loc['lat']:
                import math
                lat1, lon1 = math.radians(patient_loc['lat']), math.radians(patient_loc['lon'])
                lat2, lon2 = math.radians(doctor_loc['lat']), math.radians(doctor_loc['lon'])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                km = 6371 * c
                distance_info = {
                    'km': round(km, 1),
                    'patient_postal': patient_pincode,
                    'doctor_postal': doctor_pincode['pincode'],
                }

    # ── Re-injury risk analysis ──
    risk_data = None
    if REINJURY_RISK_AVAILABLE:
        try:
            risk_data = analyze_patient_risk(patient_id, query_db)
        except Exception as _re:
            print(f"[WARNING] Re-injury risk analysis failed for patient {patient_id}: {_re}")

    # ── Compute aggregate metrics ──
    total_sessions = len(sessions)
    recent_sessions = sessions[:5]
    avg_quality_recent = (sum(s['quality_score'] for s in recent_sessions if s.get('quality_score')) / len(recent_sessions)) if recent_sessions else 0
    avg_pain_recent = (sum(s['pain_after'] for s in recent_sessions if s.get('pain_after') is not None) / len(recent_sessions)) if recent_sessions else 0

    return render_template('clinician/patient_detail.html',
                         patient=patient,
                         patient_id=patient_id,
                         assigned_exercises=assigned_exercises,
                         workouts=workouts,
                         sessions=sessions,
                         session_dates=session_dates,
                         total_sessions=total_sessions,
                         avg_quality_recent=round(avg_quality_recent, 1),
                         avg_pain_recent=round(avg_pain_recent, 1),
                         notes=notes if notes else [],
                         caregivers=caregivers if caregivers else [],
                         pending_caregiver_requests=pending_requests if pending_requests else [],
                         appointments=appointments,
                         time_prefs=time_prefs,
                         distance_info=distance_info,
                         risk_data=risk_data)


@app.route('/api/patient/<int:patient_id>/reinjury_risk', methods=['GET'])
@login_required
@role_required('doctor')
def api_reinjury_risk(patient_id):
    """Return re-injury risk analysis for a patient as JSON."""
    if not REINJURY_RISK_AVAILABLE:
        return jsonify({"error": "Risk engine not available"}), 503
    try:
        data = analyze_patient_risk(patient_id, query_db)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# MEDICAL HISTORY — shared helpers
# ============================================================================



def _recompute_risk_cache(patient_id: int):
    """Re-run analyze_patient_risk and upsert the patient_risk_cache row."""
    if not REINJURY_RISK_AVAILABLE:
        return
    try:
        result = analyze_patient_risk(patient_id, query_db)
        execute_db(
            '''INSERT INTO patient_risk_cache
                   (patient_id, risk_score_raw, risk_score, risk_level, last_computed)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(patient_id) DO UPDATE SET
                   risk_score_raw = excluded.risk_score_raw,
                   risk_score     = excluded.risk_score,
                   risk_level     = excluded.risk_level,
                   last_computed  = excluded.last_computed''',
            (patient_id,
             result.get('raw_score', result.get('risk_score', 0)),
             result.get('risk_score', 0),
             result.get('risk_level', 'green'))
        )
    except Exception as _e:
        print(f"[WARNING] Risk cache update failed for patient {patient_id}: {_e}")


def _validate_year(value, field_name='year'):
    """Return (int_year, None) or (None, error_message)."""
    if value is None or value == '':
        return None, None
    try:
        y = int(value)
        if y < 1900 or y > datetime.now().year:
            return None, f"{field_name} must be between 1900 and {datetime.now().year}"
        return y, None
    except (ValueError, TypeError):
        return None, f"{field_name} must be a valid integer year"


def _validate_date(value, field_name='date', allow_future=False):
    """Return (date_str, None) or (None, error_message)."""
    if value is None or value == '':
        return None, None
    try:
        d = datetime.strptime(value, '%Y-%m-%d').date()
        if not allow_future and d > date.today():
            return None, f"{field_name} cannot be in the future"
        return value, None
    except ValueError:
        return None, f"{field_name} must be a valid date (YYYY-MM-DD)"


def _coerce_bool(value) -> int:
    """Coerce various truthy representations to 0/1 integer."""
    if isinstance(value, int):
        return 1 if value else 0
    if isinstance(value, str):
        return 1 if value.lower() in ('1', 'true', 'yes', 'on') else 0
    return 0


def _build_full_history_response(patient_id: int) -> dict:
    """Return all five medical history categories for a patient as dicts."""
    def _rows(sql, params=()):
        rows = query_db(sql, params) or []
        return [dict(r) for r in rows]

    return {
        'conditions': _rows(
            '''SELECT mc.*, u.name as entered_by_name, v.name as verified_by_name
               FROM medical_conditions mc
               LEFT JOIN users u ON mc.entered_by = u.id
               LEFT JOIN users v ON mc.verified_by = v.id
               WHERE mc.patient_id = ? ORDER BY mc.onset_year DESC, mc.updated_at DESC''',
            (patient_id,)
        ),
        'surgeries': _rows(
            '''SELECT ms.*, u.name as entered_by_name, v.name as verified_by_name
               FROM medical_surgeries ms
               LEFT JOIN users u ON ms.entered_by = u.id
               LEFT JOIN users v ON ms.verified_by = v.id
               WHERE ms.patient_id = ? ORDER BY ms.surgery_date DESC''',
            (patient_id,)
        ),
        'injuries': _rows(
            '''SELECT mi.*, u.name as entered_by_name, v.name as verified_by_name
               FROM medical_injuries mi
               LEFT JOIN users u ON mi.entered_by = u.id
               LEFT JOIN users v ON mi.verified_by = v.id
               WHERE mi.patient_id = ? ORDER BY mi.injury_date DESC, mi.updated_at DESC''',
            (patient_id,)
        ),
        'medications': _rows(
            '''SELECT mm.*, u.name as entered_by_name, v.name as verified_by_name
               FROM medical_medications mm
               LEFT JOIN users u ON mm.entered_by = u.id
               LEFT JOIN users v ON mm.verified_by = v.id
               WHERE mm.patient_id = ? ORDER BY mm.active DESC, mm.updated_at DESC''',
            (patient_id,)
        ),
        'family_history': _rows(
            '''SELECT mf.*, u.name as entered_by_name, v.name as verified_by_name
               FROM medical_family_history mf
               LEFT JOIN users u ON mf.entered_by = u.id
               LEFT JOIN users v ON mf.verified_by = v.id
               WHERE mf.patient_id = ? ORDER BY mf.updated_at DESC''',
            (patient_id,)
        ),
    }


# ============================================================================
# MEDICAL HISTORY — patient-facing endpoints
# ============================================================================

@app.route('/patient/medical-history', methods=['GET'])
@login_required
@role_required('patient')
def patient_medical_history_get():
    """Return the current patient's full medical history as JSON."""
    return jsonify(_build_full_history_response(session['user_id']))


@app.route('/patient/medical-history/condition', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_condition():
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    onset_year, err = _validate_year(data.get('onset_year'), 'onset_year')
    if err:
        return jsonify({'error': err}), 400
    rec_id = execute_db(
        '''INSERT INTO medical_conditions (patient_id, name, onset_year, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        (session['user_id'], name, onset_year, data.get('notes', ''), session['user_id'])
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/patient/medical-history/condition/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('patient')
def patient_update_condition(rec_id):
    row = query_db('SELECT patient_id FROM medical_conditions WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    onset_year, err = _validate_year(data.get('onset_year'), 'onset_year')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_conditions
           SET name = ?, onset_year = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (name, onset_year, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'updated'})


@app.route('/patient/medical-history/condition/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def patient_delete_condition(rec_id):
    row = query_db('SELECT patient_id FROM medical_conditions WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_conditions WHERE id = ?', (rec_id,))
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'deleted'})


@app.route('/patient/medical-history/surgery', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_surgery():
    data = request.get_json(silent=True) or request.form
    procedure = (data.get('procedure') or '').strip()
    if not procedure:
        return jsonify({'error': 'procedure is required'}), 400
    surgery_date, err = _validate_date(data.get('surgery_date'), 'surgery_date')
    if err:
        return jsonify({'error': err}), 400
    body_region = (data.get('body_region') or '')[:100].strip()
    rec_id = execute_db(
        '''INSERT INTO medical_surgeries (patient_id, procedure, surgery_date, body_region, outcome, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        (session['user_id'], procedure, surgery_date, body_region,
         data.get('outcome', ''), data.get('notes', ''), session['user_id'])
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/patient/medical-history/surgery/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('patient')
def patient_update_surgery(rec_id):
    row = query_db('SELECT patient_id FROM medical_surgeries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    procedure = (data.get('procedure') or '').strip()
    if not procedure:
        return jsonify({'error': 'procedure is required'}), 400
    surgery_date, err = _validate_date(data.get('surgery_date'), 'surgery_date')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_surgeries
           SET procedure = ?, surgery_date = ?, body_region = ?, outcome = ?, notes = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (procedure, surgery_date, (data.get('body_region') or '')[:100],
         data.get('outcome', ''), data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'updated'})


@app.route('/patient/medical-history/surgery/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def patient_delete_surgery(rec_id):
    row = query_db('SELECT patient_id FROM medical_surgeries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_surgeries WHERE id = ?', (rec_id,))
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'deleted'})


@app.route('/patient/medical-history/injury', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_injury():
    data = request.get_json(silent=True) or request.form
    body_region = (data.get('body_region') or '').strip()
    if not body_region:
        return jsonify({'error': 'body_region is required'}), 400
    injury_date, err = _validate_date(data.get('injury_date'), 'injury_date')
    if err:
        return jsonify({'error': err}), 400
    rec_id = execute_db(
        '''INSERT INTO medical_injuries
               (patient_id, body_region, injury_description, related_to_current,
                recovery_complete, recurrence, injury_date, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        (session['user_id'], body_region[:100], data.get('injury_description', ''),
         _coerce_bool(data.get('related_to_current')),
         _coerce_bool(data.get('recovery_complete')),
         _coerce_bool(data.get('recurrence')),
         injury_date, data.get('notes', ''), session['user_id'])
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/patient/medical-history/injury/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('patient')
def patient_update_injury(rec_id):
    row = query_db('SELECT patient_id FROM medical_injuries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    body_region = (data.get('body_region') or '').strip()
    if not body_region:
        return jsonify({'error': 'body_region is required'}), 400
    injury_date, err = _validate_date(data.get('injury_date'), 'injury_date')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_injuries
           SET body_region = ?, injury_description = ?, related_to_current = ?,
               recovery_complete = ?, recurrence = ?, injury_date = ?,
               notes = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (body_region[:100], data.get('injury_description', ''),
         _coerce_bool(data.get('related_to_current')),
         _coerce_bool(data.get('recovery_complete')),
         _coerce_bool(data.get('recurrence')),
         injury_date, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'updated'})


@app.route('/patient/medical-history/injury/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def patient_delete_injury(rec_id):
    row = query_db('SELECT patient_id FROM medical_injuries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_injuries WHERE id = ?', (rec_id,))
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'deleted'})


@app.route('/patient/medical-history/medication', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_medication():
    data = request.get_json(silent=True) or request.form
    drug_name = (data.get('drug_name') or '').strip()[:200]
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400
    end_date, err = _validate_date(data.get('end_date'), 'end_date', allow_future=True)
    if err:
        return jsonify({'error': err}), 400
    rec_id = execute_db(
        '''INSERT INTO medical_medications
               (patient_id, drug_name, indication, active, end_date, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        (session['user_id'], drug_name, data.get('indication', ''),
         _coerce_bool(data.get('active', 1)), end_date, session['user_id'])
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/patient/medical-history/medication/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('patient')
def patient_update_medication(rec_id):
    row = query_db('SELECT patient_id FROM medical_medications WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    drug_name = (data.get('drug_name') or '').strip()[:200]
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400
    end_date, err = _validate_date(data.get('end_date'), 'end_date', allow_future=True)
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_medications
           SET drug_name = ?, indication = ?, active = ?, end_date = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (drug_name, data.get('indication', ''),
         _coerce_bool(data.get('active', 1)), end_date, rec_id)
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'updated'})


@app.route('/patient/medical-history/medication/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def patient_delete_medication(rec_id):
    row = query_db('SELECT patient_id FROM medical_medications WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_medications WHERE id = ?', (rec_id,))
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'deleted'})


@app.route('/patient/medical-history/family-history', methods=['POST'])
@login_required
@role_required('patient')
def patient_add_family_history():
    data = request.get_json(silent=True) or request.form
    condition = (data.get('condition') or '').strip()
    relation = (data.get('relation') or '').strip()
    if not condition or not relation:
        return jsonify({'error': 'condition and relation are required'}), 400
    rec_id = execute_db(
        '''INSERT INTO medical_family_history
               (patient_id, condition, relation, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        (session['user_id'], condition, relation, data.get('notes', ''), session['user_id'])
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/patient/medical-history/family-history/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('patient')
def patient_update_family_history(rec_id):
    row = query_db('SELECT patient_id FROM medical_family_history WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    condition = (data.get('condition') or '').strip()
    relation = (data.get('relation') or '').strip()
    if not condition or not relation:
        return jsonify({'error': 'condition and relation are required'}), 400
    execute_db(
        '''UPDATE medical_family_history
           SET condition = ?, relation = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (condition, relation, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'updated'})


@app.route('/patient/medical-history/family-history/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def patient_delete_family_history(rec_id):
    row = query_db('SELECT patient_id FROM medical_family_history WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != session['user_id']:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_family_history WHERE id = ?', (rec_id,))
    _recompute_risk_cache(session['user_id'])
    return jsonify({'status': 'deleted'})


@app.route('/patient/medical-history/upload-pdf', methods=['POST'])
@login_required
@role_required('patient')
def patient_medical_history_upload_pdf():
    """Extract structured medical history from an uploaded PDF using pdfplumber + Groq."""
    import io as _io
    import json as _json
    import pdfplumber as _pdfplumber

    if 'pdf' not in request.files:
        return jsonify({'error': 'no_file', 'message': 'No PDF file provided.'}), 400

    pdf_file = request.files['pdf']
    pdf_bytes = pdf_file.read()

    if len(pdf_bytes) > 5 * 1024 * 1024:
        return jsonify({'error': 'too_large', 'message': 'File too large. Maximum size is 5MB.'}), 413

    # Extract text from PDF
    try:
        with _pdfplumber.open(_io.BytesIO(pdf_bytes)) as _pdf:
            _text = '\n'.join(_page.extract_text() or '' for _page in _pdf.pages)
    except Exception as e:
        print(f"[PDF-UPLOAD] pdfplumber failed: {e}")
        return jsonify({'error': 'parse_failed', 'message': 'Could not read PDF. Please try a different file.'}), 500

    if not _text.strip():
        return jsonify({
            'error': 'no_text',
            'message': 'This PDF appears to be scanned or image-based. Please enter your history manually.'
        }), 422

    _system_prompt = (
        "You are a medical data extraction assistant. Extract structured medical history from the provided text. "
        "Return ONLY valid JSON matching the exact schema below. Do not infer or hallucinate — only extract what is explicitly stated. "
        "Use null for any field not mentioned. Return empty arrays [] for categories with no data found. "
        "Dates must be in YYYY-MM-DD format; if only a year is given, use YYYY-01-01. "
        "The boolean fields related_to_current, recovery_complete, and recurrence default to false unless clearly indicated.\n\n"
        "Required JSON schema:\n"
        '{"conditions":[{"name":"string","onset_year":null,"notes":null}],'
        '"surgeries":[{"procedure":"string","body_region":null,"surgery_date":null,"outcome":null,"notes":null}],'
        '"injuries":[{"body_region":"string","injury_date":null,"description":null,"related_to_current":false,"recovery_complete":false,"recurrence":false}],'
        '"medications":[{"drug_name":"string","indication":null,"active":true}],'
        '"family_history":[{"condition":"string","relation":null,"notes":null}]}'
    )
    _user_msg = f"Extract medical history from the following document text:\n\n<document>\n{_text[:8000]}\n</document>"

    try:
        from groq import Groq as _Groq
        _groq_client = _Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        _resp = _groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": _user_msg},
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        _raw = _resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[PDF-UPLOAD] Groq extraction failed: {e}")
        return jsonify({'error': 'llm_error', 'message': 'Extraction service unavailable. Please try again or enter manually.'}), 500

    try:
        _extracted = _json.loads(_raw)
    except _json.JSONDecodeError:
        return jsonify({'error': 'parse_failed', 'message': 'Extraction failed. Please enter your history manually.'}), 500

    def _cs(v):
        return str(v).strip() if v is not None else None

    def _ci(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    _result = {
        'conditions': [
            {'name': _cs(c.get('name')), 'onset_year': _ci(c.get('onset_year')), 'notes': _cs(c.get('notes'))}
            for c in _extracted.get('conditions', []) if c.get('name')
        ],
        'surgeries': [
            {'procedure': _cs(s.get('procedure')), 'body_region': _cs(s.get('body_region')),
             'surgery_date': _cs(s.get('surgery_date')), 'outcome': _cs(s.get('outcome')), 'notes': _cs(s.get('notes'))}
            for s in _extracted.get('surgeries', []) if s.get('procedure')
        ],
        'injuries': [
            {'body_region': _cs(i.get('body_region')), 'injury_date': _cs(i.get('injury_date')),
             'injury_description': _cs(i.get('description')),
             'related_to_current': bool(i.get('related_to_current', False)),
             'recovery_complete': bool(i.get('recovery_complete', False)),
             'recurrence': bool(i.get('recurrence', False))}
            for i in _extracted.get('injuries', []) if i.get('body_region')
        ],
        'medications': [
            {'drug_name': _cs(m.get('drug_name')), 'indication': _cs(m.get('indication')),
             'active': bool(m.get('active', True))}
            for m in _extracted.get('medications', []) if m.get('drug_name')
        ],
        'family_history': [
            {'condition': _cs(f.get('condition')), 'relation': _cs(f.get('relation')), 'notes': _cs(f.get('notes'))}
            for f in _extracted.get('family_history', []) if f.get('condition')
        ],
    }

    return jsonify(_result)


# ─── Patient: bulk submit from post-signup step ───────────────────────────

@app.route('/signup/medical-history', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def signup_medical_history():
    """Post-signup medical history step for patients."""
    if request.method == 'GET':
        return render_template('patient/medical_history_signup.html')

    data = request.get_json(silent=True) or {}
    uid = session['user_id']

    for cond in data.get('conditions', []):
        name = (cond.get('name') or '').strip()
        if not name:
            continue
        onset_year, _ = _validate_year(cond.get('onset_year'), 'onset_year')
        execute_db(
            '''INSERT INTO medical_conditions (patient_id, name, onset_year, notes, entry_mode, verified, entered_by)
               VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
            (uid, name, onset_year, cond.get('notes', ''), uid)
        )

    for surg in data.get('surgeries', []):
        procedure = (surg.get('procedure') or '').strip()
        if not procedure:
            continue
        surgery_date, _ = _validate_date(surg.get('surgery_date'), 'surgery_date')
        execute_db(
            '''INSERT INTO medical_surgeries (patient_id, procedure, surgery_date, body_region, outcome, notes, entry_mode, verified, entered_by)
               VALUES (?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
            (uid, procedure, surgery_date, (surg.get('body_region') or '')[:100],
             surg.get('outcome', ''), surg.get('notes', ''), uid)
        )

    for inj in data.get('injuries', []):
        body_region = (inj.get('body_region') or '').strip()
        if not body_region:
            continue
        injury_date, _ = _validate_date(inj.get('injury_date'), 'injury_date')
        execute_db(
            '''INSERT INTO medical_injuries
                   (patient_id, body_region, injury_description, related_to_current,
                    recovery_complete, recurrence, injury_date, notes, entry_mode, verified, entered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
            (uid, body_region[:100], inj.get('injury_description', ''),
             _coerce_bool(inj.get('related_to_current')),
             _coerce_bool(inj.get('recovery_complete')),
             _coerce_bool(inj.get('recurrence')),
             injury_date, inj.get('notes', ''), uid)
        )

    for med in data.get('medications', []):
        drug_name = (med.get('drug_name') or '').strip()[:200]
        if not drug_name:
            continue
        end_date, _ = _validate_date(med.get('end_date'), 'end_date', allow_future=True)
        execute_db(
            '''INSERT INTO medical_medications
                   (patient_id, drug_name, indication, active, end_date, entry_mode, verified, entered_by)
               VALUES (?, ?, ?, ?, ?, 'self_report', 0, ?)''',
            (uid, drug_name, med.get('indication', ''),
             _coerce_bool(med.get('active', 1)), end_date, uid)
        )

    for fh in data.get('family_history', []):
        condition = (fh.get('condition') or '').strip()
        relation = (fh.get('relation') or '').strip()
        if not condition or not relation:
            continue
        execute_db(
            '''INSERT INTO medical_family_history
                   (patient_id, condition, relation, notes, entry_mode, verified, entered_by)
               VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
            (uid, condition, relation, fh.get('notes', ''), uid)
        )

    _recompute_risk_cache(uid)
    return jsonify({'status': 'saved', 'redirect': url_for('patient_dashboard')})


# ============================================================================
# MEDICAL HISTORY — clinician-facing endpoints
# ============================================================================

@app.route('/api/patient/<int:patient_id>/medical-history', methods=['GET'])
@login_required
@role_required('doctor')
def api_clinician_get_history(patient_id):
    """Return full medical history for a patient (doctor view)."""
    return jsonify(_build_full_history_response(patient_id))


@app.route('/api/patient/<int:patient_id>/medical-history/condition', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_add_condition(patient_id):
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    onset_year, err = _validate_year(data.get('onset_year'), 'onset_year')
    if err:
        return jsonify({'error': err}), 400
    doctor_id = session['user_id']
    rec_id = execute_db(
        '''INSERT INTO medical_conditions
               (patient_id, name, onset_year, notes, entry_mode, verified, entered_by, verified_by)
           VALUES (?, ?, ?, ?, 'clinician', 1, ?, ?)''',
        (patient_id, name, onset_year, data.get('notes', ''), doctor_id, doctor_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/api/patient/<int:patient_id>/medical-history/condition/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_clinician_update_condition(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_conditions WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    onset_year, err = _validate_year(data.get('onset_year'), 'onset_year')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_conditions
           SET name = ?, onset_year = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (name, onset_year, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'updated'})


@app.route('/api/patient/<int:patient_id>/medical-history/condition/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_clinician_delete_condition(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_conditions WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_conditions WHERE id = ?', (rec_id,))
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/patient/<int:patient_id>/medical-history/condition/<int:rec_id>/verify', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_verify_condition(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_conditions WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db(
        'UPDATE medical_conditions SET verified = 1, verified_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], rec_id)
    )
    return jsonify({'status': 'verified'})


@app.route('/api/patient/<int:patient_id>/medical-history/surgery', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_add_surgery(patient_id):
    data = request.get_json(silent=True) or request.form
    procedure = (data.get('procedure') or '').strip()
    if not procedure:
        return jsonify({'error': 'procedure is required'}), 400
    surgery_date, err = _validate_date(data.get('surgery_date'), 'surgery_date')
    if err:
        return jsonify({'error': err}), 400
    doctor_id = session['user_id']
    rec_id = execute_db(
        '''INSERT INTO medical_surgeries
               (patient_id, procedure, surgery_date, body_region, outcome, notes,
                entry_mode, verified, entered_by, verified_by)
           VALUES (?, ?, ?, ?, ?, ?, 'clinician', 1, ?, ?)''',
        (patient_id, procedure, surgery_date, (data.get('body_region') or '')[:100],
         data.get('outcome', ''), data.get('notes', ''), doctor_id, doctor_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/api/patient/<int:patient_id>/medical-history/surgery/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_clinician_update_surgery(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_surgeries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    procedure = (data.get('procedure') or '').strip()
    if not procedure:
        return jsonify({'error': 'procedure is required'}), 400
    surgery_date, err = _validate_date(data.get('surgery_date'), 'surgery_date')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_surgeries
           SET procedure = ?, surgery_date = ?, body_region = ?, outcome = ?, notes = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
        (procedure, surgery_date, (data.get('body_region') or '')[:100],
         data.get('outcome', ''), data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'updated'})


@app.route('/api/patient/<int:patient_id>/medical-history/surgery/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_clinician_delete_surgery(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_surgeries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_surgeries WHERE id = ?', (rec_id,))
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/patient/<int:patient_id>/medical-history/surgery/<int:rec_id>/verify', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_verify_surgery(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_surgeries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db(
        'UPDATE medical_surgeries SET verified = 1, verified_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], rec_id)
    )
    return jsonify({'status': 'verified'})


@app.route('/api/patient/<int:patient_id>/medical-history/injury', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_add_injury(patient_id):
    data = request.get_json(silent=True) or request.form
    body_region = (data.get('body_region') or '').strip()
    if not body_region:
        return jsonify({'error': 'body_region is required'}), 400
    injury_date, err = _validate_date(data.get('injury_date'), 'injury_date')
    if err:
        return jsonify({'error': err}), 400
    doctor_id = session['user_id']
    rec_id = execute_db(
        '''INSERT INTO medical_injuries
               (patient_id, body_region, injury_description, related_to_current,
                recovery_complete, recurrence, injury_date, notes,
                entry_mode, verified, entered_by, verified_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'clinician', 1, ?, ?)''',
        (patient_id, body_region[:100], data.get('injury_description', ''),
         _coerce_bool(data.get('related_to_current')),
         _coerce_bool(data.get('recovery_complete')),
         _coerce_bool(data.get('recurrence')),
         injury_date, data.get('notes', ''), doctor_id, doctor_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/api/patient/<int:patient_id>/medical-history/injury/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_clinician_update_injury(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_injuries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    body_region = (data.get('body_region') or '').strip()
    if not body_region:
        return jsonify({'error': 'body_region is required'}), 400
    injury_date, err = _validate_date(data.get('injury_date'), 'injury_date')
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_injuries
           SET body_region = ?, injury_description = ?, related_to_current = ?,
               recovery_complete = ?, recurrence = ?, injury_date = ?,
               notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
        (body_region[:100], data.get('injury_description', ''),
         _coerce_bool(data.get('related_to_current')),
         _coerce_bool(data.get('recovery_complete')),
         _coerce_bool(data.get('recurrence')),
         injury_date, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'updated'})


@app.route('/api/patient/<int:patient_id>/medical-history/injury/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_clinician_delete_injury(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_injuries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_injuries WHERE id = ?', (rec_id,))
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/patient/<int:patient_id>/medical-history/injury/<int:rec_id>/verify', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_verify_injury(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_injuries WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db(
        'UPDATE medical_injuries SET verified = 1, verified_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], rec_id)
    )
    return jsonify({'status': 'verified'})


@app.route('/api/patient/<int:patient_id>/medical-history/medication', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_add_medication(patient_id):
    data = request.get_json(silent=True) or request.form
    drug_name = (data.get('drug_name') or '').strip()[:200]
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400
    end_date, err = _validate_date(data.get('end_date'), 'end_date', allow_future=True)
    if err:
        return jsonify({'error': err}), 400
    doctor_id = session['user_id']
    rec_id = execute_db(
        '''INSERT INTO medical_medications
               (patient_id, drug_name, indication, active, end_date,
                entry_mode, verified, entered_by, verified_by)
           VALUES (?, ?, ?, ?, ?, 'clinician', 1, ?, ?)''',
        (patient_id, drug_name, data.get('indication', ''),
         _coerce_bool(data.get('active', 1)), end_date, doctor_id, doctor_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/api/patient/<int:patient_id>/medical-history/medication/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_clinician_update_medication(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_medications WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    drug_name = (data.get('drug_name') or '').strip()[:200]
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400
    end_date, err = _validate_date(data.get('end_date'), 'end_date', allow_future=True)
    if err:
        return jsonify({'error': err}), 400
    execute_db(
        '''UPDATE medical_medications
           SET drug_name = ?, indication = ?, active = ?, end_date = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
        (drug_name, data.get('indication', ''),
         _coerce_bool(data.get('active', 1)), end_date, rec_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'updated'})


@app.route('/api/patient/<int:patient_id>/medical-history/medication/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_clinician_delete_medication(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_medications WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_medications WHERE id = ?', (rec_id,))
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/patient/<int:patient_id>/medical-history/medication/<int:rec_id>/verify', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_verify_medication(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_medications WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db(
        'UPDATE medical_medications SET verified = 1, verified_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], rec_id)
    )
    return jsonify({'status': 'verified'})


@app.route('/api/patient/<int:patient_id>/medical-history/family-history', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_add_family_history(patient_id):
    data = request.get_json(silent=True) or request.form
    condition = (data.get('condition') or '').strip()
    relation = (data.get('relation') or '').strip()
    if not condition or not relation:
        return jsonify({'error': 'condition and relation are required'}), 400
    doctor_id = session['user_id']
    rec_id = execute_db(
        '''INSERT INTO medical_family_history
               (patient_id, condition, relation, notes, entry_mode, verified, entered_by, verified_by)
           VALUES (?, ?, ?, ?, 'clinician', 1, ?, ?)''',
        (patient_id, condition, relation, data.get('notes', ''), doctor_id, doctor_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'id': rec_id, 'status': 'created'}), 201


@app.route('/api/patient/<int:patient_id>/medical-history/family-history/<int:rec_id>', methods=['PUT'])
@login_required
@role_required('doctor')
def api_clinician_update_family_history(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_family_history WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or request.form
    condition = (data.get('condition') or '').strip()
    relation = (data.get('relation') or '').strip()
    if not condition or not relation:
        return jsonify({'error': 'condition and relation are required'}), 400
    execute_db(
        '''UPDATE medical_family_history
           SET condition = ?, relation = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
        (condition, relation, data.get('notes', ''), rec_id)
    )
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'updated'})


@app.route('/api/patient/<int:patient_id>/medical-history/family-history/<int:rec_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_clinician_delete_family_history(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_family_history WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db('DELETE FROM medical_family_history WHERE id = ?', (rec_id,))
    _recompute_risk_cache(patient_id)
    return jsonify({'status': 'deleted'})


@app.route('/api/patient/<int:patient_id>/medical-history/family-history/<int:rec_id>/verify', methods=['POST'])
@login_required
@role_required('doctor')
def api_clinician_verify_family_history(patient_id, rec_id):
    row = query_db('SELECT patient_id FROM medical_family_history WHERE id = ?', (rec_id,), one=True)
    if not row or row['patient_id'] != patient_id:
        return jsonify({'error': 'not found'}), 404
    execute_db(
        'UPDATE medical_family_history SET verified = 1, verified_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session['user_id'], rec_id)
    )
    return jsonify({'status': 'verified'})


# ============================================================================

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


@app.route('/api/doctor/specialties', methods=['POST'])
@login_required
@role_required('doctor')
def api_doctor_specialties():
    """Save doctor specialty selections."""
    data = request.get_json(force=True) or {}
    specialties = data.get('specialties', [])
    # Validate against known list
    valid = [s for s in specialties if s in DOCTOR_SPECIALTIES]
    doctor_id = session['user_id']
    execute_db('DELETE FROM doctor_specialties WHERE doctor_id = ?', (doctor_id,))
    for spec in valid:
        execute_db(
            'INSERT INTO doctor_specialties (doctor_id, specialty) VALUES (?, ?)',
            (doctor_id, spec)
        )
    return jsonify({'ok': True, 'saved': valid})


@app.route('/clinician/plan-editor', methods=['GET'])
@login_required
@role_required('doctor')
def plan_editor():
    """Rehab Plan Editor — all patients' plans in one view"""
    doctor_id = session['user_id']

    # Patients already assigned to this doctor
    assigned_patients = query_db('''
        SELECT u.id, u.name, p.condition
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON p.user_id = dp.patient_id
        WHERE dp.doctor_id = ?
    ''', (doctor_id,))
    assigned_patients = [dict(p) for p in assigned_patients] if assigned_patients else []
    assigned_ids = {p['id'] for p in assigned_patients}

    # Specialty-matched unassigned patients (show so doctor can assign to them)
    spec_rows = query_db('SELECT specialty FROM doctor_specialties WHERE doctor_id = ?', (doctor_id,))
    doctor_specialties_list = [dict(r)['specialty'] for r in spec_rows] if spec_rows else []

    if doctor_specialties_list:
        _ph = ','.join('?' * len(doctor_specialties_list))
        unassigned_matches = query_db(f'''
            SELECT u.id, u.name, p.condition
            FROM users u
            JOIN patients p ON u.id = p.user_id
            WHERE p.specialty_needed IN ({_ph})
              AND u.id NOT IN (SELECT patient_id FROM doctor_patient WHERE doctor_id = ?)
        ''', doctor_specialties_list + [doctor_id])
    else:
        # No specialties set — show ALL unassigned so doctor can claim them
        unassigned_matches = query_db('''
            SELECT u.id, u.name, p.condition
            FROM users u
            JOIN patients p ON u.id = p.user_id
            WHERE u.id NOT IN (SELECT patient_id FROM doctor_patient)
        ''')
    unassigned_matches = [dict(p) for p in unassigned_matches] if unassigned_matches else []

    # Merge: assigned first, then unmatched-unassigned (dedup by id)
    seen = set(assigned_ids)
    extra = [p for p in unassigned_matches if p['id'] not in seen]
    all_patients = assigned_patients + extra

    # If a specific patient_id is requested, show only that patient
    selected_patient_id = request.args.get('patient_id', type=int)
    if selected_patient_id:
        patients = [p for p in all_patients if p['id'] == selected_patient_id]
        if not patients:
            patients = all_patients  # fallback if not found
    else:
        patients = all_patients

    # For every patient, sync patient_exercises → workouts, then fetch workouts
    for pat in patients:
        # 1. Get exercises assigned via patient_exercises (condition-based defaults)
        assigned = query_db('''
            SELECT pe.exercise_id
            FROM patient_exercises pe
            WHERE pe.patient_id = ? AND pe.enabled = 1
        ''', (pat['id'],))
        assigned_ids = [a['exercise_id'] for a in assigned] if assigned else []

        # 2. Get exercises already in workouts table (active)
        existing_workout_exids = query_db('''
            SELECT exercise_id FROM workouts
            WHERE patient_id = ? AND is_active = 1
        ''', (pat['id'],))
        existing_ids = set(e['exercise_id'] for e in existing_workout_exids) if existing_workout_exids else set()

        # 3. Auto-create workout entries for patient_exercises not yet in workouts
        for ex_id in assigned_ids:
            if ex_id not in existing_ids:
                execute_db('''
                    INSERT INTO workouts
                    (patient_id, exercise_id, assigned_by_doctor_id, sets, reps, frequency, instructions, is_active)
                    VALUES (?, ?, ?, 3, 10, 'Daily', '', 1)
                ''', (pat['id'], ex_id, get_primary_doctor_id_for_patient(pat['id'])))

        # 4. Now fetch the full workout list
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
                           exercises=exercises,
                           selected_patient_id=selected_patient_id)


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

    # Ensure this doctor is linked to the patient they are editing.
    execute_db(
        'INSERT OR IGNORE INTO doctor_patient (doctor_id, patient_id) VALUES (?, ?)',
        (session['user_id'], patient_id)
    )

    # Also ensure the exercise is tracked in patient_exercises
    execute_db('''
        INSERT OR IGNORE INTO patient_exercises (patient_id, exercise_id, enabled)
        VALUES (?, ?, 1)
    ''', (patient_id, exercise_id))
    # Re-enable if it was previously disabled
    execute_db('''
        UPDATE patient_exercises SET enabled = 1
        WHERE patient_id = ? AND exercise_id = ?
    ''', (patient_id, exercise_id))

    execute_db('''
        INSERT INTO workouts
        (patient_id, exercise_id, assigned_by_doctor_id, sets, reps, frequency, instructions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (patient_id, exercise_id, session['user_id'], sets, reps, frequency, instructions))

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

    # Resolve patient and enforce doctor-patient link for ownership routing.
    workout_row = query_db('SELECT patient_id FROM workouts WHERE id = ?', (workout_id,), one=True)
    if workout_row:
        execute_db(
            'INSERT OR IGNORE INTO doctor_patient (doctor_id, patient_id) VALUES (?, ?)',
            (session['user_id'], workout_row['patient_id'])
        )

    execute_db('''
        UPDATE workouts
        SET sets = COALESCE(?, sets),
            reps = COALESCE(?, reps),
            frequency = COALESCE(?, frequency),
            instructions = COALESCE(?, instructions),
            assigned_by_doctor_id = ?
        WHERE id = ?
    ''', (sets, reps, frequency, instructions, session['user_id'], workout_id))

    return jsonify({'ok': True})


@app.route('/api/plan/remove-workout/<int:workout_id>', methods=['DELETE'])
@login_required
@role_required('doctor')
def api_plan_remove_workout(workout_id):
    """Soft-delete a workout from a patient's plan and disable in patient_exercises"""
    # Get the exercise_id and patient_id before deactivating
    w = query_db('SELECT patient_id, exercise_id FROM workouts WHERE id = ?', (workout_id,), one=True)
    if w:
        execute_db(
            'INSERT OR IGNORE INTO doctor_patient (doctor_id, patient_id) VALUES (?, ?)',
            (session['user_id'], w['patient_id'])
        )
    execute_db('UPDATE workouts SET is_active = 0 WHERE id = ?', (workout_id,))
    # Also disable in patient_exercises so it stays removed
    if w:
        execute_db('''
            UPDATE patient_exercises SET enabled = 0
            WHERE patient_id = ? AND exercise_id = ?
        ''', (w['patient_id'], w['exercise_id']))
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

    # Real-time: mark any appointments whose time has now passed as 'missed'
    _mark_missed_appointments()

    appointments = query_db('''
        SELECT a.*, u.name as patient_name, p.condition, p.adherence_rate, p.avg_pain_level, p.avg_quality_score
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        LEFT JOIN patients p ON u.id = p.user_id
        WHERE a.doctor_id = ? AND a.status = 'scheduled'
          AND (
            a.appointment_date > date('now')
            OR (a.appointment_date = date('now')
                AND a.appointment_time > strftime('%H:%M', 'now', 'localtime'))
          )
        ORDER BY a.appointment_date, a.appointment_time
    ''', (session['user_id'],))

    # Past completed/missed/cancelled appointments
    past_appointments = query_db('''
        SELECT a.*, u.name as patient_name, p.condition
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        LEFT JOIN patients p ON u.id = p.user_id
        WHERE a.doctor_id = ? AND a.status IN ('completed', 'missed', 'cancelled')
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 20
    ''', (session['user_id'],))

    # Plain-dict calendar events for JSON serialisation in template
    cal_events = (
        [{'date': r['appointment_date'], 'status': 'upcoming'} for r in (appointments or [])] +
        [{'date': r['appointment_date'], 'status': r['status']} for r in (past_appointments or [])]
    )

    return render_template('clinician/consultation.html',
                         patients=patients if patients else [],
                         appointments=appointments if appointments else [],
                         past_appointments=past_appointments if past_appointments else [],
                         cal_events=cal_events)


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

    # Fetch open messages submitted by this caregiver
    my_messages = query_db('''
        SELECT cm.*, u.name as patient_name
        FROM caregiver_messages cm
        JOIN users u ON cm.patient_id = u.id
        WHERE cm.caregiver_id = ?
        ORDER BY cm.created_at DESC
        LIMIT 20
    ''', (session['user_id'],))

    return render_template('caregiver/dashboard.html',
                         patients=patients_list,
                         recent_sessions=recent_sessions if recent_sessions else [],
                         alerts=alerts,
                         my_requests=my_pending_requests if my_pending_requests else [],
                         chat_patient_id=first_patient_id,
                         caregiver_patient_list=caregiver_patient_list,
                         my_messages=my_messages if my_messages else [])


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


# ==================== CAREGIVER MESSAGES ====================

@app.route('/api/caregiver/message', methods=['POST'])
@login_required
@role_required('caregiver')
def caregiver_submit_message():
    """Caregiver submits a complaint or query for a patient."""
    data = request.get_json(force=True) or {}
    patient_id = data.get('patient_id')
    message_type = data.get('message_type', 'query')
    message = (data.get('message') or '').strip()

    if not patient_id or not message:
        return jsonify({'ok': False, 'error': 'patient_id and message are required'}), 400
    if message_type not in ('complaint', 'query', 'encouragement'):
        return jsonify({'ok': False, 'error': 'message_type must be complaint, query, or encouragement'}), 400

    # Verify caregiver monitors this patient
    link = query_db(
        'SELECT 1 FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
        (session['user_id'], patient_id), one=True
    )
    if not link:
        return jsonify({'ok': False, 'error': 'Not authorised for this patient'}), 403

    execute_db(
        'INSERT INTO caregiver_messages (caregiver_id, patient_id, message_type, message) VALUES (?, ?, ?, ?)',
        (session['user_id'], patient_id, message_type, message)
    )
    return jsonify({'ok': True})


@app.route('/api/caregiver/messages/<int:patient_id>')
@login_required
def get_caregiver_messages(patient_id):
    """Get caregiver messages for a patient. Accessible by the patient, assigned doctor, or caregivers."""
    role = session.get('role')
    uid = session['user_id']

    if role == 'patient' and uid != patient_id:
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403
    if role == 'doctor':
        assigned = query_db(
            'SELECT 1 FROM doctor_patient WHERE doctor_id = ? AND patient_id = ?',
            (uid, patient_id), one=True
        )
        if not assigned:
            return jsonify({'ok': False, 'error': 'Forbidden'}), 403
    if role == 'caregiver':
        link = query_db(
            'SELECT 1 FROM caregiver_patient WHERE caregiver_id = ? AND patient_id = ?',
            (uid, patient_id), one=True
        )
        if not link:
            return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    messages = query_db('''
        SELECT cm.id, cm.message_type, cm.message, cm.status,
               cm.created_at, cm.resolved_at, cm.resolved_note,
               u.name as caregiver_name,
               ru.name as resolved_by_name
        FROM caregiver_messages cm
        JOIN users u ON cm.caregiver_id = u.id
        LEFT JOIN users ru ON cm.resolved_by = ru.id
        WHERE cm.patient_id = ?
        ORDER BY cm.created_at DESC
    ''', (patient_id,))

    return jsonify({'ok': True, 'messages': [dict(m) for m in (messages or [])]})


@app.route('/api/caregiver/message/<int:msg_id>/resolve', methods=['POST'])
@login_required
def resolve_caregiver_message(msg_id):
    """Resolve a caregiver message. Doctor or patient can resolve."""
    role = session.get('role')
    if role not in ('doctor', 'patient'):
        return jsonify({'ok': False, 'error': 'Only doctors or patients can resolve messages'}), 403

    data = request.get_json(force=True) or {}
    resolved_note = (data.get('note') or '').strip()

    msg = query_db('SELECT * FROM caregiver_messages WHERE id = ?', (msg_id,), one=True)
    if not msg:
        return jsonify({'ok': False, 'error': 'Message not found'}), 404

    uid = session['user_id']
    patient_id = msg['patient_id']

    if role == 'patient' and uid != patient_id:
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403
    if role == 'doctor':
        assigned = query_db(
            'SELECT 1 FROM doctor_patient WHERE doctor_id = ? AND patient_id = ?',
            (uid, patient_id), one=True
        )
        if not assigned:
            return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    execute_db(
        """UPDATE caregiver_messages
           SET status = 'resolved', resolved_by = ?, resolved_note = ?,
               resolved_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (uid, resolved_note, msg_id)
    )
    return jsonify({'ok': True})


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

# Initialize the CV pipelines (enabled by default for local dev; set ENABLE_CV_PIPELINES=0 to skip)
ENABLE_CV_PIPELINES = os.environ.get("ENABLE_CV_PIPELINES", "1") == "1"

if ENABLE_CV_PIPELINES:
    try:
        PIPELINE = WebRehabPipeline()
        print("[INIT] WebRehabPipeline (General Rehab) initialized successfully")
    except Exception as e:
        PIPELINE = None
        print(f"[WARNING] WebRehabPipeline failed to initialize: {e}")

    try:
        KERAAL_PIPELINE = KeraalRehabPipeline()
        print("[INIT] KeraalRehabPipeline (Low Back Pain) initialized successfully")
    except Exception as e:
        KERAAL_PIPELINE = None
        print(f"[WARNING] KeraalRehabPipeline failed to initialize: {e}")
else:
    PIPELINE = None
    KERAAL_PIPELINE = None
    print("[INIT] CV pipelines skipped at startup (set ENABLE_CV_PIPELINES=1 to enable)")


def _extract_pose_landmarks_for_calibration(frame_b64):
    """
    Lightweight pose extraction for camera setup checks.
    Reuses whichever MediaPipe-backed pipeline is available without
    touching the rep-counting/session state machines.
    """
    if PIPELINE is not None and hasattr(PIPELINE, "_extract_mediapipe_landmarks"):
        return PIPELINE._extract_mediapipe_landmarks(frame_b64)

    if KERAAL_PIPELINE is not None and hasattr(KERAAL_PIPELINE, "_extract_mediapipe_landmarks_keraal"):
        return KERAAL_PIPELINE._extract_mediapipe_landmarks_keraal(frame_b64)

    return None, None


@app.route("/api/camera/calibration", methods=["POST"])
@login_required
@role_required('patient')
def api_camera_calibration():
    """
    Run pose detection on a single webcam frame for pre-session camera setup.
    Returns raw landmarks so the frontend can compute framing score/guidance.
    """
    if PIPELINE is None and KERAAL_PIPELINE is None:
        return jsonify({"ok": False, "error": "Pose pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"ok": False, "error": "frame_b64 missing"}), 400

    try:
        frame, landmarks = _extract_pose_landmarks_for_calibration(frame_b64)
        if frame is None:
            return jsonify({"ok": False, "error": "Could not decode frame"}), 400

        frame_height, frame_width = frame.shape[:2]
        landmarks_list = landmarks.tolist() if hasattr(landmarks, "tolist") else []

        return jsonify({
            "ok": True,
            "pose_detected": bool(landmarks_list),
            "landmarks": landmarks_list,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "timestamp": time.time(),
        })
    except Exception as e:
        print(f"❌ Camera calibration error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


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

    # Store in Flask session so frame endpoints can log telemetry
    session['current_session_id'] = row['id']

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

    # Auto-adaptive suggestion trigger (no model changes; only when wrong form is detected)
    try:
        patient_id = session['user_id']
        if count > 0:
            wrong_stats = query_db('''
                SELECT
                    COUNT(*) AS total_frames,
                    SUM(CASE WHEN UPPER(COALESCE(status, '')) IN ('WRONG', 'INCORRECT') THEN 1 ELSE 0 END) AS wrong_frames
                FROM session_frames
                WHERE session_id = ? AND patient_id = ?
            ''', (session_id, patient_id), one=True)

            total_frames = int(wrong_stats['total_frames'] or 0) if wrong_stats else 0
            wrong_frames = int(wrong_stats['wrong_frames'] or 0) if wrong_stats else 0
            has_wrong_form = wrong_frames > 0

            if not has_wrong_form:
                return jsonify({'ok': True, 'session_id': session_id})

            severity = None
            reason = None
            if avg_quality < 25 or completed_perc < 50:
                severity = 'high'
                reason = f'Wrong form detected ({wrong_frames}/{max(total_frames, 1)} frames) with low quality ({avg_quality}/100) or low completion ({completed_perc}%)'
            elif pain_after >= 7:
                severity = 'high'
                reason = f'Wrong form detected ({wrong_frames}/{max(total_frames, 1)} frames) and high pain after session ({pain_after}/10)'
            elif avg_quality < 40:
                severity = 'medium'
                reason = f'Wrong form detected ({wrong_frames}/{max(total_frames, 1)} frames); quality below target ({avg_quality}/100)'

            if reason:
                workout = query_db('''
                    SELECT id, sets, reps, frequency
                    FROM workouts
                    WHERE patient_id = ? AND is_active = 1
                    ORDER BY id
                    LIMIT 1
                ''', (patient_id,), one=True)

                suggested_sets = max(1, int(workout['sets']) - 1) if workout else None
                suggested_reps = max(5, int(workout['reps']) - 2) if workout else None
                suggested_frequency = '3x per week' if severity == 'high' else (workout['frequency'] if workout else None)

                create_adaptive_suggestion(
                    patient_id=patient_id,
                    source='auto_session_analysis',
                    reason=reason,
                    suggested_change='Reduce short-term intensity and review form with clinician approval.',
                    severity=severity,
                    session_id=session_id,
                    workout_id=(workout['id'] if workout else None),
                    suggested_sets=suggested_sets,
                    suggested_reps=suggested_reps,
                    suggested_frequency=suggested_frequency,
                    app_confidence=0.82 if severity == 'high' else 0.68,
                )
    except Exception as e:
        print(f"[WARN] Adaptive suggestion auto-trigger failed: {e}")

    # Recalculate adherence after every completed session
    recalculate_adherence(session['user_id'])

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


@app.route('/api/chat/transcribe', methods=['POST'])
@login_required
def api_chat_transcribe():
    """Transcribe audio to text using MERaLiON API for voice chat input."""
    if not CHATBOT_AVAILABLE:
        return jsonify({"error": "Chatbot modules not available"}), 503
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files['audio']

    try:
        audio_bytes = audio_file.read()
        filename = audio_file.filename or "audio.webm"
        print(f"[TRANSCRIBE] Audio size: {len(audio_bytes)} bytes, filename: {filename}")

        if not audio_bytes:
            return jsonify({"error": "Empty audio payload"}), 400

        transcript = ""
        provider_errors = []
        if WHISPER_AVAILABLE:
            try:
                transcript = whisper_transcribe(audio_bytes, filename)
                print(f"[Whisper] Transcript: '{transcript}'")
            except Exception as whisper_err:
                provider_errors.append(f"Whisper: {whisper_err}")
                print(f"[Whisper] Failed, falling back to Meralion: {whisper_err}")

        # Fallback to Meralion if Whisper unavailable or returned empty
        if not transcript and CHATBOT_AVAILABLE:
            try:
                print("[TRANSCRIBE] Falling back to Meralion transcription")
                transcript = transcribe_audio(audio_bytes, filename)
                print(f"[Meralion] Transcript: '{transcript}'")
            except Exception as mer_err:
                provider_errors.append(f"Meralion: {mer_err}")
                print(f"[Meralion] Failed: {mer_err}")

        if not transcript:
            return jsonify({
                "error": "Transcription unavailable",
                "detail": " ; ".join(provider_errors) if provider_errors else "No speech detected"
            }), 502

        return jsonify({"transcript": transcript})
    except Exception as e:
        print(f"[TRANSCRIBE ERROR] {e}")
        return jsonify({"error": "Transcription failed", "detail": str(e)}), 500


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

    role = session.get('role')
    user_id = session['user_id']

    # Guard: reset chat history if it belongs to a different user
    if session.get('chat_owner') != user_id:
        session['chat_history'] = []
        session['chat_owner'] = user_id

    if 'chat_history' not in session:
        session['chat_history'] = []
    conversation_history = session['chat_history']

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
Surgery Date: {patient_info['surgery_date'] or 'N/A'}
Current Rehab Week: {patient_info['current_week']}
Adherence Rate: {patient_info['adherence_rate']}%
Avg Pain Level: {patient_info['avg_pain_level']}/10
Avg Quality Score: {patient_info['avg_quality_score']}/100
Completed Sessions: {patient_info['completed_sessions']}
Streak Days: {patient_info['streak_days']}
"""
            if recent_sessions_db:
                patient_context += "\nRecent Sessions:\n"
                for s in recent_sessions_db:
                    patient_context += f"- {s['exercise_name']}: Quality {s['quality_score']}, Pain {s['pain_after']}/10 ({s['completed_at']})\n"

        # Get workouts for exercise plan context
        workouts = query_db('''
            SELECT e.name, e.category, w.sets, w.reps, w.frequency, w.instructions FROM workouts w
            JOIN exercises e ON w.exercise_id = e.id
            WHERE w.patient_id = ? AND w.is_active = 1
        ''', (patient_id,))
        current_plan = ", ".join([w['name'] for w in workouts]) if workouts else "general fitness plan"
        if workouts:
            patient_context += "\nActive Exercise Plan:\n"
            for w in workouts:
                patient_context += f"- {w['name']} ({w['category'] or 'general'}): {w['sets']}x{w['reps']} {w['frequency']}"
                if w['instructions']:
                    patient_context += f" — {w['instructions']}"
                patient_context += "\n"

        # Get upcoming appointments
        upcoming_appts = query_db('''
            SELECT a.appointment_date, a.appointment_time, a.status, u.name as doctor_name
            FROM appointments a JOIN users u ON a.doctor_id = u.id
            WHERE a.patient_id = ? AND a.status = 'scheduled'
            ORDER BY a.appointment_date ASC LIMIT 3
        ''', (patient_id,))
        if upcoming_appts:
            patient_context += "\nUpcoming Appointments:\n"
            for a in upcoming_appts:
                patient_context += f"- {a['appointment_date']} {a['appointment_time']} with {a['doctor_name']} ({a['status']})\n"

        # Get recent clinician notes
        recent_notes = query_db('''
            SELECT cn.note_text, cn.created_at, u.name as doctor_name
            FROM clinician_notes cn JOIN users u ON cn.doctor_id = u.id
            WHERE cn.patient_id = ? ORDER BY cn.created_at DESC LIMIT 3
        ''', (patient_id,))
        if recent_notes:
            patient_context += "\nRecent Clinician Notes:\n"
            for n in recent_notes:
                patient_context += f"- Dr. {n['doctor_name']} ({n['created_at']}): {n['note_text'][:200]}\n"

        # Get assigned doctor info
        doctor_info = query_db('''
            SELECT u.name, u.email, u.phone FROM doctor_patient dp
            JOIN users u ON dp.doctor_id = u.id WHERE dp.patient_id = ?
        ''', (patient_id,))
        if doctor_info:
            patient_context += "\nAssigned Doctor(s): " + ", ".join([d['name'] for d in doctor_info]) + "\n"

        # Get caregiver info
        caregiver_info = query_db('''
            SELECT u.name, cp.relationship FROM caregiver_patient cp
            JOIN users u ON cp.caregiver_id = u.id WHERE cp.patient_id = ?
        ''', (patient_id,))
        if caregiver_info:
            patient_context += "Caregiver(s): " + ", ".join([f"{c['name']} ({c['relationship']})" for c in caregiver_info]) + "\n"

        # -- Full session reports for all completed sessions --
        all_sessions = query_db('''
            SELECT s.id, s.started_at, s.completed_at, s.pain_before, s.pain_after,
                   s.effort_level, s.quality_score, s.completed_perc, s.notes
            FROM sessions s
            WHERE s.patient_id = ? AND s.completed_at IS NOT NULL
            ORDER BY s.completed_at DESC
            LIMIT 20
        ''', (patient_id,))
        if all_sessions:
            patient_context += "\n=== FULL SESSION REPORTS (most recent 20) ===\n"
            for sess in all_sessions:
                patient_context += f"\nSession #{sess['id']} ({sess['completed_at']}):\n"
                patient_context += f"  Quality: {sess['quality_score']}/100, Completion: {sess['completed_perc']}%\n"
                patient_context += f"  Pain: {sess['pain_before']}/10 before → {sess['pain_after']}/10 after\n"
                patient_context += f"  Effort Level: {sess['effort_level']}/10\n"
                if sess['notes']:
                    patient_context += f"  Notes: {sess['notes'][:150]}\n"

                # Get exercises for this session
                sess_exercises = query_db('''
                    SELECT se.exercise_name, se.quality_score, se.sets_required, se.sets_completed,
                           se.exercise_start_time, se.exercise_end_time
                    FROM session_exercises se
                    WHERE se.session_id = ?
                ''', (sess['id'],))
                if sess_exercises:
                    for se in sess_exercises:
                        ex_name = se['exercise_name'] or 'Unknown'
                        patient_context += f"    - {ex_name}: Quality {se['quality_score']}/100"
                        if se['sets_required'] and se['sets_completed']:
                            patient_context += f", Sets required: {se['sets_required']}, completed: {se['sets_completed']}"
                        patient_context += "\n"

                # Get frame-level summary for this session
                frame_summary = query_db('''
                    SELECT exercise_name, COUNT(*) as frame_count,
                           AVG(score) as avg_score, MAX(rep_count) as max_reps
                    FROM session_frames
                    WHERE session_id = ?
                    GROUP BY exercise_name
                ''', (sess['id'],))
                if frame_summary:
                    for fr in frame_summary:
                        if fr['exercise_name']:
                            patient_context += f"    [Telemetry] {fr['exercise_name']}: {fr['frame_count']} frames, avg score {fr['avg_score']:.1f}, max reps {fr['max_reps']}\n"

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
            assigned_by_doctor_id INTEGER,
            sets INTEGER DEFAULT 3,
            reps INTEGER DEFAULT 10,
            frequency TEXT DEFAULT 'Daily',
            instructions TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id),
            FOREIGN KEY (assigned_by_doctor_id) REFERENCES users(id)
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

        CREATE TABLE IF NOT EXISTS patient_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id),
            UNIQUE(patient_id, exercise_id)
        );

        CREATE TABLE IF NOT EXISTS adaptive_plan_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            session_id INTEGER,
            workout_id INTEGER,
            source TEXT NOT NULL DEFAULT 'auto_session_analysis',
            reason TEXT NOT NULL,
            suggested_change TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            suggested_sets INTEGER,
            suggested_reps INTEGER,
            suggested_frequency TEXT,
            patient_note TEXT,
            app_confidence REAL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            review_note TEXT,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (doctor_id) REFERENCES users(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (workout_id) REFERENCES workouts(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        );
    ''')
    conn.commit()
    
    # --- Migrations for existing databases ---
    # Add new columns to sessions table if upgrading from old schema
    migrations = [
        ("sessions", "session_group_id", "TEXT"),
        ("sessions", "started_at", "TIMESTAMP"),
        ("sessions", "completed_perc", "REAL DEFAULT 0"),
        ("workouts", "assigned_by_doctor_id", "INTEGER"),
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

    # ── Frame-level session telemetry ──────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            program TEXT NOT NULL DEFAULT 'general',
            exercise_name TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT '',
            rep_count INTEGER NOT NULL DEFAULT 0,
            set_count INTEGER NOT NULL DEFAULT 1,
            asymmetry_pct REAL,
            rom_angle REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (patient_id) REFERENCES users(id)
        )
    ''')
    # Index for fast lookup by session
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_frames_session ON session_frames(session_id)')
    except Exception:
        pass
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adaptive_suggestions_doctor_status ON adaptive_plan_suggestions(doctor_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adaptive_suggestions_patient_created ON adaptive_plan_suggestions(patient_id, created_at)')
    except Exception:
        pass
    
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
    
    # ---- Seed / update exercises table with canonical list ----
    CANONICAL_EXERCISES = [
        ('Lifting of Arms', 'Shoulder', 'Stand upright, raise both arms from your sides to above your head, then slowly lower. Keep elbows slightly bent.'),
        ('Lateral Trunk Tilt', 'Spine', 'Stand with feet shoulder-width apart. Slowly tilt your trunk to one side, return to center, then tilt to the other side.'),
        ('Trunk Rotation', 'Spine', 'Stand with arms relaxed. Rotate your upper body to the left, return to center, then rotate right. Keep hips facing forward.'),
        ('Squat', 'Knee', 'Stand with feet shoulder-width apart. Lower your hips by bending your knees, keeping your back straight. Rise slowly.'),
        ('Trunk Rotation & Target Touch', 'Spine', 'Stand upright, rotate your trunk and reach toward targets at various positions. Combine trunk rotation with arm extension.'),
        ('Pelvis Rotation', 'Hip', 'Stand upright and gently rotate your pelvis in a controlled circular motion while keeping your upper body stable.'),
        ('Forward Flexion', 'Spine', 'Stand upright, slowly bend forward from your hips keeping your back straight. Reach towards your toes, then return upright.'),
        ('Flank Stretch', 'Spine', 'Stand upright, raise one arm overhead and slowly stretch to the opposite side. Alternate sides.'),
        ('Torso Rotation', 'Spine', 'Stand with feet apart, rotate your trunk gently to each side. Keep your lower body stable throughout.'),
    ]
    canonical_names = [e[0] for e in CANONICAL_EXERCISES]

    # Remove any exercises NOT in the canonical list
    placeholders = ','.join('?' * len(canonical_names))
    cursor.execute(f"DELETE FROM exercises WHERE name NOT IN ({placeholders})", canonical_names)

    # Insert/update canonical exercises
    for ex_name, ex_category, ex_desc in CANONICAL_EXERCISES:
        cursor.execute("SELECT id FROM exercises WHERE name = ?", (ex_name,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE exercises SET category = ?, description = ? WHERE name = ?", (ex_category, ex_desc, ex_name))
        else:
            cursor.execute(
                "INSERT INTO exercises (name, category, description, difficulty) VALUES (?, ?, ?, 1)",
                (ex_name, ex_category, ex_desc)
            )
    print(f"[INIT] Exercises table seeded with {len(CANONICAL_EXERCISES)} canonical exercises")

    # Caregiver messages (complaints & queries)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS caregiver_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            message_type TEXT NOT NULL CHECK(message_type IN ('complaint', 'query', 'encouragement')),
            message TEXT NOT NULL,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'resolved')),
            resolved_by INTEGER,
            resolved_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (caregiver_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (resolved_by) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()


# Ensure tables exist on startup
ensure_tables_exist()


def _mark_missed_appointments():
    """Auto-mark any 'scheduled' appointment whose date+time has passed as 'missed'."""
    with app.app_context():
        execute_db("""
            UPDATE appointments
            SET status = 'missed'
            WHERE status = 'scheduled'
              AND (
                appointment_date < date('now')
                OR (appointment_date = date('now') AND appointment_time < strftime('%H:%M', 'now', 'localtime'))
              )
        """)

_mark_missed_appointments()


def _run_daily_notifications():
    """
    Background thread: runs once per day.
    Sends email alerts for:
      1. Patients who have missed 2+ consecutive expected session days.
      2. Patients with an appointment tomorrow.
    """
    import time as _time

    def _check():
        with app.app_context():
            try:
                # ── 1. Missed sessions (2+ consecutive missed days) ──────────────
                patients = query_db('''
                    SELECT u.id, u.name, u.email, p.adherence_rate
                    FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.role = 'patient'
                ''')
                for pat in (patients or []):
                    workouts = query_db(
                        "SELECT frequency FROM workouts WHERE patient_id = ? AND is_active = 1",
                        (pat['id'],)
                    )
                    if not workouts:
                        continue
                    # Find last 2 expected session days and check if any session was done
                    max_freq = max(_parse_frequency_per_week(w['frequency']) for w in workouts)
                    # If freq < 1/day, skip daily check — only flag if at least daily
                    if max_freq < 1:
                        continue
                    missed = query_db('''
                        SELECT COUNT(*) as cnt FROM sessions
                        WHERE patient_id = ? AND completed_at IS NOT NULL
                        AND completed_at >= date('now', '-2 days')
                    ''', (pat['id'],), one=True)
                    sessions_last_2d = int(missed['cnt']) if missed else 0
                    if sessions_last_2d == 0 and pat['email']:
                        _send_email(
                            to_address=pat['email'],
                            subject="Reminder: You've missed 2 rehab sessions",
                            body=(
                                f"Hi {pat['name']},\n\n"
                                "We noticed you haven't completed a rehab session in the last 2 days. "
                                "Staying consistent is key to your recovery!\n\n"
                                "Please log in and complete your session when you can.\n\n"
                                "— Your Rehab Coach Team"
                            )
                        )

                # ── 2. Appointment reminders (tomorrow) ──────────────────────────
                upcoming = query_db('''
                    SELECT a.id, a.appointment_date, a.appointment_time,
                           pu.name as patient_name, pu.email as patient_email,
                           du.name as doctor_name
                    FROM appointments a
                    JOIN users pu ON a.patient_id = pu.id
                    JOIN users du ON a.doctor_id = du.id
                    WHERE a.status = 'scheduled'
                    AND a.appointment_date = date('now', '+1 day')
                ''')
                for appt in (upcoming or []):
                    if appt['patient_email']:
                        _send_email(
                            to_address=appt['patient_email'],
                            subject="Reminder: Appointment tomorrow",
                            body=(
                                f"Hi {appt['patient_name']},\n\n"
                                f"This is a reminder that you have an appointment tomorrow "
                                f"({appt['appointment_date']}) at {appt['appointment_time']} "
                                f"with Dr. {appt['doctor_name']}.\n\n"
                                "Please log in to the platform or contact your clinic if you need to reschedule.\n\n"
                                "— Your Rehab Coach Team"
                            )
                        )

            except Exception as _e:
                print(f"[NOTIFY] Daily notification check failed: {_e}")

    def _loop():
        while True:
            _check()
            _time.sleep(86400)  # run every 24 hours

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print("[NOTIFY] Daily notification thread started")


_run_daily_notifications()


def _parse_frequency_per_week(freq_text: str) -> float:
    """Parse a workout frequency string into sessions per week."""
    if not freq_text:
        return 3.0
    f = freq_text.strip().lower()
    if 'daily' in f or f == '7x per week':
        return 7.0
    if 'twice' in f or '2x' in f:
        return 2.0
    if 'once' in f or '1x' in f:
        return 1.0
    # handles "3x per week", "4x per week", "5x per week", etc.
    import re as _re
    m = _re.search(r'(\d+)\s*x', f)
    if m:
        return float(m.group(1))
    return 3.0  # sensible default


def recalculate_adherence(patient_id: int):
    """
    Recalculate and persist adherence_rate for a patient.

    Formula (0–100):
      50% — Recent performance: average of (completion_perc/100 + quality_score/100) / 2
             across the last 3 completed sessions.
      50% — Overall history: average quality_score / 100 across all completed sessions.

    If fewer than 3 sessions exist the recent score uses whatever is available.
    If no sessions at all, adherence stays unchanged.
    """
    try:
        # ── Recent: last 3 sessions ──────────────────────────────────────────
        recent = query_db(
            """SELECT quality_score, completed_perc FROM sessions
               WHERE patient_id = ? AND completed_at IS NOT NULL
               ORDER BY completed_at DESC LIMIT 3""",
            (patient_id,)
        )
        if not recent:
            return  # no sessions yet — leave as-is

        recent_scores = []
        for r in recent:
            comp = min(float(r['completed_perc'] or 0), 100.0) / 100.0
            qual = min(float(r['quality_score'] or 0), 100.0) / 100.0
            recent_scores.append((comp + qual) / 2.0)
        recent_component = (sum(recent_scores) / len(recent_scores)) * 100.0

        # ── Overall history: all sessions ────────────────────────────────────
        overall = query_db(
            """SELECT AVG(quality_score) as avg_q FROM sessions
               WHERE patient_id = ? AND completed_at IS NOT NULL""",
            (patient_id,), one=True
        )
        overall_component = min(float(overall['avg_q'] or 0), 100.0) if overall else 0.0

        adherence = round(0.5 * recent_component + 0.5 * overall_component, 1)

        execute_db(
            "UPDATE patients SET adherence_rate = ? WHERE user_id = ?",
            (adherence, patient_id)
        )
    except Exception as _e:
        print(f"[WARN] recalculate_adherence failed for patient {patient_id}: {_e}")


def assign_patient_exercises(patient_user_id, condition):
    """
    Assign exercises to a patient based on their MSK condition.
    Inserts rows into patient_exercises for each mapped exercise.
    """
    exercise_names = CONDITION_EXERCISE_MAP.get(condition, [])
    if not exercise_names:
        # Fallback: assign all exercises
        exercise_names = [
            'Lifting of Arms', 'Lateral Trunk Tilt', 'Trunk Rotation',
            'Squat', 'Trunk Rotation & Target Touch', 'Pelvis Rotation',
            'Forward Flexion', 'Flank Stretch', 'Torso Rotation',
        ]

    for ex_name in exercise_names:
        ex_row = query_db('SELECT id FROM exercises WHERE name = ?', (ex_name,), one=True)
        if ex_row:
            execute_db(
                'INSERT OR IGNORE INTO patient_exercises (patient_id, exercise_id, enabled) VALUES (?, ?, 1)',
                (patient_user_id, ex_row['id'])
            )


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


# ==================== FRAME TELEMETRY HELPER ====================

def _log_frame_telemetry(out: dict, program: str = 'general'):
    """Insert one row into session_frames for every processed frame.
    
    Silently skips if no active session or user is not logged in.
    Skips warmup / idle / no-pose frames that carry no useful score data.
    """
    try:
        patient_id = session.get('user_id')
        session_id = session.get('current_session_id')
        if not patient_id or not session_id:
            return  # not inside a tracked session

        form_status = out.get('form_status', '') or ''
        # Skip frames with no real scoring data
        if form_status in ('WARMUP', 'NO_POSE', 'IDLE', 'ERROR', ''):
            return

        exercise_name = out.get('exercise_name', '') or ''
        # Prefer aggregated_score (stable, matches what user sees) over raw frame_score
        score = float(out.get('aggregated_score') or out.get('frame_score', 0.0) or 0.0)
        rep_info = out.get('rep_info') or {}
        rep_count = int(rep_info.get('rep_now', 0))
        set_count = int(rep_info.get('set_now', 1))
        asymmetry_pct = out.get('asymmetry_pct')   # may be None
        rom_angle     = out.get('joint_angle')       # may be None
        ts = datetime.utcnow().isoformat()

        execute_db(
            '''INSERT INTO session_frames
               (session_id, patient_id, timestamp, program, exercise_name,
                score, status, rep_count, set_count, asymmetry_pct, rom_angle)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, patient_id, ts, program, exercise_name,
             score, form_status, rep_count, set_count, asymmetry_pct, rom_angle),
        )
    except Exception as e:
        # Never let logging break the real-time pipeline
        print(f"[FRAME_LOG] Error: {e}")


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
    exercise_hint = data.get("exercise_hint", "")
    
    PIPELINE.language = language  # keep it simple
    
    try:
        out = PIPELINE.process_frame_dataurl(
            frame_b64,
            language=language,
            mode=mode,
            manual_exercise=manual_exercise,
            exercise_hint=exercise_hint
        )
        
        # Store landmarks for frontend polling
        global LATEST_LANDMARKS
        if 'landmarks' in out and out['landmarks']:
            LATEST_LANDMARKS['kimore'] = {
                'landmarks': out['landmarks'],
                'exercise_name': out.get('exercise_name', ''),
                'timestamp': time.time()
            }

        # ── Log frame telemetry to session_frames ──────────────────
        _log_frame_telemetry(out, program='general')
        
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


# ==================== KERAAL LOW BACK PAIN PIPELINE API ====================

@app.route("/api/live_feedback_keraal", methods=["POST"])
def api_live_feedback_keraal():
    """KERAAL-specific endpoint for low back pain rehabilitation"""
    if KERAAL_PIPELINE is None:
        return jsonify({"error": "KERAAL pipeline not available"}), 503

    data = request.get_json(force=True) or {}
    frame_b64 = data.get("frame_b64", "")
    if not frame_b64:
        return jsonify({"error": "frame_b64 missing"}), 400

    language = data.get("language", "English")
    exercise_hint = data.get("exercise_hint", "")
    
    try:
        out = KERAAL_PIPELINE.process_frame_dataurl_keraal(
            frame_b64,
            language=language,
            exercise_hint=exercise_hint
        )
        
        # Store landmarks for frontend polling
        global LATEST_LANDMARKS
        if 'landmarks' in out and out['landmarks']:
            LATEST_LANDMARKS['keraal'] = {
                'landmarks': out['landmarks'],
                'exercise_name': out.get('exercise_name', ''),
                'timestamp': time.time()
            }

        # ── Log frame telemetry to session_frames ──────────────────
        _log_frame_telemetry(out, program='low_back_pain')
        
        return jsonify(out)
    except Exception as e:
        print(f"❌ KERAAL API Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "frame_score": 0.0,
            "form_status": "ERROR",
            "llm_feedback": [f"KERAAL error: {str(e)}"],
            "exercise_name": "error",
            "exercise_confidence": 0.0,
            "pipeline": "keraal",
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


@app.route("/api/session/landmarks", methods=["GET"])
def get_session_landmarks():
    """
    Get latest landmarks for skeleton visualization.
    Called by frontend for real-time pose rendering (every 200ms).
    Returns 33 landmarks with [x, y, z] coordinates.
    """
    global LATEST_LANDMARKS
    
    # Try KIMORE first, then KERAAL
    landmarks_data = LATEST_LANDMARKS.get('kimore') or LATEST_LANDMARKS.get('keraal')
    
    if landmarks_data:
        return jsonify({
            "ok": True,
            "landmarks": landmarks_data['landmarks'],
            "exercise_name": landmarks_data['exercise_name'],
            "timestamp": landmarks_data['timestamp']
        })
    else:
        return jsonify({
            "ok": False,
            "landmarks": [],
            "exercise_name": "",
            "timestamp": 0
        }), 204  # No Content


@app.route("/api/session/start/keraal", methods=["POST"])
@login_required
@role_required('patient')
def api_session_start_keraal():
    """Start a KERAAL (low back pain) session"""
    if KERAAL_PIPELINE is None:
        return jsonify({"ok": False, "error": "KERAAL pipeline not available"}), 503
    
    data = request.get_json(force=True) or {}
    language = data.get("language", "English")
    target_reps = data.get("target_reps", 10)
    target_sets = data.get("target_sets", 3)
    
    try:
        KERAAL_PIPELINE.reset()
        KERAAL_PIPELINE.language = language
        KERAAL_PIPELINE.target_reps = target_reps
        KERAAL_PIPELINE.target_sets = target_sets
        KERAAL_PIPELINE.current_rep_count = 0
        KERAAL_PIPELINE.current_set_count = 1
        print(f"🎯 KERAAL session started with target_reps={target_reps}, target_sets={target_sets}")
        return jsonify({
            "ok": True,
            "pipeline": "keraal",
            "message": "KERAAL session started"
        })
    except Exception as e:
        print(f"❌ KERAAL Session Start Error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/api/session/stop/keraal", methods=["POST"])
@login_required
@role_required('patient')
def api_session_stop_keraal():
    """Stop a KERAAL session"""
    if KERAAL_PIPELINE is None:
        return jsonify({"ok": True, "warning": "KERAAL pipeline not available"})
    
    try:
        KERAAL_PIPELINE.reset()
        return jsonify({"ok": True, "pipeline": "keraal"})
    except Exception as e:
        print(f"❌ KERAAL Session Stop Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


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
    port = int(os.environ.get("PORT", "5050"))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
