# Alert Setup Guide

This guide shows you how to set up email and SMS alerts for crash probability warnings.

## Overview

The alerting system can notify you via:
- **Email** (using SMTP - works with Gmail, Outlook, etc.)
- **SMS** (using Twilio - optional, requires paid account)

When crash probability exceeds your threshold (e.g., 60%), you'll receive automatic notifications.

---

## Email Alerts Setup

### Step 1: Configure Email Settings

You need to set environment variables for your email account.

#### For Gmail:

1. **Enable 2-Factor Authentication** on your Google account
2. **Create an App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "Crash Monitor"
   - Copy the 16-character password

3. **Set environment variables**:

```bash
# Add to ~/.bashrc or ~/.zshrc for permanent configuration
export EMAIL_FROM="your-email@gmail.com"
export EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"  # App password from step 2
export EMAIL_TO="recipient@email.com"        # Where to send alerts

# Optional: Custom SMTP server (defaults to Gmail)
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
```

4. **Reload your shell**:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

#### For Other Email Providers:

**Outlook/Hotmail:**
```bash
export SMTP_SERVER="smtp-mail.outlook.com"
export SMTP_PORT="587"
export EMAIL_FROM="your-email@outlook.com"
export EMAIL_PASSWORD="your-password"
export EMAIL_TO="recipient@email.com"
```

**Yahoo:**
```bash
export SMTP_SERVER="smtp.mail.yahoo.com"
export SMTP_PORT="587"
export EMAIL_FROM="your-email@yahoo.com"
export EMAIL_PASSWORD="your-app-password"  # Get from Yahoo account settings
export EMAIL_TO="recipient@email.com"
```

### Step 2: Test Email Alerts

```bash
# Test the alerting system
python src/utils/alerting.py

# Run monitor with email alerts (60% threshold)
python monitor_with_alerts.py --threshold 60 --email
```

---

## SMS Alerts Setup (Optional)

SMS alerts use Twilio, a paid service (~$1/month + $0.0075 per SMS).

### Step 1: Create Twilio Account

1. Go to: https://www.twilio.com/try-twilio
2. Sign up for free trial (includes $15 credit)
3. Get a Twilio phone number (free with trial)

### Step 2: Get Twilio Credentials

1. From Twilio Console: https://console.twilio.com/
2. Copy your:
   - **Account SID**
   - **Auth Token**
   - **Twilio Phone Number**

### Step 3: Install Twilio SDK

```bash
pip install twilio
```

### Step 4: Configure Twilio Environment Variables

```bash
export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TWILIO_AUTH_TOKEN="your-auth-token"
export TWILIO_FROM="+12345678901"  # Your Twilio number
export TWILIO_TO="+10987654321"    # Your mobile number
```

### Step 5: Test SMS Alerts

```bash
# Run monitor with SMS alerts
python monitor_with_alerts.py --threshold 60 --sms

# Or both email and SMS
python monitor_with_alerts.py --threshold 60 --email --sms
```

---

## Usage Examples

### Basic Email Alert

```bash
# Send email alert if probability >= 60%
python monitor_with_alerts.py --threshold 60 --email
```

### Email + SMS Alerts

```bash
# Send both email and SMS if probability >= 70%
python monitor_with_alerts.py --threshold 70 --email --sms
```

### Custom Threshold

```bash
# Lower threshold for early warning (40%)
python monitor_with_alerts.py --threshold 40 --email
```

### Programmatic Usage

```python
from src.utils.alerting import CrashAlerter

# Initialize alerter
alerter = CrashAlerter(
    alert_threshold=60.0,
    enable_email=True,
    enable_sms=False
)

# Check and send alert if needed
alert_sent = alerter.check_and_alert(
    crash_probability=75.5,
    spy_price=450.25,
    qqq_price=385.50,
    vix_level=32.5,
    date="2024-01-15"
)

if alert_sent:
    print("Alert sent!")
```

---

## Automated Daily Monitoring

### Option 1: Cron Job (Linux/Mac)

Run the monitor daily at 5 PM (after market close):

```bash
# Edit crontab
crontab -e

# Add this line:
0 17 * * 1-5 cd /path/to/proj_stock_monitor && python monitor_with_alerts.py --threshold 60 --email >> logs/monitor.log 2>&1
```

This runs:
- At 5:00 PM (17:00)
- Monday through Friday (1-5)
- Logs output to logs/monitor.log

