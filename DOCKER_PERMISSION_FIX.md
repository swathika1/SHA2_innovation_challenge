# Docker Permission Setup - WSL Ubuntu

## Problem
```
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

## Solution

The user `swathika` needs permission to access the Docker daemon. There are three approaches:

### Option 1: Add User to Docker Group (RECOMMENDED)

This is the safest and most convenient approach. Run this once in WSL:

```bash
# 1. Open WSL terminal as root (or use sudo)
wsl -u root -d Ubuntu

# 2. Add swathika to docker group
sudo usermod -aG docker swathika

# 3. Create docker group if it doesn't exist (usually it does)
sudo groupadd docker 2>/dev/null || true

# 4. Apply new group permissions (run this in WSL as swathika)
newgrp docker

# 5. Exit root
exit
```

### Option 2: Run Build with Sudo (If Option 1 doesn't work)

```bash
wsl -u root -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

### Option 3: Reset Docker Daemon in WSL

If Docker still doesn't work, try restarting the Docker daemon:

```bash
# In WSL
wsl -u root -d Ubuntu service docker restart

# Then try build again
wsl -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

## Step-by-Step Fix (Copy-Paste Ready)

### For Option 1 (Docker Group - BEST):

```powershell
# Run in Windows PowerShell
wsl -u root -d Ubuntu bash -c "usermod -aG docker swathika && echo 'Docker group added successfully'"

# Verify in WSL
wsl -d Ubuntu docker --version

# Then build
wsl -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

### For Option 2 (Sudo Approach):

```powershell
# Run in Windows PowerShell
wsl -u root -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

## Verify Docker Access

After fixing permissions, verify:

```bash
# In WSL Ubuntu
docker ps
docker images
docker version
```

If these commands work without `sudo` and without permission errors, you're ready to build!

## Complete Build Command

Once permissions are fixed, run:

```bash
# In WSL terminal
cd /home/swathika/IC26/SHA2_innovation_challenge
docker build -t rehab-coach:latest .

# Or directly from PowerShell
wsl -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

## Monitor Build Progress

The build will:
1. Pull Python 3.11-slim base image (~150MB)
2. Install system dependencies
3. Install Python requirements from requirements.txt
4. Create the multi-stage build

This typically takes **5-15 minutes** depending on your internet connection.

## Expected Output

```
Step 1/19 : FROM python:3.11-slim as builder
Step 2/19 : WORKDIR /build
Step 3/19 : RUN apt-get update && apt-get install -y...
...
Step 19/19 : CMD ["python", "main.py"]
Successfully tagged rehab-coach:latest
```

## Next Steps After Build

Once the image is built:

```bash
# Test the image
docker run --rm rehab-coach:latest docker --version

# Run with docker-compose (needs .env file)
docker-compose up -d

# Or run single container
docker run -p 8000:8000 --env-file .env rehab-coach:latest
```

## Troubleshooting

### Still getting permission errors?
```bash
# Check docker group membership
id swathika

# If docker group not listed, logout and login to WSL
# In WSL, logout and reconnect
exit
# Then reconnect WSL and try again
```

### Docker daemon not running?
```bash
# Check status
wsl -u root -d Ubuntu service docker status

# Start docker
wsl -u root -d Ubuntu service docker start

# Check if running
wsl -u root -d Ubuntu docker ps
```

### Build space issues?
```bash
# Check disk space
docker system df

# Clean up if needed
docker system prune -a
```

## Reference: Full WSL Command to Build

```powershell
# Windows PowerShell - AFTER FIXING PERMISSIONS
wsl -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```

## Reference: Full WSL Command with Sudo (if needed)

```powershell
# Windows PowerShell - Alternative using sudo
wsl -u root -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && docker build -t rehab-coach:latest ."
```
