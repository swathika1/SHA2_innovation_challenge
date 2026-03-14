#!/bin/bash
# Docker build and deployment script for SHA2 Innovation Challenge
# Run this script inside WSL Ubuntu with: bash docker-build.sh

set -e  # Exit on any error

PROJECT_DIR="/home/swathika/IC26/SHA2_innovation_challenge"
IMAGE_NAME="rehab-coach"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

echo "=========================================="
echo "SHA2 Innovation Challenge - Docker Build"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

echo "✓ Docker is installed"
echo ""

# Check Docker daemon
if ! docker ps -q &> /dev/null; then
    echo "⚠️  Docker daemon may not be running. Starting Docker..."
    sudo service docker start || true
fi

# Navigate to project directory
cd "$PROJECT_DIR"
echo "📁 Working in: $(pwd)"
echo ""

# Step 1: Build the image
echo "🔨 Building Docker image: $FULL_IMAGE_NAME"
echo "==========================================="

if sudo docker build -t "$FULL_IMAGE_NAME" .; then
    echo ""
    echo "✅ Image built successfully!"
    echo "   Image: $FULL_IMAGE_NAME"
    echo ""
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi

# Step 2: Verify the image
echo "🔍 Verifying image..."
sudo docker images | grep "$IMAGE_NAME"
echo ""

# Step 3: Show image details
echo "📊 Image Information:"
echo "==========================================="
IMAGE_ID=$(sudo docker images -q "$FULL_IMAGE_NAME" | head -1)
IMAGE_SIZE=$(sudo docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep "$FULL_IMAGE_NAME" | awk '{print $2}')
echo "Image ID: $IMAGE_ID"
echo "Size: $IMAGE_SIZE"
echo ""

# Step 4: Optional - Test run
read -p "Do you want to test run the image? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Starting test container..."
    echo "   Note: Press Ctrl+C to stop"
    echo ""
    sudo docker run --rm -p 8000:8000 \
        -v $(pwd)/rehab_coach.db:/app/rehab_coach.db \
        --env-file .env.docker \
        "$FULL_IMAGE_NAME" \
        python -c "print('✓ Docker image is working correctly!')"
fi

echo ""
echo "=========================================="
echo "✅ Docker build complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy .env.docker to .env and configure API keys"
echo "   cp .env.docker .env"
echo "   nano .env"
echo ""
echo "2. Run with docker-compose:"
echo "   docker-compose up -d"
echo ""
echo "3. Or run directly:"
echo "   docker run -p 8000:8000 --env-file .env $FULL_IMAGE_NAME"
echo ""
echo "Access the app at: http://localhost:8000"
echo ""
