#!/bin/bash

set -e

# Target directory for everything
ROOT_DIR="/goinfre/$USER"
VENV_DIR="$ROOT_DIR/venv"
PLAYWRIGHT_CACHE="$ROOT_DIR/playwright-browsers"
PIP_CACHE="$ROOT_DIR/pip-cache"

# Export paths to redirect installs
export PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_CACHE"
export PIP_CACHE_DIR="$PIP_CACHE"

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3 and rerun this script."
    exit 1
fi

# 2. Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "📦 pip3 is not installed. Installing pip3..."
    python3 -m ensurepip --upgrade || sudo apt-get install -y python3-pip
fi

# 3. Install venv if not present
if ! python3 -m venv --help &> /dev/null; then
    echo "📦 python3-venv is not installed. Installing..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# 4. Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "📁 Creating virtualenv in $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# 5. Activate virtual environment
source "$VENV_DIR/bin/activate"

# 6. Upgrade pip using redirected cache
pip install --upgrade pip

# 7. Install dependencies from requirements.txt
pip install -r requirements.txt

# 8. Install Playwright browser (optional: just Chromium if you want)
python -m playwright install chromium

# 9. Done
cat << EOF

✅ Setup complete!

📁 All files were stored in: $ROOT_DIR

To activate your virtual environment, run:
  source $VENV_DIR/bin/activate

To start the FastAPI app, run:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Open: http://localhost:8000/

EOF
