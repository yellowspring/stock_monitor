#!/usr/bin/env python3
"""
Quick example of using the Crash Probability Index system
"""
import sys
sys.path.append('src')

from data.data_fetcher import MarketDataFetcher
from data.label_generator import CrashLabelGenerator
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor
import warnings
warnings.filterwarnings('ignore')


def main():
    print("=" * 80)
    print("CRASH PROBABILITY INDEX - QUICK EXAMPLE")
    print("=" * 80)

    # Step 1: Fetch data
    print("\n[1/5] Fetching market data (SPY, QQQ, VIX)...")
    fetcher = MarketDataFetcher(start_date="2010-01-01", end_date="2023-12-31")
    data = fetcher.fetch_data()
    print(f"      Loaded {len(data)} trading days")

    # Step 2: Generate crash labels
    print("\n[2/5] Generating crash labels (≥15% drawdown in next 20 days)...")
    label_gen = CrashLabelGenerator(crash_threshold=-0.15, lookforward_days=20)
    data = label_gen.generate_labels(data)

    stats = label_gen.get_label_statistics(data)
    print(f"      Found {stats['crash_days']} crash days ({stats['crash_rate']*100:.2f}%)")
    print(f"      Identified {stats['num_crash_events']} crash events")

    # Step 3: Engineer features
    print("\n[3/5] Engineering features (6 categories)...")
    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)
    feature_names = feature_engine.get_feature_names(data)
    print(f"      Created {len(feature_names)} features")

    # Step 4: Train model
    print("\n[4/5] Training XGBoost model...")
    predictor = CrashPredictor(model_type='xgboost')

    X_train, X_test, y_train, y_test, train_dates, test_dates = predictor.prepare_data(
        data, feature_names, test_size=0.2
    )

    train_metrics = predictor.train(X_train, y_train)
    test_metrics = predictor.evaluate(X_test, y_test)

    # Step 5: Make predictions
    print("\n[5/5] Generating crash probabilities...")
    cols_to_check = feature_names + ['crash_label']
    data_clean = data.dropna(subset=cols_to_check)
    X_all = data_clean[feature_names].values
    crash_probabilities = predictor.get_crash_probability_index(X_all)
    data_clean['crash_probability'] = crash_probabilities

    # Show results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    # Recent predictions
    print("\nRecent 10-day crash probabilities:")
    recent = data_clean.tail(10)
    for idx, row in recent.iterrows():
        date_str = idx.strftime('%Y-%m-%d')
        prob = row['crash_probability']
        spy = row['SPY']
        qqq = row['QQQ']
        vix = row['VIX']

        risk_indicator = "⚠️ " if prob > 30 else "   "
        print(f"{risk_indicator}{date_str}: {prob:5.1f}  (SPY: ${spy:6.2f}, QQQ: ${qqq:6.2f}, VIX: {vix:5.2f})")

    # Latest prediction
    latest = data_clean.iloc[-1]
    latest_prob = latest['crash_probability']

    print("\n" + "=" * 80)
    print(f"LATEST CRASH PROBABILITY INDEX: {latest_prob:.1f}/100")
    print("=" * 80)

    if latest_prob < 20:
        print("Risk Level: LOW - Market conditions appear stable")
    elif latest_prob < 40:
        print("Risk Level: MODERATE - Elevated risk, monitor closely")
    elif latest_prob < 60:
        print("Risk Level: HIGH - High crash risk, consider defensive positioning")
    else:
        print("Risk Level: EXTREME - URGENT: Extreme crash risk detected")

    # Top features
    print("\n" + "=" * 80)
    print("TOP 10 MOST IMPORTANT FEATURES")
    print("=" * 80)
    top_features = predictor.get_top_features(10)
    for idx, row in top_features.iterrows():
        print(f"{idx+1:2d}. {row['feature']:30s} {row['importance']:.4f}")

    # Known crash events
    print("\n" + "=" * 80)
    print("DETECTION OF KNOWN CRASH EVENTS")
    print("=" * 80)

    crash_events = [
        ('2020-02-15', '2020-03-31', 'COVID-19 Crash'),
        ('2022-01-01', '2022-06-30', '2022 Bear Market'),
        ('2018-10-01', '2018-12-31', '2018 Q4 Selloff'),
    ]

    for start, end, name in crash_events:
        try:
            event_data = data_clean.loc[start:end]
            if len(event_data) > 0:
                avg_prob = event_data['crash_probability'].mean()
                max_prob = event_data['crash_probability'].max()
                days_high = (event_data['crash_probability'] > 30).sum()
                total_days = len(event_data)

                print(f"\n{name} ({start} to {end})")
                print(f"  Average probability: {avg_prob:5.1f}")
                print(f"  Maximum probability: {max_prob:5.1f}")
                print(f"  Days above 30 threshold: {days_high}/{total_days} ({days_high/total_days*100:.1f}%)")
        except:
            pass

    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("  - Run full pipeline: python main.py --mode all")
    print("  - Get current prediction: python main.py --mode predict")
    print("  - Run backtest: python main.py --mode backtest")
    print("  - Create visualizations: python main.py --mode visualize")


if __name__ == "__main__":
    main()
