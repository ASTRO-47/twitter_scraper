#!/bin/bash

echo "🛑 Stopping VNC server and related processes..."

# Kill processes by name
echo "🔄 Killing processes by name..."
pkill Xvfb 2>/dev/null
pkill x11vnc 2>/dev/null  
pkill websockify 2>/dev/null

# Also try to kill by PID if available
if [ -f "/root/.vnc/pids" ]; then
    echo "🔄 Killing processes by saved PIDs..."
    source /root/.vnc/pids
    [ -n "$XVFB_PID" ] && kill $XVFB_PID 2>/dev/null
    [ -n "$X11VNC_PID" ] && kill $X11VNC_PID 2>/dev/null
    [ -n "$WEBSOCKIFY_PID" ] && kill $WEBSOCKIFY_PID 2>/dev/null
    rm -f /root/.vnc/pids
fi

# Wait for processes to terminate
sleep 2

# Check what's still running
echo "📊 Checking remaining processes..."
REMAINING_XVFB=$(pgrep Xvfb | wc -l)
REMAINING_X11VNC=$(pgrep x11vnc | wc -l) 
REMAINING_WEBSOCKIFY=$(pgrep websockify | wc -l)

if [ $REMAINING_XVFB -eq 0 ] && [ $REMAINING_X11VNC -eq 0 ] && [ $REMAINING_WEBSOCKIFY -eq 0 ]; then
    echo "✅ All VNC processes stopped successfully"
else
    echo "⚠️  Some processes may still be running:"
    [ $REMAINING_XVFB -gt 0 ] && echo "   - Xvfb: $REMAINING_XVFB processes"
    [ $REMAINING_X11VNC -gt 0 ] && echo "   - x11vnc: $REMAINING_X11VNC processes" 
    [ $REMAINING_WEBSOCKIFY -gt 0 ] && echo "   - websockify: $REMAINING_WEBSOCKIFY processes"
    echo "🔧 Try: sudo killall -9 Xvfb x11vnc websockify"
fi

# Clean up environment
echo "🧹 Cleaning up environment..."
rm -f /tmp/display.env

echo "🎉 VNC cleanup complete!"
