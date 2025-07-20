#!/bin/bash

echo "📦 Installing VNC and NoVNC dependencies..."

# Update package list
echo "🔄 Updating package list..."
apt update

# Install required packages
echo "📥 Installing packages..."
apt install -y xvfb x11vnc websockify novnc

# Install additional useful tools
apt install -y x11-utils xauth

# Verify installations
echo "✅ Verifying installations..."

check_command() {
    if command -v "$1" &> /dev/null; then
        echo "✅ $1 is installed"
        return 0
    else
        echo "❌ $1 is NOT installed"
        return 1
    fi
}

SUCCESS=true

check_command "Xvfb" || SUCCESS=false
check_command "x11vnc" || SUCCESS=false 
check_command "websockify" || SUCCESS=false

if [ -d "/usr/share/novnc/" ]; then
    echo "✅ NoVNC is installed"
else
    echo "❌ NoVNC is NOT installed"
    SUCCESS=false
fi

check_command "xdpyinfo" || echo "⚠️  x11-utils not fully installed (optional)"

if [ "$SUCCESS" = true ]; then
    echo ""
    echo "🎉 All dependencies installed successfully!"
    echo "📝 You can now run: ./start_vnc_improved.sh"
else
    echo ""
    echo "❌ Some installations failed. Please check the errors above."
    exit 1
fi
