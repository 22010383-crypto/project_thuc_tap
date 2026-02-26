#!/bin/bash
echo "Installing dependencies for Realtime Mode..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo:"
    echo "sudo bash INSTALL_DEPS.sh"
    exit 1
fi

# Install system packages
apt update
apt install -y \
    python3-opencv \
    python3-numpy \
    python3-scipy \
    python3-pil.imagetk \
    cmake

# Install dlib and face_recognition
apt install -y python3-dlib || {
    echo "Installing dlib from pip..."
    apt install -y build-essential python3-dev python3-pip
    pip3 install --break-system-packages dlib
}

apt install -y python3-face-recognition || {
    echo "Installing face_recognition from pip..."
    pip3 install --break-system-packages face_recognition
}

echo ""
echo "✓ Installation complete!"
echo ""
echo "Now run: python3 run_realtime.py"
