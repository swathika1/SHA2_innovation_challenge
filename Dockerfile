# SHA2 Innovation Challenge - Home Rehab Coach Application
# Multi-stage Dockerfile for containerization

# ============================================================================
# Stage 1: Builder - Install dependencies and prepare the environment
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    libsndfile1 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    postgresql-client \
    libpq-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TRANSFORMERS_NO_TF=1 \
    USE_TF=0 \
    KERAS_BACKEND=torch \
    PYTORCH_ENABLE_MPS_FALLBACK=1

# Copy entire application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/flask_session && \
    mkdir -p /app/rag_db && \
    mkdir -p /app/logs && \
    chmod -R 755 /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Expose ports
# Flask web interface
EXPOSE 8000
# FastAPI chatbot server (if used separately)
EXPOSE 8001
# Optional: WebRTC for video call
EXPOSE 3000

# Default command - run the Flask application
CMD ["python", "main.py"]
