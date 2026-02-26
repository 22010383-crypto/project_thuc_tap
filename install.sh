#!/bin/bash
set -e

echo "Installing dependencies for Face Attendance System..."

# Use pip from current Python
PIP="python3 -m pip"

# Install with --break-system-packages if needed (for Debian/Ubuntu with PEP 668)
INSTALL_CMD="$PIP install"

# Try normal install first, fallback to --break-system-packages
install_package() {
    $INSTALL_CMD "$1" 2>/dev/null || $INSTALL_CMD --break-system-packages "$1"
}

echo "Installing core packages..."
install_package "numpy>=1.21.0"
install_package "opencv-python>=4.5.5"
install_package "Pillow>=9.0.0"
install_package "scipy>=1.7.3"

echo "Installing dlib (may take time)..."
install_package "dlib>=19.24.0"

echo "Installing face_recognition..."
install_package "face-recognition>=1.3.0"

echo "Installing mediapipe (optional, for blink detection)..."
install_package "mediapipe>=0.10.9" || echo "⚠️ MediaPipe failed, will use texture-only mode"

echo "Installing data processing..."
install_package "pandas>=1.3.5"
install_package "openpyxl>=3.0.9"
install_package "scikit-image>=0.19.0"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Run: python3 app/main.py"
