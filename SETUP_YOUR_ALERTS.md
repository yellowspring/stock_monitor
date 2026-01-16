# Your Personal Alert Setup

## Email Addresses Configured
- tao.zhang.1977@gmail.com
- gao.yuan.77@gmail.com

---

## Step 1: Set Up Gmail App Password (5 minutes)

### For tao.zhang.1977@gmail.com:

1. **Enable 2-Factor Authentication**
   - Go to: https://myaccount.google.com/security
   - Click "2-Step Verification"
   - Follow the setup wizard

2. **Create App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: "Mail"
   - Select device: "Other (Custom name)"
   - Type: "Crash Monitor"
   - Click "Generate"
   - **Copy the 16-character password** (looks like: xxxx xxxx xxxx xxxx)

3. **Save the password** - you'll need it in Step 2

---

## Step 2: Configure Environment Variables

### Option A: Quick Setup (Temporary - for testing)

```bash
# Open terminal and run these commands:
export EMAIL_FROM="tao.zhang.1977@gmail.com"
export EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"  # Your app password from Step 1
export EMAIL_TO="tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com"
```

### Option B: Permanent Setup (Recommended)

```bash
# Add to your ~/.bashrc or ~/.zshrc file:
echo 'export EMAIL_FROM="tao.zhang.1977@gmail.com"' >> ~/.bashrc
echo 'export EMAIL_PASSWORD="xxxx-xxxx-xxxx-xxxx"' >> ~/.bashrc
echo 'export EMAIL_TO="tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com"' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

### Option C: Using .env File (Most Secure)

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env file
nano .env

# 3. Update these lines:
EMAIL_FROM=tao.zhang.1977@gmail.com
EMAIL_PASSWORD=your-app-password-here  # Paste your 16-char password
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com

# Save and exit (Ctrl+X, then Y, then Enter)

# 4. Load environment variables
source .env
```

---

## Step 3: Test Email Alerts (2 minutes)

```bash
# First, train the model if you haven't
python main.py --mode train

# Test the alert system
python monitor_with_alerts.py --threshold 60 --email
```

You should see:
```
✓ Email alert sent to tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com
```

Check both email inboxes for the test alert!

---

## Step 4: Set Up SMS Alerts (Optional)

### Why SMS?
- **Instant notifications** on your phone
- **Works anywhere** (no need for email app)
- **Backup channel** if email fails

### Cost:
- Free trial: $15 credit (~2000 SMS)
- After trial: ~$0.0075 per SMS (~$0.15/month for 20 alerts)

### Setup:

1. **Sign up for Twilio**
   - Go to: https://www.twilio.com/try-twilio
   - Sign up (free trial)
   - Verify your phone number

2. **Get Credentials**
   - From console: https://console.twilio.com/
   - Copy:
     - Account SID
     - Auth Token
   - Get a phone number (free with trial)

3. **Install Twilio SDK**
   ```bash
   pip install twilio
   ```

4. **Configure**
   ```bash
   export TWILIO_ACCOUNT_SID="AC..."
   export TWILIO_AUTH_TOKEN="your-token"
   export TWILIO_FROM="+12345678901"  # Your Twilio number
   export TWILIO_TO="+1YOUR-CELL"     # Your mobile number
   ```

5. **Test SMS**
   ```bash
   python monitor_with_alerts.py --threshold 60 --sms
   ```

---

## Step 5: Set Up Daily Automation

### Run automatically every weekday at 5 PM (after market close)

```bash
# Edit crontab
crontab -e

# Add this line (update the path to your project):
0 17 * * 1-5 cd /home/tom2zhang/workspace/proj_stock_monitor && export EMAIL_FROM="tao.zhang.1977@gmail.com" && export EMAIL_PASSWORD="xxxx-xxxx-xxxx-xxxx" && export EMAIL_TO="tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com" && python monitor_with_alerts.py --threshold 60 --email >> logs/alerts.log 2>&1

# Save and exit
```

Or create a simple wrapper script:

```bash
# Create daily_check.sh
cat > daily_check.sh << 'EOF'
#!/bin/bash
cd /home/tom2zhang/workspace/proj_stock_monitor
source .env  # Load your credentials
python monitor_with_alerts.py --threshold 60 --email
EOF

chmod +x daily_check.sh

# Test it
./daily_check.sh

# Add to crontab
crontab -e
# Add: 0 17 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
```

---

## Quick Reference

### Check Current Risk
```bash
python monitor_with_alerts.py --threshold 60 --email
```

### Check with Lower Threshold (More Sensitive)
```bash
python monitor_with_alerts.py --threshold 40 --email
```

### Check with SMS + Email
```bash
python monitor_with_alerts.py --threshold 60 --email --sms
```

### View Recent Predictions
```bash
python show_covid_predictions.py
```

---

## Troubleshooting

### "Authentication failed" error

**Solution:**
1. Make sure you're using App Password, not regular Gmail password
2. Check 2-Factor Authentication is enabled
3. Verify EMAIL_FROM and EMAIL_PASSWORD are set correctly

**Test variables:**
```bash
echo $EMAIL_FROM
echo $EMAIL_PASSWORD
echo $EMAIL_TO
```

### "No module named 'twilio'" (for SMS)

**Solution:**
```bash
pip install twilio
```

### Emails not arriving

**Check:**
1. Spam folder in both inboxes
2. Gmail "Less secure app access" settings
3. Try sending to one email first to test

### Cron job not working

**Solution:**
Add full paths and environment variables to crontab:
```bash
0 17 * * 1-5 /usr/bin/python3 /full/path/to/monitor_with_alerts.py --threshold 60 --email
```

---

## Email Alert Example

When triggered, you'll receive:

**Subject:**
```
🚨 CRASH ALERT: 75.5% Risk - EXTREME (HIGH)
```

**Preview:**
```
CRASH PROBABILITY ALERT
==================================================

Date: 2024-01-15
Crash Probability: 75.5/100
Risk Level: EXTREME
Urgency: HIGH

SPY: $450.25
QQQ: $385.50
VIX: 32.50

⚠️  HIGH CRASH RISK ⚠️

RECOMMENDED ACTIONS:
• Reduce equity exposure
• Tighten stop losses
• Consider hedging
...
```

Both **tao.zhang.1977@gmail.com** and **gao.yuan.77@gmail.com** will receive this!

---

## Next Steps

1. ✅ Set up Gmail App Password
2. ✅ Configure environment variables
3. ✅ Test email alerts
4. ⏺️ (Optional) Set up SMS
5. ⏺️ (Optional) Set up daily automation

**Ready to protect your portfolio!** 🛡️
