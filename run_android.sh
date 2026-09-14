#!/data/data/com.termux/files/usr/bin/bash
# =======================================================
# StockExtractor AI - Android Termux Launcher
# =======================================================

echo "============================================================"
echo " Starting StockExtractor AI on Android (Termux)"
echo " Server URL: http://localhost:8000"
echo "============================================================"

# Ensure script runs from the repository root
cd "$(dirname "$0")"

# Launch using uvicorn with pure asyncio loop on port 8000
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
