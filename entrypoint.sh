#!/bin/bash
set -e

echo "[INIT] Starting SHA2 Rehab Coach application..."
echo "[INIT] Container home: /app"
echo "[INIT] Python version:"
python --version

# Ensure instance directory exists
mkdir -p /app/instance

# Try to initialize database if it doesn't exist
echo "[DB] Checking database..."
if [ ! -f /app/rehab_coach.db ]; then
    echo "[DB] Database not found. Initializing..."
    cd /app
    python -c "from database import ensure_tables_exist; ensure_tables_exist()" || echo "[DB] Warning: Could not initialize database"
else
    echo "[DB] Database found at /app/rehab_coach.db"
fi

# Verify environment variables
echo "[ENV] Checking critical environment variables..."
if [ -z "$GROQ_API_KEY" ]; then
    echo "[ENV] WARNING: GROQ_API_KEY not set"
fi
if [ -z "$MERILION_API_KEY" ]; then
    echo "[ENV] WARNING: MERILION_API_KEY not set"
fi

# Set port (default 5050)
PORT=${PORT:-5050}
echo "[CONFIG] Running on port $PORT"

# Start Gunicorn with Flask app
echo "[START] Launching Flask app with Gunicorn..."
cd /app
exec gunicorn \
    --bind 0.0.0.0:${PORT} \
    --timeout 300 \
    --workers 2 \
    --worker-class sync \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    main:app
