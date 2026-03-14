# Docker Setup Guide - SHA2 Innovation Challenge (Home Rehab Coach)

## Overview
This guide explains how to containerize and run the SHA2 Innovation Challenge application using Docker.

## Prerequisites
- Docker installed and running
- Docker Compose (usually included with Docker Desktop)
- WSL 2 (Windows Subsystem for Linux) if on Windows
- API keys for:
  - Groq API
  - Google Generative AI (optional)
  - MeriLion API
  - FAL.ai (optional)

## Quick Start

### 1. Prepare Environment File
```bash
# Copy the template environment file
cp .env.docker .env

# Edit .env with your actual API keys
nano .env  # or use your favorite editor
```

**Required environment variables to populate:**
- `GROQ_API_KEY` - For LLM inference
- `MERILION_API_KEY` - For healthcare integration
- `MERILION_USERNAME` - Your MeriLion username

### 2. Build the Docker Image
```bash
# Build the image with a tag
docker build -t rehab-coach:latest .

# For more verbose output
docker build --progress=plain -t rehab-coach:latest .
```

**Or use the WSL command directly:**
```powershell
# From Windows PowerShell
wsl -d Ubuntu -u swathika cd ~/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest .
```

### 3. Run with Docker Compose (Recommended)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

### 4. Run with Docker Directly (Single Container)
```bash
# Basic run
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/rehab_coach.db:/app/rehab_coach.db \
  -v $(pwd)/flask_session:/app/flask_session \
  -v $(pwd)/rag_db:/app/rag_db \
  --name rehab-coach \
  rehab-coach:latest

# On Windows PowerShell
docker run -p 8000:8000 `
  --env-file .env `
  -v ${PWD}/rehab_coach.db:/app/rehab_coach.db `
  -v ${PWD}/flask_session:/app/flask_session `
  -v ${PWD}/rag_db:/app/rag_db `
  --name rehab-coach `
  rehab-coach:latest
```

## Docker Compose Services

### 1. **Web Service**
   - Main Flask application
   - Port: 8000
   - Database: SQLite (persisted)
   - Session storage: Filesystem (persisted)

### 2. **Chatbot Service** (Optional)
   - FastAPI server for async chat operations
   - Port: 8001
   - Can be disabled by commenting out in docker-compose.yml

### 3. **Database Initialization** (runs once)
   - Initializes the SQLite database
   - Runs before the web service starts

## Volumes and Persistence

The following data is persisted across container restarts:
- `rehab_data` - Application data and SQLite database
- `flask_sessions` - User session information
- `rag_data` - RAG/vector database
- `app_logs` - Application logs

## Building and Tagging

### Build with specific tag
```bash
docker build -t rehab-coach:1.0 .
docker build -t rehab-coach:latest .
```

### Build without cache (fresh install)
```bash
docker build --no-cache -t rehab-coach:latest .
```

### View built images
```bash
docker images | grep rehab-coach
```

## Accessing the Application

After starting the container:
- **Web Interface**: http://localhost:8000
- **Chatbot API** (if using docker-compose): http://localhost:8001
- **Health Check**: http://localhost:8000/health

## Managing Containers

### View running containers
```bash
docker ps
docker-compose ps
```

### View logs
```bash
# Follow logs in real-time
docker logs -f rehab-coach

# Last 100 lines
docker logs --tail 100 rehab-coach

# With docker-compose
docker-compose logs -f web
```

### Stop and remove containers
```bash
# Stop
docker stop rehab-coach
docker-compose down

# Stop and remove all data
docker-compose down -v
```

### Rebuild after code changes
```bash
docker-compose down
docker-compose up -d --build
```

## Troubleshooting

### Image build fails
```bash
# Try building without cache
docker build --no-cache -t rehab-coach:latest .

# Check for syntax errors
docker build --progress=plain -t rehab-coach:latest .
```

### Container runs but app crashes
```bash
# Check logs
docker logs rehab-coach

# Run with interactive terminal
docker run -it rehab-coach:latest /bin/bash
```

### Database issues
```bash
# Reinitialize database
docker-compose down -v
docker-compose up -d --build
```

### Permission errors
```bash
# Give proper permissions in running container
docker exec rehab-coach chmod -R 755 /app
```

### API key errors
```bash
# Verify .env file is loaded
docker run --env-file .env rehab-coach:latest env | grep -i api

# Check if keys are set
docker exec rehab-coach python -c "import os; print(os.environ.get('GROQ_API_KEY', 'NOT SET'))"
```

## Environment Variables Reference

### Required
| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | API key for Groq LLM service |
| `MERILION_API_KEY` | MeriLion API authentication key |
| `MERILION_USERNAME` | MeriLion API username |

### Optional
| Variable | Description |
|----------|-------------|
| `GOOGLE_GENAI_API_KEY` | Google Generative AI key |
| `FAL_KEY` | FAL.ai service key |
| `MERILION_BASE_URL` | MeriLion API endpoint (default: https://api.cr8lab.com) |

## Performance Optimization

### Multi-stage build
The Dockerfile uses a multi-stage build to keep the final image size small:
- **Builder stage**: Compiles all dependencies
- **Runtime stage**: Contains only necessary components

### Clean builds
```bash
# Remove unused images and containers
docker system prune -a

# Remove unused volumes
docker volume prune
```

## Production Considerations

1. **Use environment secrets**: Don't commit `.env` files with real keys to version control
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use stronger secrets**: Generate proper SECRET_KEY for Flask
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Health checks**: The Dockerfile includes health checks
   ```bash
   docker inspect --format='{{.State.Health.Status}}' rehab-coach
   ```

4. **Resource limits**: Limit container resources
   ```bash
   docker run -m 4g --cpus=2 rehab-coach:latest
   ```

5. **Logging**: Check container logs regularly
   ```bash
   docker logs --tail 100 -f rehab-coach
   ```

## Example: Full WSL Workflow

```powershell
# 1. Open PowerShell
# 2. Navigate to project (if needed)
cd "\\wsl.localhost\Ubuntu\home\swathika\IC26\SHA2_innovation_challenge"

# 3. Copy environment file and configure
wsl cp .env.docker .env

# 4. Edit .env with keys
wsl nano .env

# 5. Build image
wsl docker build -t rehab-coach:latest .

# 6. Run with docker-compose
wsl docker-compose up -d

# 7. Check status
wsl docker-compose ps

# 8. View logs
wsl docker-compose logs -f web
```

## Extending the Setup

### Add Redis for caching
```yaml
# In docker-compose.yml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - rehab-network
```

### Add PostgreSQL database
Uncomment the `postgres` service in `docker-compose.yml` and update environment variables.

### Add Nginx reverse proxy
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - web
```

## Support and Issues

For issues with:
- **Docker/Docker Compose**: Check [Docker documentation](https://docs.docker.com/)
- **Application**: Check application logs: `docker logs rehab-coach`
- **Dependencies**: Review `requirements.txt` and compatibility notes in README.md

## Next Steps

1. Populate `.env` with your API keys
2. Build the image: `docker build -t rehab-coach:latest .`
3. Run with docker-compose: `docker-compose up -d`
4. Access the application at `http://localhost:8000`
5. Check logs for any initialization messages
