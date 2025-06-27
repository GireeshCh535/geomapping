#!/bin/bash

SERVER_IP="134.122.116.219"
SERVER_PASSWORD="clustering@1Acre"

echo "🚀 Quick deployment starting..."

# Direct deployment without Ansible for speed
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no root@$SERVER_IP << 'EOF'
# Quick server setup
apt update
apt install -y docker.io docker-compose git

# Start docker
systemctl start docker
systemctl enable docker

# Clone repo directly
cd /opt
rm -rf geomapping
git clone --depth 1 https://gitlab.com/rohit.boni/geomapping.git
cd geomapping

# Update settings for server
sed -i "s/ALLOWED_HOSTS = \[\]/ALLOWED_HOSTS = ['*']/" geo_mapping/settings.py

# Build and start
docker-compose down || true
docker-compose build
docker-compose up -d

echo "✅ Quick deployment completed!"
echo "🌐 Application available at: http://134.122.116.219:8000"
EOF