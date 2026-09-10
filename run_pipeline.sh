#!/bin/bash
# ==============================================================================
# 2-STAGE AUTOMATED AGY STOCK EXTRACTION PIPELINE SCRIPT
# Step 1: Saves translated transcript to text file (reuses if already exists)
# Step 2: Analyzes transcript with LLM / AGY Engine & saves 'DD-MM-YY - Title.md'
# ==============================================================================

URL="$1"
METHOD="${2:-agy}"
FORMAT="${3:-markdown}"

if [ -z "$URL" ]; then
    echo "Usage: ./run_pipeline.sh <YOUTUBE_URL_OR_ID> [METHOD] [FORMAT]"
    exit 1
fi

PYTHON_CMD="python"
if [ -f "./.venv/bin/python" ]; then
    PYTHON_CMD="./.venv/bin/python"
elif [ -f "../stock_rec/.venv/bin/python" ]; then
    PYTHON_CMD="../stock_rec/.venv/bin/python"
elif [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_CMD="$VIRTUAL_ENV/bin/python"
fi

echo "============================================================"
echo " STARTING AUTOMATED AGY STOCK EXTRACTION PIPELINE"
echo " Video URL: $URL"
echo " Python:    $PYTHON_CMD"
echo " Method:    $METHOD"
echo "============================================================"

$PYTHON_CMD pipeline.py "$URL" --method "$METHOD" --format "$FORMAT"

