#!/bin/bash

echo "🧪 Testing VNC and Browser Setup..."

# Test 1: Check if VNC processes are running
echo "📊 Checking VNC processes..."
XVFB_COUNT=$(pgrep Xvfb | wc -l)
X11VNC_COUNT=$(pgrep x11vnc | wc -l)
WEBSOCKIFY_COUNT=$(pgrep websockify | wc -l)

echo "   - Xvfb processes: $XVFB_COUNT"
echo "   - x11vnc processes: $X11VNC_COUNT"
echo "   - websockify processes: $WEBSOCKIFY_COUNT"

if [ $XVFB_COUNT -eq 0 ] || [ $X11VNC_COUNT -eq 0 ] || [ $WEBSOCKIFY_COUNT -eq 0 ]; then
    echo "❌ Some VNC processes are not running. Run ./start_vnc_improved.sh first"
    exit 1
fi

# Test 2: Check DISPLAY variable
echo "🖥️  Checking DISPLAY variable..."
if [ -n "$DISPLAY" ]; then
    echo "   ✅ DISPLAY is set to: $DISPLAY"
else
    echo "   ⚠️  DISPLAY not set. Trying to set it..."
    export DISPLAY=:1
    echo "   🔧 DISPLAY set to: $DISPLAY"
fi

# Test 3: Test X11 connection
echo "🔌 Testing X11 connection..."
if command -v xdpyinfo &> /dev/null; then
    if DISPLAY=:1 xdpyinfo > /dev/null 2>&1; then
        echo "   ✅ X11 connection successful"
    else
        echo "   ❌ X11 connection failed"
        echo "   💡 Try restarting VNC: ./stop_vnc.sh && ./start_vnc_improved.sh"
    fi
else
    echo "   ⚠️  xdpyinfo not available, skipping X11 test"
fi

# Test 4: Check network connectivity
echo "🌐 Testing network ports..."
if ss -tuln | grep -q ":5901 "; then
    echo "   ✅ VNC port 5901 is listening"
else
    echo "   ❌ VNC port 5901 is not listening"
fi

if ss -tuln | grep -q ":6080 "; then
    echo "   ✅ NoVNC port 6080 is listening"
else
    echo "   ❌ NoVNC port 6080 is not listening"
fi

# Test 5: Test browser launch (quick test)
echo "🌐 Testing browser launch..."
cd /root/twitter_scraper

# Create a simple test script
cat > test_browser.py << 'EOF'
import asyncio
import os
from playwright.async_api import async_playwright

async def test_browser():
    print(f"DISPLAY = {os.environ.get('DISPLAY', 'Not set')}")
    
    try:
        async with async_playwright() as p:
            # Try to launch browser
            has_display = os.environ.get('DISPLAY') is not None
            browser = await p.chromium.launch(
                headless=not has_display,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            page = await browser.new_page()
            await page.goto('https://example.com')
            title = await page.title()
            
            print(f"✅ Browser test successful! Page title: {title}")
            await browser.close()
            return True
            
    except Exception as e:
        print(f"❌ Browser test failed: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_browser())
EOF

export DISPLAY=:1
if python test_browser.py; then
    echo "   ✅ Browser launches successfully"
else
    echo "   ❌ Browser launch failed"
    echo "   💡 Check that all VNC processes are running and DISPLAY is set"
fi

# Cleanup
rm -f test_browser.py

# Test 6: Show access URLs
echo ""
echo "🔗 Access URLs:"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
if [ "$PUBLIC_IP" != "localhost" ]; then
    echo "   🌍 NoVNC Web: http://$PUBLIC_IP:6080/vnc.html"
fi
echo "   🏠 Local NoVNC: http://localhost:6080/vnc.html"
echo "   📱 VNC Client: $PUBLIC_IP:5901"

echo ""
echo "🎯 Next steps:"
echo "   1. Open NoVNC in browser: http://localhost:6080/vnc.html"
echo "   2. Start your app: ./start_with_display.sh"
echo "   3. Browser should appear in VNC viewer"
