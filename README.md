# SHA2 Innovation Challenge - IC 2026

## Multimodal Home Rehab Form Coach (MSK / Post-op Rehab)

### Short Description / Features
**Target Users:** Outpatient / post-op / musculoskeletal (MSK) patients needing rehabilitation.  

**Key Features:**
- Detects exercises → counts reps/sets, checks form quality, flags mistakes
- Real-time guidance: “knees tracking inward”, “slow down”, “stand taller”
- Generates clinician-ready summary: adherence %, quality trend, top errors, “needs intervention” flags
- Personalized feedback based on baseline range-of-motion and progressive targets
- Multi-lingual cues: SEA-LION can give audio/text instructions in different languages

### Multimodal Inputs
- **Video:** Pose/joint angles (primary) using MediaPipe / MoveNet
- **Audio:** Optional effort/pain check
- **Patient-reported:** Pain/perceived exertion
- **Optional Wearables:** Smoothness, stability

### MVP (Minimum Viable Product)
- On-device pose extraction
- Rule-based checks for exercise form
- PDF summary generation

### Advanced Features
- Small temporal ML models (1D-CNN / LSTM) to predict quality score
- Personalized feedback and progression tracking

---

## Running the Flask App Locally

### 1. Clone the Repository
```bash
git clone https://github.com/swathika1/SHA2_innovation_challenge.git
cd SHA2_innovation_challenge
```

### 2. Create a virtual environment
Linux / Mac
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell)
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the app
Linux / Mac
```bash
python3 main.py
```

Windows
```bash
python main.py
```

Than run it on localhost!

---

## ✅ NEW: Session Logging & Dynamic Dashboard (Feb 2026)

### Features Implemented:
- 📊 **Session Data Logging**: Exercise sessions automatically saved to database
- 📈 **Dynamic Metrics**: Dashboard powered by real-time database calculations
- 🎯 **Automatic Updates**: Adherence, quality scores, pain levels, and streaks auto-calculated
- 💾 **Complete History**: All session data stored with timestamps for analysis

### Quick Test:
```bash
# 1. Run the test suite
python3 test_session_logging.py

# 2. Start app (already running)
python3 main.py

# 3. Login as patient → Start session → Complete → See metrics update!
```

### Documentation:
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Complete overview
- **[Quick Start Guide](QUICK_START_GUIDE.md)** - How to use the features
- **[Visual Flow Diagram](VISUAL_FLOW_DIAGRAM.md)** - Step-by-step visual guide
- **[Technical Details](SESSION_LOGGING_IMPLEMENTATION.md)** - Full technical documentation

---

DB design:

<img width="1536" height="1024" alt="ChatGPT Image Feb 9, 2026, 12_39_58 PM" src="https://github.com/user-attachments/assets/73b76900-89af-4d27-b2ad-d920980889d3" />



## Database Tables (8)


| Table Name           | Description                                   |
|----------------------|-----------------------------------------------|
| `users`              | Central authentication & user info           |
| `patients`           | Extended patient medical data                 |
| `doctor_patient`     | Doctor–patient assignments                    |
| `caregiver_patient`  | Caregiver monitoring relationships            |
| `exercises`          | Exercise library                              |
| `workouts`           | Patient exercise prescriptions                |
| `sessions`           | Completed rehabilitation sessions             |
| `appointments`       | Scheduled consultations                        |
