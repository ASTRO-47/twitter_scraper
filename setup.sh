#!/bin/bash

set -e

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python 3 and rerun this script."
    exit 1
fi

# 2. Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Installing pip3..."
    python3 -m ensurepip --upgrade || sudo apt-get install -y python3-pip
fi

# 3. Install venv if not present
if ! python3 -m venv --help &> /dev/null; then
    echo "python3-venv is not installed. Installing python3-venv..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# 4. Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 5. Activate virtual environment
source venv/bin/activate

# 6. Upgrade pip
pip install --upgrade pip

# 7. Install dependencies
pip install -r requirements.txt

# 8. Install Playwright browsers
python -m playwright install

# 9. Print instructions
cat << EOF

Setup complete!

To activate your virtual environment, run:
  source venv/bin/activate

To start the FastAPI app, run:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Then open http://localhost:8000/ in your browser.
EOF 