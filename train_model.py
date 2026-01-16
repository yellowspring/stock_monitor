#!/usr/bin/env python3
"""
Train Crash Probability Model with Calibration

Usage:
    python train_model.py --start 2005-01-01 --end 2025-01-01 --model xgboost

Steps:
    1. Fetch data (10+ years)
    2. Generate labels (future 20-day max drawdown >= 15%)
    3. Create features (100+ features)
    4. Train/Calibration/Test split (60/20/20)
    5. Train XGBoost/LightGBM
    6. Calibrate with Isotonic Regression
    7. Evaluate with Brier Score & Calibration Curve
    8. Save calibrated model
"""

import argparse
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

from data.data_fetcher import MarketDataFetcher
from data.label_generator import CrashLabelGenerator
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Train crash probability model")
    parser.add_argument('--start', type=str, default='2005-01-01', help='Start date')
    parser.add_argument('--end', type=str, default=None, help='End date (default: today)')
    parser.add_argument('--model', type=str, default='xgboost',
                       choices=['xgboost', 'lightgbm', 'random_forest'],
                       help='Model type')
    parser.add_argument('--threshold', type=float, default=-0.15,
                       help='Crash threshold (default: -15%)')
    parser.add_argument('--forward-days', type=int, default=20,
                       help='Forward looking days (default: 20)')
    parser.add_argument('--output', type=str, default='models/crash_model.joblib',
                       help='Output model path')

    args = parser.parse_args()

    end_date = args.end or datetime.now().strftime('%Y-%m-%d')

    print("=" * 70)
    print("CRASH PROBABILITY MODEL TRAINING")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Data range: {args.start} to {end_date}")
    print(f"  Model type: {args.model}")
    print(f"  Crash threshold: {args.threshold*100:.0f}%")
    print(f"  Forward days: {args.forward_days}")
    print(f"  Output: {args.output}")

    # Step 1: Fetch data
    print("\n" + "=" * 70)
    print("STEP 1: FETCHING DATA")
    print("=" * 70)

    fetcher = MarketDataFetcher(start_date=args.start, end_date=end_date)
    data = fetcher.fetch_data()
    print(f"Fetched {len(data)} trading days")

    # Step 2: Generate labels
    print("\n" + "=" * 70)
    print("STEP 2: GENERATING LABELS")
    print("=" * 70)

    label_gen = CrashLabelGenerator(
        crash_threshold=args.threshold,
        lookforward_days=args.forward_days
    )
    data = label_gen.generate_labels(data)

    stats = label_gen.get_label_statistics(data)
    print(f"Total days: {stats['total_days']}")
    print(f"Crash days: {stats['crash_days']} ({stats['crash_rate']*100:.2f}%)")
    print(f"Normal days: {stats['normal_days']}")

    # Step 3: Create features
    print("\n" + "=" * 70)
    print("STEP 3: CREATING FEATURES")
    print("=" * 70)

    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)
    feature_names = feature_engine.get_feature_names(data)
    print(f"Created {len(feature_names)} features")

    # Step 4: Prepare data with train/calibration/test split
    print("\n" + "=" * 70)
    print("STEP 4: PREPARING DATA (Train 60% / Calibration 20% / Test 20%)")
    print("=" * 70)

    # Remove NaN rows
    cols_to_check = feature_names + ['crash_label']
    df_clean = data.dropna(subset=cols_to_check)

    X = df_clean[feature_names].values
    y = df_clean['crash_label'].values
    dates = df_clean.index

    # Time series split: 60% train, 20% calibration, 20% test
    n = len(X)
    train_end = int(n * 0.6)
    cal_end = int(n * 0.8)

    X_train, y_train = X[:train_end], y[:train_end]
    X_cal, y_cal = X[train_end:cal_end], y[train_end:cal_end]
    X_test, y_test = X[cal_end:], y[cal_end:]

    train_dates = dates[:train_end]
    cal_dates = dates[train_end:cal_end]
    test_dates = dates[cal_end:]

    print(f"Training set: {len(X_train)} samples ({train_dates[0].strftime('%Y-%m-%d')} to {train_dates[-1].strftime('%Y-%m-%d')})")
    print(f"  Crash rate: {y_train.mean()*100:.2f}%")
    print(f"Calibration set: {len(X_cal)} samples ({cal_dates[0].strftime('%Y-%m-%d')} to {cal_dates[-1].strftime('%Y-%m-%d')})")
    print(f"  Crash rate: {y_cal.mean()*100:.2f}%")
    print(f"Test set: {len(X_test)} samples ({test_dates[0].strftime('%Y-%m-%d')} to {test_dates[-1].strftime('%Y-%m-%d')})")
    print(f"  Crash rate: {y_test.mean()*100:.2f}%")

    # Step 5: Train model
    print("\n" + "=" * 70)
    print("STEP 5: TRAINING MODEL")
    print("=" * 70)

    predictor = CrashPredictor(model_type=args.model)
    predictor.feature_names = feature_names

    # Scale features
    X_train_scaled = predictor.scaler.fit_transform(X_train)
    X_cal_scaled = predictor.scaler.transform(X_cal)
    X_test_scaled = predictor.scaler.transform(X_test)

    # Train
    train_metrics = predictor.train(X_train_scaled, y_train)

    # Step 6: Calibrate
    print("\n" + "=" * 70)
    print("STEP 6: PROBABILITY CALIBRATION (Isotonic Regression)")
    print("=" * 70)

    cal_metrics = predictor.calibrate(X_cal_scaled, y_cal)

    # Step 7: Evaluate on test set
    print("\n" + "=" * 70)
    print("STEP 7: EVALUATION ON TEST SET")
    print("=" * 70)

    test_metrics = predictor.evaluate_with_calibration(X_test_scaled, y_test)

    # Print calibration verification
    print("\n" + "-" * 50)
    print("CALIBRATION VERIFICATION (Test Set)")
    print("-" * 50)

    y_proba = predictor.predict_probability(X_test)

    # Bin probabilities and check actual rates
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    print(f"{'Predicted Range':^20} | {'Actual Rate':^15} | {'Count':^10}")
    print("-" * 50)

    for i in range(len(bins)-1):
        mask = (y_proba >= bins[i]) & (y_proba < bins[i+1])
        if mask.sum() > 0:
            actual_rate = y_test[mask].mean() * 100
            pred_range = f"{bins[i]*100:.0f}% - {bins[i+1]*100:.0f}%"
            print(f"{pred_range:^20} | {actual_rate:^13.1f}% | {mask.sum():^10}")

    # Step 8: Feature importance
    print("\n" + "=" * 70)
    print("STEP 8: TOP 20 FEATURES")
    print("=" * 70)

    top_features = predictor.get_top_features(20)
    if top_features is not None:
        for i, row in top_features.iterrows():
            print(f"  {row['feature']}: {row['importance']:.4f}")

    # Step 9: Save model
    print("\n" + "=" * 70)
    print("STEP 9: SAVING MODEL")
    print("=" * 70)

    # Create directory if needed
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    predictor.save_model(args.output)

    # Summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nModel: {args.output}")
    print(f"Test AUC: {test_metrics['test_auc']:.4f}")
    print(f"Brier Score: {test_metrics['brier_score']:.4f}")
    print(f"Calibration: {'Enabled' if predictor.is_calibrated else 'Disabled'}")

    print("\n" + "-" * 50)
    print("USAGE:")
    print("-" * 50)
    print("""
    from models.crash_predictor import CrashPredictor

    predictor = CrashPredictor()
    predictor.load_model('models/crash_model.joblib')

    # Get calibrated probability (0-100)
    probability = predictor.get_crash_probability_index(X_today)

    if probability >= 60:
        print("HIGH RISK - Consider reducing exposure")
    elif probability <= 25:
        print("LOW RISK - Normal conditions")
    else:
        print("MODERATE - Monitor closely")
    """)


if __name__ == '__main__':
    main()
