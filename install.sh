#!/bin/bash

# Exit on any error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root"
  exit 1
fi

# Create install directory
install_dir="/opt/berryble"
mkdir -p $install_dir

# Copy files
cp berryble.py $install_dir/
cp requirements.txt $install_dir/
cp berryble.service /etc/systemd/system/

# Setup Python environment
python3 -m venv --system-site-packages $install_dir/venv
$install_dir/venv/bin/pip install -r $install_dir/requirements.txt

# Install system dependencies
apt-get update
apt-get install -y libgirepository1.0-dev libcairo2-dev python3-dev gir1.2-secret-1

# Setup systemd service
systemctl daemon-reload
systemctl enable berryble
systemctl start berryble

echo "Installation complete! Service is running."
