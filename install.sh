#!/bin/bash
#
# BOS-Radio-Bridge Installation Script
# Installs dependencies and systemd service for Raspberry Pi OS
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_NAME="bos-bridge"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON3=$(which python3)

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}=== BOS-Radio-Bridge Installation ===${NC}"

# Update package list
echo -e "${YELLOW}Updating package list...${NC}"
apt-get update

# Install Python dependencies (system packages)
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt-get install -y python3 python3-pip python3-venv python3-dev

# Install NumPy (required dependency)
echo -e "${YELLOW}Installing NumPy...${NC}"
pip3 install --upgrade pip
pip3 install numpy

# Check if colorama is needed (optional, for colored output)
if python3 -c "import colorama" 2>/dev/null; then
    echo -e "${GREEN}colorama already installed${NC}"
else
    echo -e "${YELLOW}Installing colorama (optional)...${NC}"
    pip3 install colorama || echo -e "${YELLOW}Warning: colorama installation failed (optional)${NC}"
fi

# Create systemd service file
echo -e "${YELLOW}Creating systemd service file...${NC}"
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=BOS-Radio-Bridge - Bidirectional Python Radio Bridge
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON3} ${SCRIPT_DIR}/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# Security settings
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chmod 644 "${SERVICE_FILE}"

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Enable service (but don't start yet)
echo -e "${YELLOW}Enabling ${SERVICE_NAME} service...${NC}"
systemctl enable "${SERVICE_NAME}"

# Check if config.json exists
if [ ! -f "${SCRIPT_DIR}/config.json" ]; then
    echo -e "${RED}Warning: config.json not found in ${SCRIPT_DIR}${NC}"
    echo -e "${YELLOW}Please create config.json before starting the service${NC}"
else
    echo -e "${GREEN}config.json found${NC}"
fi

# Summary
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo -e "${GREEN}Service file: ${SERVICE_FILE}${NC}"
echo -e "${GREEN}Working directory: ${SCRIPT_DIR}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review/edit ${SERVICE_FILE} if needed"
echo -e "  2. Check/edit ${SCRIPT_DIR}/config.json"
echo -e "  3. Start service: systemctl start ${SERVICE_NAME}"
echo -e "  4. Check status: systemctl status ${SERVICE_NAME}"
echo -e "  5. View logs: journalctl -u ${SERVICE_NAME} -f"
echo ""

