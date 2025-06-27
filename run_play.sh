#!/bin/bash

# Set the system language to UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Define variables
PRIMARY_USER="root"
SERVER_IP="134.122.116.219"
SERVER_PASSWORD="clustering@1Acre"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting GeoMapping Deployment${NC}"
echo -e "${YELLOW}📡 Target Server: ${SERVER_IP}${NC}"
echo -e "${YELLOW}👤 User: ${PRIMARY_USER}${NC}"

# Check if Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo -e "${RED}❌ Ansible is not installed. Installing...${NC}"
    
    # Install Ansible based on OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Ubuntu/Debian
        if command -v apt &> /dev/null; then
            sudo apt update
            sudo apt install -y ansible sshpass
        # CentOS/RHEL
        elif command -v yum &> /dev/null; then
            sudo yum install -y epel-release
            sudo yum install -y ansible sshpass
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ansible
            # Install sshpass for macOS
            brew install hudochenkov/sshpass/sshpass
        else
            echo -e "${RED}❌ Please install Homebrew first${NC}"
            echo -e "${YELLOW}💡 Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
            exit 1
        fi
    fi
fi

# Check if sshpass is installed (required for password authentication)
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass not found. Installing...${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install hudochenkov/sshpass/sshpass
        else
            echo -e "${RED}❌ Please install sshpass manually or use SSH keys${NC}"
            echo -e "${YELLOW}💡 Alternative: brew install hudochenkov/sshpass/sshpass${NC}"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt &> /dev/null; then
            sudo apt install -y sshpass
        elif command -v yum &> /dev/null; then
            sudo yum install -y sshpass
        fi
    fi
fi

# Verify sshpass is now available
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}❌ sshpass is still not available. Please install it manually.${NC}"
    echo -e "${YELLOW}💡 macOS: brew install hudochenkov/sshpass/sshpass${NC}"
    echo -e "${YELLOW}💡 Ubuntu: sudo apt install sshpass${NC}"
    exit 1
fi

echo -e "${GREEN}✅ sshpass is available${NC}"

# Create temporary inventory file
cat > /tmp/inventory << EOF
[servers]
${SERVER_IP} ansible_user=${PRIMARY_USER} ansible_ssh_pass=${SERVER_PASSWORD} ansible_host_key_checking=False

[servers:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
EOF

echo -e "${GREEN}📝 Created inventory file${NC}"

# Check if deploy.yml exists
if [ ! -f "deploy.yml" ]; then
    echo -e "${RED}❌ deploy.yml not found in current directory${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Running Ansible playbook...${NC}"

# Test SSH connection first
echo -e "${YELLOW}🔍 Testing SSH connection...${NC}"
if sshpass -p "${SERVER_PASSWORD}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${PRIMARY_USER}@${SERVER_IP} "echo 'SSH connection successful'" 2>/dev/null; then
    echo -e "${GREEN}✅ SSH connection test passed${NC}"
else
    echo -e "${RED}❌ SSH connection test failed${NC}"
    echo -e "${YELLOW}💡 Please check:${NC}"
    echo -e "   - Server IP: ${SERVER_IP}"
    echo -e "   - Username: ${PRIMARY_USER}"
    echo -e "   - Password: [hidden]"
    echo -e "   - Server firewall allows SSH (port 22)"
    exit 1
fi

# Run the Ansible playbook
ansible-playbook \
    -i /tmp/inventory \
    -e "ansible_ssh_pass=${SERVER_PASSWORD}" \
    -e "ansible_become_pass=${SERVER_PASSWORD}" \
    deploy.yml

DEPLOYMENT_STATUS=$?

# Clean up temporary files
rm -f /tmp/inventory

if [ $DEPLOYMENT_STATUS -eq 0 ]; then
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "${BLUE}🌐 Application should be available at: http://${SERVER_IP}:8000${NC}"
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo -e "   1. Open http://${SERVER_IP}:8000 in your browser"
    echo -e "   2. SSH to server: ssh ${PRIMARY_USER}@${SERVER_IP}"
    echo -e "   3. Check containers: docker-compose ps"
    echo -e "   4. View logs: docker-compose logs -f"
else
    echo -e "${RED}❌ Deployment failed with exit code ${DEPLOYMENT_STATUS}${NC}"
    echo -e "${YELLOW}💡 Try running with verbose mode: ${NC}"
    echo -e "   ansible-playbook -i /tmp/inventory -vvv deploy.yml"
fi

exit $DEPLOYMENT_STATUS