#!/bin/bash

# Configuration
SSH_KEY="oneacre-prod.pem"
SERVER_HOST="13.201.23.9"
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
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$ANSIBLE_USER@$SERVER_HOST" "echo 'SSH connection successful'" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ SSH connection failed. Please check:"
    echo "   1. SSH key path: $SSH_KEY"
    echo "   2. Server hostname: $SERVER_HOST"
    echo "   3. AWS Security Group allows SSH (port 22)"
    echo "   4. Server is running"
    exit 1
fi

echo "✅ SSH connection verified"

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
    echo "   http://$SERVER_HOST"
    echo ""
    echo "📋 Useful commands to check your deployment:"
    echo "   ssh -i \"$SSH_KEY\" $ANSIBLE_USER@$SERVER_HOST"
    echo "   cd /opt/geomapping"
    echo "   docker-compose ps"
    echo "   docker-compose logs -f"
    echo ""
    echo "⚠️  Make sure your AWS Security Group allows inbound traffic on port 80"
    echo ""
    echo "🔍 Quick test:"
    echo "   curl http://$SERVER_HOST"
else
    echo "================================================"
    echo "❌ Deployment failed!"
    echo "Please check the error messages above and try again."
    echo ""
    echo "🔍 Common issues:"
    echo "   1. AWS Security Group not allowing SSH (port 22)"
    echo "   2. AWS Security Group not allowing HTTP (port 80)"
    echo "   3. SSH key permissions incorrect"
    echo "   4. Server not responding"
    echo ""
    echo "📞 To debug manually:"
    echo "   ssh -i \"$SSH_KEY\" $ANSIBLE_USER@$SERVER_HOST"
fi

# Clean up temporary inventory file
rm -f "$INVENTORY_FILE"

echo "🧹 Cleaned up temporary files"