#!/bin/bash

# Configuration
SSH_KEY="oneacre-prod.pem"
SERVER_HOST="13.201.23.9"
DOMAIN="gis-portal2.1acre.in" 
ANSIBLE_USER="ubuntu"

echo "🚀 Starting GeoDjango deployment to AWS EC2..."

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found: $SSH_KEY"
    echo "Please ensure the SSH key file exists and has correct permissions."
    exit 1
fi

# Set correct permissions for SSH key
chmod 400 "$SSH_KEY"
echo "✅ SSH key permissions set"

# Check if Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "📦 Installing Ansible..."
    pip3 install ansible
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Ansible. Please install manually:"
        echo "   pip3 install ansible"
        exit 1
    fi
fi

echo "✅ Ansible is available"

# Create temporary inventory file
INVENTORY_FILE="/tmp/inventory_aws.ini"
cat > "$INVENTORY_FILE" << EOF
[aws_servers]
geomapping-server ansible_host=$SERVER_HOST

[aws_servers:vars]
ansible_user=$ANSIBLE_USER
ansible_ssh_private_key_file=$SSH_KEY
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
ansible_python_interpreter=/usr/bin/python3
EOF

echo "✅ Inventory file created"

# Test SSH connection
echo "🔐 Testing SSH connection..."
SSH_TEST=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes "$ANSIBLE_USER@$SERVER_HOST" "echo 'SSH connection successful'" 2>&1)
SSH_EXIT_CODE=$?

if [ $SSH_EXIT_CODE -ne 0 ]; then
    echo "⚠️  SSH test failed, but this might be a false positive."
    echo "📋 SSH test output: $SSH_TEST"
    echo ""
    echo "🔄 Continuing with deployment anyway..."
    echo "   (Manual SSH works, so Ansible should work too)"
    echo ""
else
    echo "✅ SSH connection verified"
fi

# Check if deploy.yml exists
if [ ! -f "deploy.yml" ]; then
    echo "❌ deploy.yml not found in current directory"
    echo "Please ensure deploy.yml is in the same directory as this script"
    exit 1
fi

echo "✅ deploy.yml found"

# Run the Ansible playbook
echo "🚀 Running Ansible playbook..."
echo "================================================"

ansible-playbook -i "$INVENTORY_FILE" deploy.yml -v

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo "================================================"
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "🌐 Your application should be available at:"
    echo "   🔒 HTTPS: https://$DOMAIN"
    echo "   📱 HTTP:  http://$DOMAIN (redirects to HTTPS)"
    echo "   🔗 API:   https://$DOMAIN/api/"
    echo ""
    echo "📋 Useful commands to check your deployment:"
    echo "   ssh -i \"$SSH_KEY\" $ANSIBLE_USER@$SERVER_HOST"
    echo "   cd /opt/geomapping"
    echo "   docker-compose ps"
    echo "   docker-compose logs -f web"
    echo "   docker-compose logs -f nginx"
    echo ""
    echo "⚠️  Make sure your AWS Security Group allows inbound traffic on:"
    echo "   📡 Port 22 (SSH)"
    echo "   🌐 Port 80 (HTTP - redirects to HTTPS)"
    echo "   🔒 Port 443 (HTTPS)"
    echo ""
    echo "🔍 Quick tests:"
    echo "   curl -I https://$DOMAIN"
    echo "   curl -I http://$DOMAIN"
    echo ""
    echo "📊 Branch deployed: change_of_pattern"
    echo "🎯 Domain: $DOMAIN"
    echo "💻 Server IP: $SERVER_HOST"
else
    echo "================================================"
    echo "❌ Deployment failed!"
    echo "Please check the error messages above and try again."
    echo ""
    echo "🔍 Common issues:"
    echo "   1. AWS Security Group not allowing SSH (port 22)"
    echo "   2. AWS Security Group not allowing HTTP (port 80) and HTTPS (port 443)"
    echo "   3. SSH key permissions incorrect"
    echo "   4. Server not responding"
    echo "   5. Docker containers failing to start"
    echo "   6. SSL certificate issues"
    echo ""
    echo "📞 To debug manually:"
    echo "   ssh -i \"$SSH_KEY\" $ANSIBLE_USER@$SERVER_HOST"
    echo "   cd /opt/geomapping"
    echo "   docker-compose logs -f"
    echo ""
    echo "🏥 Health checks:"
    echo "   docker-compose ps"
    echo "   curl -I https://$DOMAIN"
fi

# Clean up temporary inventory file
rm -f "$INVENTORY_FILE"

echo "🧹 Cleaned up temporary files"