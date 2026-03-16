# Use stable Python 3.11 slim image for smaller footprint
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install required system dependencies for OpenCV, ffmpeg, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt /app/

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy entire project directory (preserves all files including database)
COPY . /app/

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose Flask application port
EXPOSE 5050

# Set environment variables for ML libraries (compatible with PyTorch backend)
ENV TRANSFORMERS_NO_TF=1 \
    USE_TF=0 \
    KERAS_BACKEND=torch \
    PYTORCH_ENABLE_MPS_FALLBACK=1 \
    PORT=5050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5050/health', timeout=5)" || exit 1

# Run Flask application with Gunicorn via entrypoint
CMD ["/app/entrypoint.sh"]
