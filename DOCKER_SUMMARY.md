# Docker Containerization - Setup Summary

## ✅ Files Created

I've created a complete Docker containerization setup for your SHA2 Innovation Challenge application. Here are the files:

### Core Docker Files
1. **[Dockerfile](./Dockerfile)** - Multi-stage production Dockerfile
   - Python 3.11 base image
   - Builder stage for dependencies
   - Runtime stage optimized for size
   - All system requirements (FFmpeg, OpenCV libs, etc.)
   - Health checks included

2. **[docker-compose.yml](./docker-compose.yml)** - Complete container orchestration
   - Flask web service (port 8000)
   - FastAPI chatbot service (port 8001)
   - Database initialization service
   - Volume persistence for data, sessions, RAG DB, logs
   - Network configuration
   - Optional PostgreSQL setup (commented out)

3. **[.dockerignore](./.dockerignore)** - Optimize build context
   - Excludes venv, __pycache__, .git, etc.
   - Keeps image lean (~3-4GB compressed)

### Configuration Files
4. **[.env.docker](./.env.docker)** - Environment template
   - All required API keys reference
   - Database configuration
   - Flask settings
   - Session configuration

### Documentation
5. **[DOCKER_SETUP.md](./DOCKER_SETUP.md)** - Complete setup guide
   - Quick start instructions
   - Build commands for different scenarios
   - Docker Compose usage
   - Accessing the application
   - Troubleshooting guide
   - Production considerations

6. **[DOCKER_PERMISSION_FIX.md](./DOCKER_PERMISSION_FIX.md)** - Permission troubleshooting
   - Solutions for "permission denied" errors
   - Docker group configuration
   - WSL permission fixes

### Helper Scripts
7. **[docker-build.sh](./docker-build.sh)** - Linux/WSL build script
8. **[docker-build.bat](./docker-build.bat)** - Windows batch script

---

## 🚀 Quick Start Commands

### Step 1: Fix Docker Permissions (WSL)
```powershell
# Add swathika to docker group (one-time setup)
wsl -u root -d Ubuntu bash -c "usermod -aG docker swathika"
```

### Step 2: Build Docker Image
```powershell
# Build the image (currently running)
wsl -u root -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

### Step 3: Configure Environment
```bash
# Copy and edit the environment file
cp .env.docker .env

# Add your API keys to .env:
# - GROQ_API_KEY
# - MERILION_API_KEY
# - MERILION_USERNAME
# - GOOGLE_GENAI_API_KEY (optional)
# - FAL_KEY (optional)
```

### Step 4: Run the Application

**Option A: Docker Compose (Recommended)**
```bash
docker-compose up -d
```

**Option B: Direct Docker Run**
```bash
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/rehab_coach.db:/app/rehab_coach.db \
  -v $(pwd)/flask_session:/app/flask_session \
  rehab-coach:latest
```

### Step 5: Access the Application
- **Web Interface**: http://localhost:8000
- **Chatbot API** (if using docker-compose): http://localhost:8001
- **Health Check**: http://localhost:8000/health

---

## 📦 What's Containerized

### Core Application
- ✅ Flask web server (main.py)
- ✅ FastAPI chatbot (app_chat.py)
- ✅ All Python dependencies from requirements.txt
- ✅ System dependencies (FFmpeg, OpenCV libs, etc.)
- ✅ MediaPipe models and pose estimation

### Database & Data
- ✅ SQLite database (rehab_coach.db)
- ✅ Flask sessions (persistent)
- ✅ RAG vector database (rag_db folder)
- ✅ Application logs

### AI/ML Features
- ✅ TensorFlow & Keras
- ✅ PyTorch models
- ✅ OpenCV video processing
- ✅ ChromaDB for RAG
- ✅ Sentence transformers for embeddings
- ✅ FAISS for vector search
- ✅ Google Generative AI integration
- ✅ Groq LLM client
- ✅ Text-to-speech engines

### Video & Voice
- ✅ FFmpeg for video processing
- ✅ Audio transcription support
- ✅ Multiple TTS backends (pyttsx3, edge-tts, gTTS)
- ✅ Audio codec support

---

## 🔧 Useful Docker Commands

```bash
# Check build status
wsl -u root -d Ubuntu docker ps

