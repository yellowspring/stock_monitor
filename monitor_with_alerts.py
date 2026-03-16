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
from utils.cape_fetcher import CAPEFetcher
from utils.cfq_evaluator import CFQEvaluator
from utils.etf_evaluator import ETFEvaluator
from utils.cycle_detector import CycleDetector
from utils.crypto_scorer import CryptoScorer, RateRegime, RiskAppetite, NarrativeSentiment
from utils.stock_scanner import StockScanner
from utils.futures_fetcher import FuturesFetcher
from utils.crypto_trend import CryptoTrendAnalyzer


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
    parser.add_argument(
        '--scan-stocks',
        action='store_true',
        help='Run stock scanner to find top candidates (takes extra time)'
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

    # Filter to only use features that actually exist in the data
    # (some features may be missing if data fetch failed for certain symbols)
    available_features = [f for f in feature_names if f in data.columns]
    missing_features = [f for f in feature_names if f not in data.columns]

    if missing_features:
        print(f"Warning: {len(missing_features)} features missing due to data fetch issues:")
        print(f"  {', '.join(missing_features[:5])}{'...' if len(missing_features) > 5 else ''}")
        print("Continuing with available features...")

    # Clean data using only available features
    cols_to_check = available_features + ['crash_label']
    data_clean = data.dropna(subset=cols_to_check)

    # For missing features, fill with 0 (neutral value) so model can still run
    for feature in missing_features:
        data_clean[feature] = 0

    # Get latest data point
    latest_data = data_clean.iloc[-1:]
    latest_date = latest_data.index[0].strftime('%Y-%m-%d')

    # Extract values
    spy_price = latest_data['SPY'].values[0]
    qqq_price = latest_data['QQQ'].values[0]
    vix_level = latest_data['VIX'].values[0]

    # Extract daily returns (percentage change)
    spy_change = latest_data['spy_return'].values[0] * 100 if 'spy_return' in latest_data.columns else None
    qqq_change = latest_data['qqq_return'].values[0] * 100 if 'qqq_return' in latest_data.columns else None

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

        # Fetch CAPE data
        cape_analysis = None
        try:
            print("Fetching Shiller CAPE data...")
            cape_fetcher = CAPEFetcher()
            cape_analysis = cape_fetcher.analyze()
            if cape_analysis:
                print(f"  CAPE: {cape_analysis.current_cape:.1f} ({cape_analysis.cape_level})")
                print(f"  Historical Percentile: {cape_analysis.cape_percentile:.0f}%")
        except Exception as e:
            print(f"  Warning: Could not fetch CAPE data: {e}")

        # CFQ valuation for monitored stocks
        cfq_scores = []
        try:
            if monitored_stocks:
                print("Running CFQ valuation...")
                cfq_evaluator = CFQEvaluator()
                stocks_list = [(s.symbol, s.name) for s in monitored_stocks]
                cfq_scores = cfq_evaluator.evaluate_multiple(stocks_list)
                print(f"  Evaluated {len(cfq_scores)} stocks")

                # Show buy recommendations
                buy_stocks = [s for s in cfq_scores if s.recommendation == 'BUY']
                if buy_stocks:
                    print(f"  💡 {len(buy_stocks)} stocks rated BUY:")
                    for s in buy_stocks:
                        print(f"      {s.name}: {s.total_score}/15")
        except Exception as e:
            print(f"  Warning: Could not run CFQ valuation: {e}")

        # ETF-4Q evaluation - load cached results first, then supplement with config ETFs
        etf_scores = []
        try:
            # First try to load cached ETF scan results from nightly scan
            from pathlib import Path
            import json
            etf_cache_file = Path(__file__).parent / "cache" / "etf_scan_results.json"
            cached_etf_scores = []

            if etf_cache_file.exists():
                with open(etf_cache_file, 'r') as f:
                    cached_data = json.load(f)

                # Check if cache is fresh (within 24 hours)
                cached_time = datetime.fromisoformat(cached_data.get('timestamp', '2000-01-01'))
                if (datetime.now() - cached_time).total_seconds() < 24 * 3600:
                    cached_etf_scores = cached_data.get('results', [])
                    print(f"\n📂 Loaded {len(cached_etf_scores)} cached ETF scan results")

                    # Show top A+ ETFs from cache
                    top_cached = [e for e in cached_etf_scores if e.get('recommendation') == 'A+']
                    if top_cached:
                        print(f"  💡 {len(top_cached)} ETFs rated A+:")
                        for e in top_cached[:5]:
                            print(f"      {e['symbol']} ({e['name']}): {e['total_score']}/15 [{e.get('role_tag', '')}]")
                else:
                    print("\n📂 Cached ETF results expired, running fresh evaluation...")

            # If no cached results, run fresh evaluation on config ETFs
            if not cached_etf_scores:
                etf_symbols = config.get_etf_symbols()
                if etf_symbols:
                    print(f"Running ETF-4Q evaluation for {len(etf_symbols)} ETFs...")
                    cape_value = cape_analysis.current_cape if cape_analysis else None
                    etf_evaluator = ETFEvaluator(vix_level=vix_level, cape_level=cape_value)
                    etf_scores = etf_evaluator.evaluate_multiple(etf_symbols)
                    print(f"  Evaluated {len(etf_scores)} ETFs")

                    top_etfs = [s for s in etf_scores if s.recommendation == 'A+']
                    if top_etfs:
                        print(f"  💡 {len(top_etfs)} ETFs rated A+:")
                        for s in top_etfs:
                            print(f"      {s.symbol} ({s.name}): {s.total_score}/15 [{s.role_tag}]")
            else:
                # Convert cached results to ETFScore objects for the report
                cape_value = cape_analysis.current_cape if cape_analysis else None
                etf_evaluator = ETFEvaluator(vix_level=vix_level, cape_level=cape_value)

                # Re-evaluate config ETFs with full details for the detailed 4Q table
                etf_symbols = config.get_etf_symbols()
                if etf_symbols:
                    print(f"Running detailed ETF-4Q evaluation for {len(etf_symbols)} config ETFs...")
                    etf_scores = etf_evaluator.evaluate_multiple(etf_symbols)
                    print(f"  Evaluated {len(etf_scores)} ETFs with full 4Q scores")

        except Exception as e:
            print(f"  Warning: Could not run ETF evaluation: {e}")

        # Run cycle detection
        cycle_state = None
        try:
            print("\n📊 Running Market Cycle Analysis...")
            cycle_detector = CycleDetector()
            cycle_state = cycle_detector.detect_cycles()
            print(f"  Risk Cycle: {cycle_state.risk_regime.upper()}")
            print(f"  Rate Cycle: {cycle_state.rate_regime.upper()}")
            print(f"  AI Cycle: {cycle_state.ai_regime.upper()}")
            print("  Role Tilts:")
            for role, suggestion in cycle_state.role_suggestions.items():
                tilt = cycle_state.role_tilts.get(role, 0)
                print(f"    {role}: {suggestion} ({tilt:+d})")
        except Exception as e:
            print(f"  Warning: Could not run cycle detection: {e}")

        # Run crypto scoring
        crypto_scores = []
        try:
            print("\n₿ Running Crypto Entry Scoring...")
            crypto_scorer = CryptoScorer()

            # Map cycle state to rate/risk regimes
            rate_regime = RateRegime.PAUSE
            risk_appetite = RiskAppetite.NEUTRAL
            if cycle_state:
                if cycle_state.rate_regime == 'ease':
                    rate_regime = RateRegime.EASING
                elif cycle_state.rate_regime == 'tight':
                    rate_regime = RateRegime.TIGHTENING

                if cycle_state.risk_regime == 'risk_off':
                    risk_appetite = RiskAppetite.RISK_OFF
                elif cycle_state.risk_regime == 'risk_on':
                    risk_appetite = RiskAppetite.RISK_ON

            # Score BTC and ETH
            for asset in ['BTC', 'ETH']:
                score = crypto_scorer.score_asset(
                    asset=asset,
                    rate_regime=rate_regime,
                    risk_appetite=risk_appetite,
                    narrative=NarrativeSentiment.NEUTRAL,
                )
                crypto_scores.append(score)
                print(f"  {asset}: {score.score:.0f}/100 ({score.recommendation}) [Data: {score.chain_data_source}]")
        except Exception as e:
            print(f"  Warning: Could not run crypto scoring: {e}")

        # Run crypto trend analysis
        crypto_trends = []
        try:
            print("\n📈 Running Crypto Trend Analysis...")
            trend_analyzer = CryptoTrendAnalyzer()
            crypto_trends = trend_analyzer.analyze_all()
            for t in crypto_trends:
                arrow = {'STRONG_BULL': '⬆️⬆️', 'BULL': '⬆️', 'NEUTRAL': '➡️',
                         'BEAR': '⬇️', 'STRONG_BEAR': '⬇️⬇️'}.get(t.overall_trend, '➡️')
                print(f"  {t.name}: {arrow} {t.overall_trend} (Score: {t.trend_score:+d})")
        except Exception as e:
            print(f"  Warning: Could not run crypto trend analysis: {e}")

        # Run stock scanner or load cached results
        stock_scan_results = []
        if args.scan_stocks:
            # Run live scanner (slow, use only when explicitly requested)
            try:
                print("\n🔍 Running Stock Scanner...")
                scanner = StockScanner()  # Uses default universe
                stock_scan_results = scanner.scan_all(top_n=10, min_score=50, max_workers=3)
                print(f"  Found {len(stock_scan_results)} candidates")
                for r in stock_scan_results[:5]:
                    print(f"    {r.symbol}: {r.score:.0f}/100 ({r.recommendation})")
            except Exception as e:
                print(f"  Warning: Could not run stock scanner: {e}")
        else:
            # Load cached results from nightly scan (fast)
            try:
                scanner = StockScanner(cache_hours=24)  # Accept results up to 24h old
                cached = scanner.load_cached_results()
                if cached:
                    stock_scan_results = cached  # List of dicts
                    print(f"\n📂 Loaded {len(cached)} cached stock scan results")
                    for r in cached[:3]:
                        print(f"    {r['symbol']}: {r['score']:.0f}/100 ({r['recommendation']})")
                else:
                    print("\n📂 No cached stock scan results available (run run_stock_scan.py to generate)")
            except Exception as e:
                print(f"  Warning: Could not load cached stock scan results: {e}")

        # Fetch futures premium/discount data
        futures_data = None
        try:
            print("\n📈 Fetching Futures Premium/Discount...")
            futures_fetcher = FuturesFetcher()
            futures_data = futures_fetcher.fetch_all_futures()
            if futures_data.sp500:
                sign = "+" if futures_data.sp500.premium_pct > 0 else ""
                print(f"  S&P 500 (ES): {sign}{futures_data.sp500.premium_pct:.2f}% ({futures_data.sp500.signal})")
            if futures_data.nasdaq:
                sign = "+" if futures_data.nasdaq.premium_pct > 0 else ""
                print(f"  Nasdaq-100 (NQ): {sign}{futures_data.nasdaq.premium_pct:.2f}% ({futures_data.nasdaq.signal})")
            print(f"  Overall: {futures_data.overall_signal}")
        except Exception as e:
            print(f"  Warning: Could not fetch futures data: {e}")

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
            spy_change=spy_change,
            qqq_change=qqq_change,
            stress_score=stress_score,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
            cfq_scores=cfq_scores,
            etf_scores=etf_scores,
            cape_analysis=cape_analysis,
            cycle_state=cycle_state,
            crypto_scores=crypto_scores,
            crypto_trends=crypto_trends,
            stock_scan_results=stock_scan_results,
            futures_data=futures_data,
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