### Option 2: Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 5:00 PM
4. Action: Start a program
   - Program: `python`
   - Arguments: `monitor_with_alerts.py --threshold 60 --email`
   - Start in: `C:\path\to\proj_stock_monitor`

### Option 3: Python Script with Schedule

Create `daily_monitor.py`:

```python
import schedule
import time
import subprocess

def run_monitor():
    subprocess.run([
        "python", "monitor_with_alerts.py",
        "--threshold", "60",
        "--email"
    ])

# Run daily at 5 PM
schedule.every().day.at("17:00").do(run_monitor)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run in background:
```bash
nohup python daily_monitor.py &
```

---

## Alert Message Example

When triggered, you'll receive:

**Subject:**
```
🚨 CRASH ALERT: 75.5% Risk - EXTREME (HIGH)
```

**Body:**
```
CRASH PROBABILITY ALERT
==================================================

Date: 2024-01-15
Crash Probability: 75.5/100
Risk Level: EXTREME
Urgency: HIGH

==================================================
MARKET DATA
==================================================

SPY: $450.25
QQQ: $385.50
VIX: 32.50

==================================================
INTERPRETATION
==================================================

The model estimates a 75.5% probability that SPY or QQQ
will experience a ≥15% drawdown within the next 20 trading days.

⚠️  HIGH CRASH RISK ⚠️

Elevated crash probability detected. Multiple risk indicators
are showing stress.

RECOMMENDED ACTIONS:
• Reduce equity exposure
• Tighten stop losses
• Consider hedging
• Review portfolio risk
• Monitor daily

==================================================

This alert was generated by the Crash Probability Index system.
Threshold: 60.0%

⚠️  DISCLAIMER: This is not financial advice. Always do your own
research and consult with qualified financial professionals.
```

---

## Troubleshooting

### Email Not Sending

**Problem:** "Authentication failed" error

**Solutions:**
1. Gmail: Make sure you're using an App Password, not your regular password
2. Enable "Less secure app access" (if not using 2FA)
3. Check SMTP server and port settings
4. Verify EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO are set correctly

**Test connection:**
```bash
python -c "
import os
print('EMAIL_FROM:', os.getenv('EMAIL_FROM'))
print('EMAIL_PASSWORD:', '***' if os.getenv('EMAIL_PASSWORD') else 'NOT SET')
print('EMAIL_TO:', os.getenv('EMAIL_TO'))
"
```

### SMS Not Sending

**Problem:** "Twilio not installed" or "Invalid credentials"

**Solutions:**
1. Install Twilio: `pip install twilio`
2. Verify credentials in Twilio Console
3. Check phone number format: must include country code (+1 for US)
4. Trial accounts can only send to verified numbers

### Environment Variables Not Persisting

**Problem:** Variables work in terminal but not in cron

**Solution:** Add variables to crontab:
```bash
0 17 * * 1-5 EMAIL_FROM=your@email.com EMAIL_PASSWORD=xxx EMAIL_TO=recipient@email.com cd /path/to/proj_stock_monitor && python monitor_with_alerts.py --threshold 60 --email
```

Or create `.env` file and load it:
```bash
# .env file
EMAIL_FROM=your@email.com
EMAIL_PASSWORD=xxx
EMAIL_TO=recipient@email.com
```

---

## Security Best Practices

1. **Never commit credentials to Git**
   - Add `.env` to `.gitignore`
   - Use environment variables only

2. **Use App Passwords**
   - Don't use your main email password
   - Create app-specific passwords

3. **Restrict Permissions**
   - Only grant necessary access
   - Regularly rotate credentials

4. **Monitor Usage**
   - Check email/SMS logs
   - Review Twilio usage dashboard

---

## Cost Estimate

**Email Alerts:**
- ✓ **FREE** (using Gmail, Outlook, Yahoo, etc.)

**SMS Alerts (Twilio):**
- Trial: $15 free credit
- After trial: ~$1/month + $0.0075 per SMS
- Example: 20 alerts/month = $1 + $0.15 = $1.15/month

---

## Next Steps

1. Configure email (5 minutes)
2. Test alerts: `python monitor_with_alerts.py --threshold 60 --email`
3. Set up daily automation (cron job)
4. (Optional) Add SMS alerts for critical warnings

**Ready to monitor!** 🚀
