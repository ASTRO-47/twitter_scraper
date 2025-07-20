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
