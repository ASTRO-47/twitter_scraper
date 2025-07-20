#!/bin/bash

echo "🚀 Starting VNC server for remote browser access..."

# Function to get public IP
get_public_ip() {
    local ip=$(curl -s ifconfig.me 2>/dev/null)
    if [ -n "$ip" ]; then
        echo "$ip"
    else
        echo "localhost"
    fi
}

# Kill any existing processes
echo "🔄 Stopping existing VNC processes..."
pkill Xvfb 2>/dev/null
pkill x11vnc 2>/dev/null
pkill websockify 2>/dev/null

# Wait for processes to terminate
sleep 3

# Create VNC log directory
mkdir -p /root/.vnc

# Check if required packages are installed
check_dependencies() {
    local missing=""
    
    if ! command -v Xvfb &> /dev/null; then
        missing="$missing xvfb"
    fi
    
    if ! command -v x11vnc &> /dev/null; then
        missing="$missing x11vnc"
    fi
    
    if ! command -v websockify &> /dev/null; then
        missing="$missing websockify"
    fi
    
    if [ ! -d "/usr/share/novnc/" ]; then
        missing="$missing novnc"
    fi
    
    if [ -n "$missing" ]; then
        echo "❌ Missing dependencies: $missing"
        echo "📦 Install with: sudo apt update && sudo apt install -y$missing"
        return 1
    fi
    
    return 0
}

# Check dependencies first
if ! check_dependencies; then
    exit 1
fi

# Start a virtual display with better settings
echo "🖥️  Starting virtual display (Xvfb)..."
Xvfb :1 -screen 0 1366x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 3

# Check if Xvfb started successfully
if ! pgrep Xvfb > /dev/null; then
    echo "❌ Failed to start Xvfb"
    exit 1
fi
echo "✅ Xvfb started successfully (PID: $XVFB_PID)"

# Start VNC server with better options
echo "📡 Starting VNC server (x11vnc)..."
x11vnc -display :1 -forever -nopw -shared -rfbport 5901 -bg -o /root/.vnc/x11vnc.log -xkb
sleep 2

# Check if x11vnc started successfully
X11VNC_PID=$(pgrep x11vnc)
if [ -z "$X11VNC_PID" ]; then
    echo "❌ Failed to start x11vnc"
    kill $XVFB_PID 2>/dev/null
    exit 1
fi
echo "✅ x11vnc started successfully (PID: $X11VNC_PID)"

# Start NoVNC web interface
echo "🌐 Starting NoVNC web interface..."
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901 &
WEBSOCKIFY_PID=$!
sleep 2

if pgrep websockify > /dev/null; then
    echo "✅ NoVNC started successfully (PID: $(pgrep websockify))"
else
    echo "❌ Failed to start NoVNC"
    kill $XVFB_PID $X11VNC_PID 2>/dev/null
    exit 1
fi

# Set the display environment variable GLOBALLY
echo "🔧 Setting DISPLAY environment variable..."
export DISPLAY=:1
echo "export DISPLAY=:1" >> ~/.bashrc
echo "export DISPLAY=:1" >> ~/.zshrc

# Also create a systemd environment file for services
echo "DISPLAY=:1" > /tmp/display.env

# Test if display is working
echo "🧪 Testing display..."
if command -v xdpyinfo &> /dev/null; then
    if DISPLAY=:1 xdpyinfo > /dev/null 2>&1; then
        echo "✅ Display test passed"
    else
        echo "⚠️  Display test failed, but continuing..."
    fi
fi

# Get public IP for access instructions
PUBLIC_IP=$(get_public_ip)

# Create a startup script for the Twitter scraper with proper environment
cat > /root/twitter_scraper/start_with_display.sh << 'EOF'
#!/bin/bash
# Load display environment
export DISPLAY=:1

# Also try to source any existing environment
[ -f /tmp/display.env ] && export $(cat /tmp/display.env | xargs)

# Change to the project directory
cd /root/twitter_scraper

echo "🚀 Starting Twitter scraper with DISPLAY=$DISPLAY"

# Start your FastAPI application
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF

chmod +x /root/twitter_scraper/start_with_display.sh

echo ""
echo "🎉 VNC SERVER IS READY!"
echo "=========================="
if [ "$PUBLIC_IP" != "localhost" ]; then
    echo "🌍 NoVNC Web Access: http://$PUBLIC_IP:6080/vnc.html"
fi
echo "🔐 SSH tunnel access: http://localhost:6080/vnc.html"
echo "💡 SSH tunnel command: ssh -L 6080:localhost:6080 user@$PUBLIC_IP"
echo "📊 VNC direct port: $PUBLIC_IP:5901 (for VNC clients)"
echo "=========================="
echo ""
echo "🐍 To start your Python app with proper display:"
echo "   ./start_with_display.sh"
echo "   OR"
echo "   export DISPLAY=:1 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "✨ Ready for browser automation!"

# Save process IDs for cleanup script
cat > /root/.vnc/pids << EOF
XVFB_PID=$XVFB_PID
X11VNC_PID=$X11VNC_PID
WEBSOCKIFY_PID=$(pgrep websockify)
EOF

echo "📝 Process IDs saved to /root/.vnc/pids for cleanup"
