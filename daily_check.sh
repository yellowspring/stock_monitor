 #!/bin/bash
# Crash probability check - runs at 10 AM and 3 PM
# Sends email alerts if probability exceeds 60%

# Set PATH for cron environment
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Set project directory
PROJECT_DIR="/home/tom2zhang/workspace/proj_stock_monitor"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"

# Change to project directory
cd "${PROJECT_DIR}" || exit 1

# Create logs directory if it doesn't exist
mkdir -p logs

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
echo "=================================================================================" >> logs/alerts.log
echo "Check started: $(date)" >> logs/alerts.log
echo "Using Python: ${VENV_PYTHON}" >> logs/alerts.log

# Verify Python exists
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "ERROR: Python not found at ${VENV_PYTHON}" >> logs/alerts.log
    exit 1
fi

# Run crash monitor with 60% threshold using venv python directly
# --daily-report: Always send a daily summary email
# --email: Also send alert email if probability exceeds 60%
# SMS disabled due to Twilio trial account limitations (error 30032)
# To enable: upgrade Twilio account at https://www.twilio.com/console/billing
"${VENV_PYTHON}" monitor_with_alerts.py --threshold 60 --email --daily-report >> logs/alerts.log 2>&1

# Log completion
echo "Check completed: $(date)" >> logs/alerts.log
echo "" >> logs/alerts.log
