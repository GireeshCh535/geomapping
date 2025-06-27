#!/bin/bash

SERVER_IP="134.122.116.219"
SERVER_PASSWORD="clustering@1Acre"
REPO_URL="https://gitlab.com/rohit.boni/geomapping.git"

echo "🚀 Manual deployment starting..."

# Step 1: Clone locally (you're already authenticated)
echo "📥 Cloning repository locally..."
rm -rf /tmp/geomapping_deploy
git clone $REPO_URL /tmp/geomapping_deploy

# Step 2: Create archive
echo "📦 Creating archive..."
cd /tmp
tar -czf geomapping.tar.gz -C geomapping_deploy .

# Step 3: Upload to server
echo "⬆️  Uploading to server..."
sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no geomapping.tar.gz root@$SERVER_IP:/tmp/

# Step 4: Deploy on server
echo "🚀 Deploying on server..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no root@$SERVER_IP << 'EOF'

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    apt update
    apt install -y docker.io docker-compose git
    systemctl start docker
    systemctl enable docker
fi

# Setup project
cd /opt
rm -rf geomapping
mkdir -p geomapping
cd geomapping

# Extract uploaded code
tar -xzf /tmp/geomapping.tar.gz

# Update Django settings for server access
sed -i "s/ALLOWED_HOSTS = \[\]/ALLOWED_HOSTS = ['*']/" geo_mapping/settings.py || true
sed -i "s/ALLOWED_HOSTS = \[.*\]/ALLOWED_HOSTS = ['*']/" geo_mapping/settings.py || true

# Stop old containers
docker-compose down 2>/dev/null || true

# Build and start
echo "🔧 Building containers..."
docker-compose build

echo "🚀 Starting containers..."
docker-compose up -d

# Wait a bit for containers to start
sleep 15

# Run migrations
echo "🗄️  Running migrations..."
docker-compose exec -T web python manage.py migrate 2>/dev/null || echo "Migrations skipped"

# Clean up
rm -f /tmp/geomapping.tar.gz

echo "✅ Deployment completed!"
echo "🌐 Application should be available at: http://134.122.116.219:8000"

EOF

# Clean up local files
rm -rf /tmp/geomapping_deploy
rm -f /tmp/geomapping.tar.gz

echo "🎉 Manual deployment completed!"
echo "🌐 Check: http://$SERVER_IP:8000"