# VNC Browser Automation Setup

This guide helps you set up a VNC server to remotely view and control the browser during Twitter scraping operations.

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   sudo ./install_vnc_deps.sh
   ```

2. **Start VNC server:**
   ```bash
   ./start_vnc_improved.sh
   ```

3. **Test the setup:**
   ```bash
   ./test_vnc_setup.sh
   ```

4. **Start your application:**
   ```bash
   ./start_with_display.sh
   ```

5. **Access the browser:**
   - Open http://localhost:6080/vnc.html in your web browser
   - You should see the remote desktop where the browser will appear

## 📁 Files Overview

| File | Purpose |
|------|---------|
| `install_vnc_deps.sh` | Install all required VNC dependencies |
| `start_vnc_improved.sh` | Start the VNC server with proper configuration |
| `stop_vnc.sh` | Stop all VNC processes cleanly |
| `test_vnc_setup.sh` | Test if VNC setup is working correctly |
| `start_with_display.sh` | Start the Twitter scraper with proper DISPLAY variable |

## 🔧 What the Scripts Do

### start_vnc_improved.sh
- Starts Xvfb (virtual display server) on display :1
- Starts x11vnc (VNC server) on port 5901
- Starts websockify/NoVNC web interface on port 6080
- Sets DISPLAY environment variable globally
- Creates startup script for your application
- Performs dependency checks

### Key Improvements Over Original Script
- ✅ Better error handling and process management
- ✅ Dependency verification
- ✅ Global DISPLAY environment variable setting
- ✅ Process ID tracking for clean shutdown
- ✅ Automatic startup script generation
- ✅ Display testing and verification

## 🌐 Access Methods

1. **Web Browser (Recommended):**
   - Local: http://localhost:6080/vnc.html
   - Remote: http://YOUR_SERVER_IP:6080/vnc.html

2. **VNC Client:**
   - Server: YOUR_SERVER_IP:5901
   - No password required

3. **SSH Tunnel (Secure):**
   ```bash
   ssh -L 6080:localhost:6080 user@YOUR_SERVER_IP
   ```
   Then access: http://localhost:6080/vnc.html

## 🐛 Troubleshooting

### Browser Not Appearing
1. Check if VNC processes are running:
   ```bash
   pgrep Xvfb && pgrep x11vnc && pgrep websockify
   ```

2. Verify DISPLAY variable:
   ```bash
   echo $DISPLAY  # Should show :1
   ```

3. Test X11 connection:
   ```bash
   DISPLAY=:1 xdpyinfo
   ```

### VNC Web Interface Not Loading
1. Check if websockify is running on port 6080:
   ```bash
   ss -tuln | grep 6080
   ```

2. Check firewall settings:
   ```bash
   sudo ufw status
   # If needed: sudo ufw allow 6080
   ```

### Browser Launch Fails
1. Run the test script:
   ```bash
   ./test_vnc_setup.sh
   ```

2. Check if all dependencies are installed:
   ```bash
   ./install_vnc_deps.sh
   ```

3. Restart VNC completely:
   ```bash
   ./stop_vnc.sh
   sleep 5
   ./start_vnc_improved.sh
   ```

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "Cannot open display :1" | Run `./start_vnc_improved.sh` to start VNC |
| NoVNC shows black screen | Wait 10-15 seconds, refresh browser |
| Browser crashes immediately | Add `--disable-dev-shm-usage --no-sandbox` to browser args |
| Permission denied errors | Run scripts with `sudo` if needed |

## 🔒 Security Notes

- This setup uses VNC without password for simplicity
- For production, consider:
  - Adding VNC password authentication
  - Using SSL/TLS encryption
  - Restricting network access with firewall rules
  - Using SSH tunneling for remote access

## 📊 Resource Usage

- Xvfb: ~50MB RAM
- x11vnc: ~20MB RAM  
- websockify: ~10MB RAM
- Chromium browser: ~200-500MB RAM (per instance)

## 🎯 Integration with Twitter Scraper

The scraper has been modified to:
- ✅ Auto-detect if DISPLAY is available
- ✅ Run headless when no display (server mode)
- ✅ Run headed when display available (VNC mode)
- ✅ Use appropriate browser arguments for each mode

## 📝 Manual Commands

If you prefer to run commands manually:

```bash
# Start VNC manually
export DISPLAY=:1
Xvfb :1 -screen 0 1366x768x24 -ac +extension GLX +render -noreset &
x11vnc -display :1 -forever -nopw -shared -rfbport 5901 -bg
websockify --web=/usr/share/novnc/ 6080 localhost:5901 &

# Start your app with display
DISPLAY=:1 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Stop VNC manually  
pkill Xvfb x11vnc websockify
```

## ✨ Success Indicators

When everything is working correctly, you should see:
- ✅ All VNC processes running (Xvfb, x11vnc, websockify)
- ✅ NoVNC web interface loads at http://localhost:6080/vnc.html
- ✅ Desktop/background visible in NoVNC viewer
- ✅ Browser window appears in VNC when scraper runs
- ✅ Console shows "Display available: True (DISPLAY=:1)"
