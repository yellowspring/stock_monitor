#!/bin/bash
# Quick setup script for your crash alert system

echo "========================================================================"
echo "CRASH PROBABILITY INDEX - QUICK SETUP"
echo "========================================================================"
echo ""
echo "This will set up email alerts for:"
echo "  - tao.zhang.1977@gmail.com"
echo "  - gao.yuan.77@gmail.com"
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Create .env file
echo "Creating .env configuration file..."
cat > .env << 'EOF'
# Email Configuration for Crash Alerts

# Your Gmail account (sender)
EMAIL_FROM=tao.zhang.1977@gmail.com

# Gmail App Password (NOT your regular password!)
# Get it from: https://myaccount.google.com/apppasswords
EMAIL_PASSWORD=REPLACE-WITH-YOUR-16-CHAR-APP-PASSWORD

# Recipients (both email addresses will receive alerts)
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com

# SMTP Settings (Gmail default)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Alert threshold (60 = EXTREME risk level)
ALERT_THRESHOLD=60

# Optional: SMS via Twilio (leave blank if not using)
# TWILIO_ACCOUNT_SID=
# TWILIO_AUTH_TOKEN=
# TWILIO_FROM=
# TWILIO_TO=
EOF

echo "✓ .env file created"
echo ""
echo "========================================================================"
echo "NEXT STEPS:"
echo "========================================================================"
echo ""
echo "1. Get your Gmail App Password:"
echo "   a. Go to: https://myaccount.google.com/apppasswords"
echo "   b. If needed, enable 2-Factor Authentication first"
echo "   c. Create app password for 'Mail'"
echo "   d. Copy the 16-character password"
echo ""
echo "2. Edit .env file and paste your app password:"
echo "   nano .env"
echo "   (Replace REPLACE-WITH-YOUR-16-CHAR-APP-PASSWORD with your actual password)"
echo ""
echo "3. Load the environment:"
echo "   source .env"
echo ""
echo "4. Test the alert system:"
echo "   python monitor_with_alerts.py --threshold 60 --email"
echo ""
echo "5. Set up daily monitoring (optional):"
echo "   See SETUP_YOUR_ALERTS.md for cron job setup"
echo ""
echo "========================================================================"
echo ""
echo "For detailed instructions, see: SETUP_YOUR_ALERTS.md"
echo ""
