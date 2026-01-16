#!/usr/bin/env python3
"""
Crash Probability Monitor with Alerts

This script monitors crash probability and sends alerts when it exceeds a threshold.
Run this daily (e.g., via cron) to get automatic notifications.

Usage:
    python monitor_with_alerts.py --threshold 60 --email --sms
"""

import argparse
import sys
import os
from datetime import datetime

# Load .env file for environment variables (works in cron)
from pathlib import Path
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Add src to path
sys.path.append('src')

from data.data_fetcher import MarketDataFetcher
from data.label_generator import CrashLabelGenerator
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor
from utils.alerting import CrashAlerter
from utils.config_loader import ConfigLoader
from utils.stock_risk_calculator import StockRiskCalculator


def main():
    parser = argparse.ArgumentParser(
        description="Monitor crash probability and send alerts"
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=60.0,
        help='Alert threshold (0-100, default: 60)'
    )
    parser.add_argument(
        '--email',
        action='store_true',
        help='Enable email alerts'
    )
    parser.add_argument(
        '--sms',
        action='store_true',
        help='Enable SMS alerts (requires Twilio)'
    )
    parser.add_argument(
        '--model-path',
        type=str,
        default='models/crash_predictor.pkl',
        help='Path to trained model'
    )
    parser.add_argument(
        '--daily-report',
        action='store_true',
        help='Send daily report email (regardless of alert threshold)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("CRASH PROBABILITY MONITOR WITH ALERTS")
    print("=" * 80)
    print(f"Alert threshold: {args.threshold}%")
    print(f"Email alerts: {'ENABLED' if args.email else 'DISABLED'}")
    print(f"SMS alerts: {'ENABLED' if args.sms else 'DISABLED'}")
    print(f"Daily report: {'ENABLED' if args.daily_report else 'DISABLED'}")
    print()

    # Check if model exists
    if not os.path.exists(args.model_path):
        print(f"✗ Model not found at {args.model_path}")
        print("  Run: python main.py --mode train")
        sys.exit(1)

    # Initialize components
    print("Loading model and fetching data...")

    # Load model
    predictor = CrashPredictor()
    predictor.load_model(args.model_path)

    # Fetch latest data
    fetcher = MarketDataFetcher(start_date="2020-01-01")
    data = fetcher.fetch_data()

    # Generate labels and features
    label_gen = CrashLabelGenerator()
    data = label_gen.generate_labels(data)

    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)

    # Get feature names
    feature_names = predictor.feature_names

    # Clean data
    cols_to_check = feature_names + ['crash_label']
    data_clean = data.dropna(subset=cols_to_check)

    # Get latest data point
    latest_data = data_clean.iloc[-1:]
    latest_date = latest_data.index[0].strftime('%Y-%m-%d')

    # Extract values
    spy_price = latest_data['SPY'].values[0]
    qqq_price = latest_data['QQQ'].values[0]
    vix_level = latest_data['VIX'].values[0]

    # Extract additional indicators for daily report
    stress_score = latest_data['stress_composite'].values[0] if 'stress_composite' in latest_data.columns else None
    stress_acceleration = latest_data['stress_acceleration_5d'].values[0] if 'stress_acceleration_5d' in latest_data.columns else None
    false_calm = latest_data['false_calm_detector'].values[0] == 1 if 'false_calm_detector' in latest_data.columns else False
    skew_level = latest_data['SKEW'].values[0] if 'SKEW' in latest_data.columns else None
    credit_spread_change = latest_data['credit_spread_change_5d'].values[0] if 'credit_spread_change_5d' in latest_data.columns else None

    # Predict crash probability
    X_latest = latest_data[feature_names].values
    crash_prob = predictor.get_crash_probability_index(X_latest)[0]

    # Display current status
    print()
    print("=" * 80)
    print("CURRENT MARKET STATUS")
    print("=" * 80)
    print(f"Date: {latest_date}")
    print(f"SPY: ${spy_price:.2f}")
    print(f"QQQ: ${qqq_price:.2f}")
    print(f"VIX: {vix_level:.2f}")
    print()
    print(f"CRASH PROBABILITY INDEX: {crash_prob:.1f}/100")
    print("=" * 80)

    # Determine risk level
    if crash_prob < 20:
        risk_level = "LOW"
        status_icon = "✓"
    elif crash_prob < 40:
        risk_level = "MODERATE"
        status_icon = "⚠️"
    elif crash_prob < 60:
        risk_level = "HIGH"
        status_icon = "⚠️"
    else:
        risk_level = "EXTREME"
        status_icon = "🚨"

    print(f"{status_icon} Risk Level: {risk_level}")
    print()

    # Check if alert should be sent
    if crash_prob >= args.threshold:
        print(f"🚨 ALERT: Crash probability ({crash_prob:.1f}%) exceeds threshold ({args.threshold}%)")
        print()

        # Initialize alerter
        alerter = CrashAlerter(
            alert_threshold=args.threshold,
            enable_email=args.email,
            enable_sms=args.sms
        )

        # Send alert
        alert_sent = alerter.check_and_alert(
            crash_probability=crash_prob,
            spy_price=spy_price,
            qqq_price=qqq_price,
            vix_level=vix_level,
            date=latest_date
        )

        if alert_sent:
            print("✓ Alert sent successfully")
        else:
            if not args.email and not args.sms:
                print("⚠️  No alert methods enabled. Use --email or --sms flags.")
            else:
                print("⚠️  Alert configured but not sent. Check configuration.")
                print()
                print("Email configuration:")
                print(f"  EMAIL_FROM: {'✓ Set' if os.getenv('EMAIL_FROM') else '✗ Not set'}")
                print(f"  EMAIL_PASSWORD: {'✓ Set' if os.getenv('EMAIL_PASSWORD') else '✗ Not set'}")
                print(f"  EMAIL_TO: {'✓ Set' if os.getenv('EMAIL_TO') else '✗ Not set'}")
                if args.sms:
                    print()
                    print("SMS configuration:")
                    print(f"  TWILIO_ACCOUNT_SID: {'✓ Set' if os.getenv('TWILIO_ACCOUNT_SID') else '✗ Not set'}")
                    print(f"  TWILIO_AUTH_TOKEN: {'✓ Set' if os.getenv('TWILIO_AUTH_TOKEN') else '✗ Not set'}")
    else:
        print(f"✓ No alert needed. Crash probability ({crash_prob:.1f}%) below threshold ({args.threshold}%)")

    # Show recent history
    print()
    print("Recent 5-day history:")
    recent_data = data_clean.tail(5)
    X_recent = recent_data[feature_names].values
    recent_probs = predictor.get_crash_probability_index(X_recent)

    recent_history = []
    for date, prob in zip(recent_data.index, recent_probs):
        icon = "🚨" if prob >= args.threshold else "  "
        print(f"  {icon} {date.strftime('%Y-%m-%d')}: {prob:5.1f}%")
        recent_history.append((date.strftime('%Y-%m-%d'), prob))

    # Send daily report if enabled
    if args.daily_report:
        print()
        print("=" * 80)
        print("SENDING DAILY REPORT")
        print("=" * 80)

        # Load stock configuration and calculate individual stock risks
        stock_risks = []
        try:
            config = ConfigLoader()
            monitored_stocks = config.get_monitored_stocks()
            thresholds = config.get_thresholds()

            if monitored_stocks:
                print(f"Calculating risk for {len(monitored_stocks)} monitored stocks...")
                calculator = StockRiskCalculator(thresholds={
                    'high_risk': thresholds.high_risk,
                    'moderate_risk': thresholds.moderate_risk,
                    'low_risk': thresholds.low_risk
                })

                stocks_list = [(s.symbol, s.name) for s in monitored_stocks]
                stock_risks = calculator.calculate_multiple_stocks(stocks_list, crash_prob)
                print(f"  Calculated risk for {len(stock_risks)} stocks")

                # Display high-risk stocks
                high_risk = [r for r in stock_risks if r.risk_level == 'HIGH']
                if high_risk:
                    print(f"  ⚠️  {len(high_risk)} stocks at HIGH risk:")
                    for r in high_risk:
                        print(f"      {r.name} ({r.symbol}): {r.crash_probability:.1f}%")
        except Exception as e:
            print(f"  Warning: Could not calculate stock risks: {e}")

        alerter = CrashAlerter(
            alert_threshold=args.threshold,
            enable_email=True,
            enable_sms=False
        )

        report_sent = alerter.send_daily_report(
            crash_probability=crash_prob,
            spy_price=spy_price,
            qqq_price=qqq_price,
            vix_level=vix_level,
            stress_score=stress_score,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
            date=latest_date
        )

        if report_sent:
            print("✓ Daily report sent successfully")
        else:
            print("✗ Failed to send daily report. Check email configuration:")
            print(f"  EMAIL_FROM: {'✓ Set' if os.getenv('EMAIL_FROM') else '✗ Not set'}")
            print(f"  EMAIL_PASSWORD: {'✓ Set' if os.getenv('EMAIL_PASSWORD') else '✗ Not set'}")
            print(f"  EMAIL_TO: {'✓ Set' if os.getenv('EMAIL_TO') else '✗ Not set'}")

    print()
    print("=" * 80)
    print("MONITOR COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
