#!/bin/bash
# Setup cron jobs for crash monitoring and stock scanning

echo "Setting up cron jobs for crash probability monitoring..."
echo ""
echo "This will run:"
echo "  - 1:00 AM daily: Stock scanner (scans and caches results)"
echo "  - 10:00 AM weekdays: Crash monitor with daily report"
echo "  - 3:00 PM weekdays: Crash monitor check"
echo "  - 9:00 PM weekends: Weekend report"
echo ""
echo "Emails will be sent to:"
echo "  - tao.zhang.1977@gmail.com"
echo "  - gao.yuan.77@gmail.com"
echo ""
echo "Stock scan results are cached for the daily report"
echo ""

# Get the current crontab
crontab -l > /tmp/current_cron 2>/dev/null || touch /tmp/current_cron

# Remove any existing crash monitor and stock scan entries
grep -v "proj_stock_monitor/daily_check.sh" /tmp/current_cron | grep -v "proj_stock_monitor/run_stock_scan.sh" > /tmp/new_cron

# Add new cron jobs
# 1 AM daily - Stock scanner (runs every day to cache results)
echo "0 1 * * * /home/tom2zhang/workspace/proj_stock_monitor/run_stock_scan.sh" >> /tmp/new_cron

# 10 AM every weekday (Monday-Friday) - Crash monitor with daily report
echo "0 10 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh" >> /tmp/new_cron

# 3 PM every weekday (Monday-Friday) - Crash monitor check
echo "0 15 * * 1-5 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh" >> /tmp/new_cron

# 9 PM every weekend (Saturday and Sunday) - Weekend report
echo "0 21 * * 0,6 /home/tom2zhang/workspace/proj_stock_monitor/daily_check.sh" >> /tmp/new_cron

# Install the new crontab
crontab /tmp/new_cron

# Clean up
rm /tmp/current_cron /tmp/new_cron

echo "✓ Cron jobs installed successfully!"
echo ""
echo "To verify, run: crontab -l"
echo ""
echo "To view logs: tail -f /home/tom2zhang/workspace/proj_stock_monitor/logs/alerts.log"
echo ""
echo "To remove cron jobs: crontab -e (then delete the lines)"
echo ""
