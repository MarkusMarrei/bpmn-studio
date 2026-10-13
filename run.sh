#!/usr/bin/env bash
set -e

# Move to the directory containing this script
cd "$(dirname "$0")"

echo "====================================================================="
echo "  BPMN Studio - Local AI BPMN Generator"
echo "  Author: Markus Marrei (Apache 2.0 License)"
echo "====================================================================="
echo ""

# Find python3 or python
if command -v python3 &> /dev/null; then
    PY_CMD="python3"
elif command -v python &> /dev/null; then
    PY_CMD="python"
else
    echo "[ERROR] Python 3 was not found in your system PATH!"
    echo "Please install Python 3.10+ (e.g. sudo apt install python3 python3-pip)"
    exit 1
fi

echo "[1/2] Checking Python packages..."
if ! $PY_CMD -c "import fastapi, uvicorn" &> /dev/null; then
    echo "[INFO] Installing required dependencies from requirements.txt..."
    $PY_CMD -m pip install -r requirements.txt
fi

echo "[2/2] Starting server at http://127.0.0.1:8000 ..."
echo "Browser will open automatically. Press Ctrl+C to stop the server."
echo ""
$PY_CMD app.py
