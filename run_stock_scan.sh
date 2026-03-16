#!/bin/bash
# Stock scanner - runs at 1 AM daily
# Scans stocks and caches results for the daily report

# Set PATH for cron environment
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Set project directory
PROJECT_DIR="/home/tom2zhang/workspace/proj_stock_monitor"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"

# Change to project directory
cd "${PROJECT_DIR}" || exit 1

# Create logs and cache directories if they don't exist
mkdir -p logs
mkdir -p cache

# Load environment variables from .env file (handle special characters in values)
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        # Export the variable
        export "$line"
    done < .env
fi

# Log timestamp
echo "=================================================================================" >> logs/scan.log
echo "Stock scan started: $(date)" >> logs/scan.log
echo "Using Python: ${VENV_PYTHON}" >> logs/scan.log

# Verify Python exists
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "ERROR: Python not found at ${VENV_PYTHON}" >> logs/scan.log
    exit 1
fi

# Run stock scanner with ALL stock universes combined
# Includes: S&P 500 + NASDAQ 100 + Mid-cap 400 + Dividend Aristocrats (~680 stocks)
# ETFs are scanned SEPARATELY using ETFEvaluator (~80 ETFs with 4Q model)
# Results cached to: cache/stock_scan_results.json + cache/etf_scan_results.json
# Using 2 workers with rate limiting to avoid Yahoo Finance throttling
# Estimated time: ~60-80 minutes for stocks + ~5 minutes for ETFs
"${VENV_PYTHON}" run_stock_scan.py --universe all --top 50 --min-score 45 --workers 2 >> logs/scan.log 2>&1

# Log completion
echo "Stock scan completed: $(date)" >> logs/scan.log
echo "" >> logs/scan.log
