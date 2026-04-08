# SHA2 Innovation Challenge - IC 2026

## Multimodal Home Rehab Form Coach (MSK / Post-op Rehab)

**Target Users:** Outpatient / post-op / musculoskeletal (MSK) patients needing rehabilitation.

**Key Features:**
- Detects exercises → counts reps/sets, checks form quality, flags mistakes
- Real-time guidance: "knees tracking inward", "slow down", "stand taller"
- Generates clinician-ready summary: adherence %, quality trend, top errors, "needs intervention" flags
- Personalized feedback based on baseline range-of-motion and progressive targets
- Multi-lingual cues: SEA-LION can give audio/text instructions in different languages

### Multimodal Inputs
- **Video:** Pose/joint angles (primary) using MediaPipe / MoveNet
- **Audio:** Optional effort/pain check
- **Patient-reported:** Pain/perceived exertion
- **Optional Wearables:** Smoothness, stability

### MVP
- On-device pose extraction
- Rule-based checks for exercise form
- PDF summary generation

### Advanced Features
- Small temporal ML models (1D-CNN / LSTM) to predict quality score
- Personalized feedback and progression tracking

---

## Setup

> **Python 3.11 is required.** MediaPipe and TensorFlow are not compatible with Python 3.12 or later. Verify your version with `python3 --version` before proceeding.

### 1. Clone the Repository
```bash
git clone https://github.com/swathika1/SHA2_innovation_challenge.git
cd SHA2_innovation_challenge
```

### 2. Create a virtual environment