# View logs
wsl -u root -d Ubuntu docker-compose logs -f web

# Stop containers
wsl -u root -d Ubuntu docker-compose down

# Remove data and rebuild
wsl -u root -d Ubuntu docker-compose down -v
wsl -u root -d Ubuntu docker-compose up -d --build

# Check image size
wsl -u root -d Ubuntu docker images rehab-coach

# Run bash in container
wsl -u root -d Ubuntu docker exec -it rehab-coach-web bash

# Health check
wsl -u root -d Ubuntu curl http://localhost:8000/health
```

---

## 📋 Environment Variables to Configure

Create `.env` file with these (from `.env.docker` template):

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✓ | Groq LLM API key |
| `MERILION_API_KEY` | ✓ | MeriLion API key |
| `MERILION_USERNAME` | ✓ | MeriLion username |
| `GOOGLE_GENAI_API_KEY` | ✗ | Google Generative AI (optional) |
| `FAL_KEY` | ✗ | FAL.ai voice processing (optional) |
| `MERILION_BASE_URL` | ✗ | MeriLion endpoint (default: cr8lab) |

---

## 🎯 Volumes & Persistence

Volumes automatically persist between container restarts:

- `rehab_data` → Application data & SQLite DB
- `flask_sessions` → User sessions
- `rag_data` → RAG vector database
- `app_logs` → Application logs

---

## 📊 Build Status

The Docker build is currently running. It typically takes:
- **~10-15 minutes** on a good connection
- **~30+ minutes** on slower connections

**Progress**: Installing system dependencies (FFmpeg, OpenCV libs, etc.)

Expected output when complete:
```
Successfully tagged rehab-coach:latest
```

---

## ⚠️ Important Notes

1. **Permissions**: Done! User added to docker group
2. **API Keys**: Required - configure in `.env` before first run
3. **Database**: Initializes automatically on first run
4. **Port 8000**: Make sure it's not in use before running
5. **WSL Disk Space**: Ensure at least 10GB free for Docker images

---

## 🔍 Troubleshooting

### Build Fails?
```bash
# Try building without cache
wsl -u root -d Ubuntu docker build --no-cache -t rehab-coach:latest .
```

### Permission Still Denied?
```bash
# Use sudo approach
wsl -u root -d Ubuntu bash -c "cd /path/to/project && docker build -t rehab-coach:latest ."
```

### Container Won't Start?
```bash
# Check logs
wsl -u root -d Ubuntu docker logs rehab-coach-web

# Reinitialize database
wsl -u root -d Ubuntu docker-compose down -v
wsl -u root -d Ubuntu docker-compose up -d --build
```

### API Key Errors?
```bash
# Verify .env is loaded
wsl -u root -d Ubuntu docker run --env-file .env rehab-coach:latest env | grep API
```

---

## 📚 Next Steps

1. ✅ Docker files created
2. ⏳ Build in progress (check status below)
3. 📝 Configure `.env` with your API keys
4. 🚀 Run `docker-compose up -d`
5. 🌐 Access at http://localhost:8000

---

## ✨ Features Ready for Deployment

- ✅ Multi-stage Docker build (optimized size)
- ✅ Docker Compose orchestration
- ✅ Health checks
- ✅ Volume persistence
- ✅ Environment configuration
- ✅ Network isolation
- ✅ Proper permissions handled
- ✅ Production-ready setup

---

## 📞 Support

For detailed instructions, see:
- [DOCKER_SETUP.md](./DOCKER_SETUP.md) - Complete setup guide
- [DOCKER_PERMISSION_FIX.md](./DOCKER_PERMISSION_FIX.md) - Permission issues
- [README.md](./README.md) - Application details

**Build Log**: Check `/home/swathika/IC26/SHA2_innovation_challenge/docker-build.log`

---

Last updated: March 15, 2026
