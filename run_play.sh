#!/bin/bash

# Quick fix for docker-compose not found issue
SSH_KEY="oneacre-prod.pem"
SERVER_HOST="ec2-3-110-50-194.ap-south-1.compute.amazonaws.com"
ANSIBLE_USER="ubuntu"

echo "🔧 Quick fix for docker-compose issue..."

# SSH to server and fix docker-compose
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ANSIBLE_USER@$SERVER_HOST" << 'EOF'

echo "🐳 Installing docker-compose..."

# Download and install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose

# Make it executable
sudo chmod +x /usr/local/bin/docker-compose

# Create symlink
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Verify installation
echo "✅ Docker Compose version:"
docker-compose --version

# Now run the docker commands
echo "🚀 Starting deployment..."
cd /opt/geomapping

# Build containers
echo "🔧 Building containers..."
docker-compose build --no-cache

# Start containers
echo "🏃 Starting containers..."
docker-compose up -d

# Wait a bit
sleep 15

# Run migrations
echo "🗄️ Running migrations..."
docker-compose exec -T web python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

# Show status
echo "📊 Container status:"
docker-compose ps

echo "✅ Deployment completed!"
echo "🌐 Your app should be available at: http://ec2-3-110-50-194.ap-south-1.compute.amazonaws.com:8000"

EOF

echo "🎉 Quick fix completed!"