Linux / Mac:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell):
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Then open `.env` and set the following variables:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key — get from [console.groq.com](https://console.groq.com) |
| `MERILION_API_KEY` | Yes | MERaLiON API key from cr8lab |
| `MERILION_USERNAME` | Yes | MERaLiON account username |
| `MERILION_BASE_URL` | Yes | Default: `https://api.cr8lab.com` |
| `GROQ_MODEL` | Yes | Default: `llama-3.1-8b-instant` |
| `FLASK_SECRET_KEY` | Yes | Any long random string — used to sign session cookies |
| `NOTIFY_EMAIL_SENDER` | No | Gmail address for session alert emails |
| `NOTIFY_EMAIL_PASSWORD` | No | Gmail app password (not your account password) |

> Without `GROQ_API_KEY` and `MERILION_API_KEY` the app will start but AI feedback and the Jimmy chatbot will not function.

### 5. Download ML model files

Download the full model files from Google Drive and place them inside `Rehab_Scorer_Coach/models/`:

**[Download models (Google Drive)](https://drive.google.com/drive/folders/1tNtTbmkIOcD_DPkIV7chTlQfDga6GPsX?usp=sharing)**

| File | Purpose |
|---|---|
| `poseformer_transformer_model.keras` | Pose quality regression model |
| `scoring_model.keras` | Frame-level score scaler model |
| `mobilenet_exercise_model.keras` | Exercise classification model |
| `x_scaler.pkl` | Input feature scaler |
| `y_map.pkl` | Output label map |
| `scoring_scaler.pkl` | Score normalisation scaler |
| `exercise_scaler.pkl` | Exercise feature scaler |
| `exercise_label_map.json` | Exercise class index map |

### 6. Initialise the database (first run only)

```bash
python init_database.py
```

This creates `rehab_coach.db` with all required tables and default seed data. Skip if `rehab_coach.db` already exists.

### 7. Build the RAG knowledge base (first run only)

```bash
python knowledge_loader.py --all
```

This ingests KIMORE exercise guides, PDF documents, and the exercise library into the local FAISS vector store used by the AI feedback pipeline. Skip if the `rag_db/` directory already exists and is populated.

### 8. Run the app

Linux / Mac:
```bash
python3 main.py
```

Windows:
```bash
python main.py
```

App runs on: `http://localhost:5050`

---

## Architecture

Two parallel rehab pipelines run depending on the exercise type:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  VIDEO CAPTURE → Base64 Encode → POST /api/live_feedback                 │
└──────────────────────────────────────────────────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
  ┌─────────────────────────┐   ┌─────────────────────────┐
  │  WebRehabPipeline       │   │  KeraalRehabPipeline     │
  │  (KIMORE - 8 exercises) │   │  (Low back pain - 3 ex.) │
  │                         │   │                          │
  │  MediaPipe (33 pts)     │   │  MediaPipe (33 pts)      │
  │  → 50D feature vector   │   │  → Pose buffer (48 frames)│
  │  → Exercise classifier  │   │  → Exercise classifier   │
  │  → Score model (0-50)   │   │  → Correctness model     │
  │  → RepCounter (angles)  │   │  → RepCounter (angles)   │
  └─────────────────────────┘   └─────────────────────────┘
               │                             │
               └──────────────┬──────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  API Response                 │
              │  {                            │
              │    frame_score: 34.5,         │
              │    form_status: "CORRECT",    │
              │    exercise_name: "squat",    │
              │    rep_info: {                │
              │      rep_now: 5,              │
              │      rep_target: 10,          │
              │      set_now: 1,              │
              │      set_target: 3,           │
              │      rep_incremented: true,   │
              │      set_completed: false,    │
              │      exercise_completed: false│
              │    },                         │
              │    landmarks: [[x,y,z]×33],   │
              │    llm_feedback: [...]        │
              │  }                            │
              └───────────────────────────────┘
```

### Rep Detection
Rules-based using MediaPipe joint angles:
- Squat: knee angle < 90° (down) → > 160° (up)
- Arm Lifting: shoulder-wrist distance high → low
- Lateral Tilt: side asymmetry > 15%
- ...and more per exercise

### Skeleton Visualization
Frontend polls `GET /api/session/landmarks` every 200ms independently of the main feedback loop. Returns the latest 33 landmark points for real-time skeleton overlay on canvas.

### Gamification
Badge unlocks tracked client-side based on total reps:
- First Step (≥1 rep)
- One Set (≥10 reps)
- Pair Power (≥20 reps)
- Champion (≥30 reps)

---

## Session Flow

```
Patient Login → Dashboard → Start Session → Enable Camera
     → Exercise Loop (100ms poll) → Stop Session
     → Completion Modal (pain/effort check-in)
     → Save → Metrics Auto-updated → Dashboard
```

After each save, `update_patient_metrics()` recalculates:
- `adherence_rate` = (actual_sessions / expected_sessions) × 100
- `avg_quality_score` = average over last 30 days
- `avg_pain_level` = average `pain_after` over last 30 days
- `streak_days` = consecutive days with sessions

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/session/start` | POST | Initialize session state |
| `/api/live_feedback` | POST | Process video frame, returns score + rep_info + landmarks |
| `/api/session/landmarks` | GET | Latest landmarks for skeleton rendering |
| `/api/session/save` | POST | Save completed session to DB |

### Example: Save a session
```bash
curl -X POST http://localhost:5050/api/session/save \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "workout_id": 1,
    "pain_before": 3,
    "pain_after": 2,
    "effort_level": 7,
    "quality_score": 42.5,
    "sets_completed": 3,
    "reps_completed": 30,
    "notes": "Test session"
  }'
```

---

## Database

DB design:

<img width="1536" height="1024" alt="ChatGPT Image Feb 9, 2026, 12_39_58 PM" src="https://github.com/user-attachments/assets/73b76900-89af-4d27-b2ad-d920980889d3" />

### Tables (8)

| Table | Description |
|---|---|
| `users` | Central authentication & user info |
| `patients` | Extended patient medical data |
| `doctor_patient` | Doctor–patient assignments |
| `caregiver_patient` | Caregiver monitoring relationships |
| `exercises` | Exercise library |
| `workouts` | Patient exercise prescriptions |
| `sessions` | Completed rehabilitation sessions |
| `appointments` | Scheduled consultations |

### Key schemas

**sessions** — one row per completed exercise session:

| Column | Type | Notes |
|---|---|---|
| `patient_id` | INTEGER | → users.id |
| `workout_id` | INTEGER | → workouts.id |
| `pain_before` / `pain_after` | INTEGER | 0–10 |
| `effort_level` | INTEGER | 1–10 |
| `quality_score` | REAL | 0–50, avg of all frame scores |
| `sets_completed` / `reps_completed` | INTEGER | |
| `completed_at` | TIMESTAMP | |

**patients** — aggregate metrics, auto-updated after each session:

| Column | Type | Notes |
|---|---|---|
| `adherence_rate` | REAL | % of expected sessions completed |
| `streak_days` | INTEGER | consecutive days with sessions |
| `avg_quality_score` | REAL | last 30 days |
| `avg_pain_level` | REAL | last 30 days |

### Useful queries
```bash
sqlite3 rehab_coach.db

# Recent sessions
SELECT id, patient_id, quality_score, pain_after, sets_completed, reps_completed,
       datetime(completed_at, 'localtime') as completed
FROM sessions ORDER BY completed_at DESC LIMIT 10;

# Patient metrics
SELECT p.user_id, u.name, p.adherence_rate, p.streak_days,
       p.avg_quality_score, p.avg_pain_level
FROM patients p JOIN users u ON p.user_id = u.id;
```

---

## Troubleshooting

**Session not saving?**
1. Check browser console (F12) for JS errors
2. Check Flask terminal for server errors
3. Verify logged in as a patient
4. Verify `workoutId` is not null in `session.html`

**Metrics not updating?**
1. `SELECT * FROM sessions ORDER BY completed_at DESC LIMIT 1;`
2. `SELECT * FROM patients WHERE user_id = YOUR_ID;`
3. Verify `update_patient_metrics()` is being called in server logs

**"Workout not found" error?**
- Check: `SELECT * FROM workouts WHERE patient_id = YOUR_ID AND is_active = 1;`
- If none, ask a doctor to create one via the clinician dashboard
