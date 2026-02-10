# Rehab Score Coach (Pose → DL Score → Vision LLM Advice → TTS)

## What it does
- Captures webcam video
- Every 2 seconds extracts a frame
- Runs pose estimation → 100-dim feature vector
- Builds a rolling sequence → resamples to 100 timesteps
- Predicts rehab quality score (clamped 0–50)
- If score drops below threshold (with smoothing + hysteresis + cooldown):
  - send frame to Vision LLM for coaching text
  - read coaching out loud using TTS
- Returns overall session score as JSON:
  {"Overall Session Score": X.XX}

## Setup
```bash
pip install -r requirements.txt
python scripts/download_assets.py
