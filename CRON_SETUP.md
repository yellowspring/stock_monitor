# Automated Crash Monitoring - Cron Setup

## Schedule

Your crash probability monitor runs automatically **twice daily**:

- **10:00 AM** - Before market open
- **3:00 PM** - Before market close (4 PM ET)

**Days:** Monday through Friday (weekdays only)

## Email Recipients

Alerts are sent to:
- tao.zhang.1977@gmail.com
- gao.yuan.77@gmail.com

## Alert Threshold

Emails are sent **only when crash probability exceeds 60%** (EXTREME risk level)

## What Happens

1. **At 10 AM and 3 PM** (weekdays only):
   - Script fetches latest SPY, QQQ, VIX data
   - Model predicts crash probability
   - If probability > 60%, email alert is sent
   - Result is logged to `logs/alerts.log`

2. **Email Alert Contains**:
   - Current crash probability
   - Risk level (LOW, MODERATE, HIGH, EXTREME)
   - Current market prices (SPY, QQQ, VIX)
   - Recommended actions
   - Recent 5-day probability history

## Monitoring

### View Logs (Real-time)
```bash
tail -f /home/tom2zhang/workspace/proj_stock_monitor/logs/alerts.log
```

### View Recent Logs
```bash
tail -50 /home/tom2zhang/workspace/proj_stock_monitor/logs/alerts.log
```

### Check Today's Results
```bash
grep "$(date +%Y-%m-%d)" /home/tom2zhang/workspace/proj_stock_monitor/logs/alerts.log
```

## Manual Testing

### Test Email Alert (Force send)
```bash
cd /home/tom2zhang/workspace/proj_stock_monitor
./daily_check.sh
```

### Run with Different Threshold
```bash
cd /home/tom2zhang/workspace/proj_stock_monitor
export $(grep -v '^#' .env | xargs)
python monitor_with_alerts.py --threshold 20 --email
```

## Managing Cron Jobs

### View Current Cron Jobs
```bash
crontab -l
```

### Edit Cron Jobs
```bash
crontab -e
```

### Remove Cron Jobs
```bash
crontab -e
# Delete the two lines containing "daily_check.sh"
```

### Reinstall Cron Jobs
```bash
cd /home/tom2zhang/workspace/proj_stock_monitor
./setup_cron.sh
```

## Current Cron Schedule

```
0 10 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
0 15 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
```

**Format:** `minute hour day month weekday command`
- `0 10` = 10:00 AM
- `0 15` = 3:00 PM
- `1-5` = Monday through Friday

## Troubleshooting

### Cron Not Running?

1. **Check cron service is running:**
   ```bash
   systemctl status cron
   # or on some systems:
   systemctl status crond
   ```

2. **Check logs for errors:**
   ```bash
   grep CRON /var/log/syslog
   ```

3. **Verify script is executable:**
   ```bash
   ls -l /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
   # Should show: -rwxr-xr-x
   ```

### Emails Not Sending?

1. **Check .env configuration:**
   ```bash
   cat /home/tom2zhang/workspace/proj_stock_monitor/.env
   ```

2. **Test manually:**
   ```bash
   cd /home/tom2zhang/workspace/proj_stock_monitor
   ./daily_check.sh
   ```

3. **Check logs:**
   ```bash
   tail -50 /home/tom2zhang/workspace/proj_stock_monitor/logs/alerts.log
   ```

### Change Schedule

To run at different times, edit crontab:
```bash
crontab -e
```

Examples:
```
# 9 AM and 4 PM
0 9 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
0 16 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh

# Only 3 PM
0 15 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh

# Every hour from 9 AM to 4 PM
0 9-16 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh
```

## Files

- **[daily_check.sh](daily_check.sh)** - Main script that runs the monitor (activates venv automatically)
- **[.env](.env)** - Email configuration (passwords, recipients)
- **[logs/alerts.log](logs/alerts.log)** - Log of all checks and alerts
- **[setup_cron.sh](setup_cron.sh)** - Script to install/reinstall cron jobs

## Python Virtual Environment

The script automatically activates the Python virtual environment at:
```
/home/tom2zhang/workspace/proj_stock_monitor/venv/bin/activate
```

This ensures all required packages (pandas, yfinance, xgboost, etc.) are available when running via cron.

## Summary

✅ **Automated:** Runs twice daily at 10 AM and 3 PM
✅ **Weekdays only:** Monday through Friday
✅ **Email alerts:** Sent when probability > 60%
✅ **Logged:** All results saved to logs/alerts.log
✅ **Two recipients:** Both emails receive alerts

**You're all set!** The system will monitor crash risk automatically and alert you when needed.
