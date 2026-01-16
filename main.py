#!/usr/bin/env python3
"""
Crash Probability Index - Main Script

A systematic crash prediction model that predicts the probability (0-100)
of a ≥15% drawdown in SPY or QQQ within the next 20 trading days.

Usage:
    python main.py --mode train          # Train new model
    python main.py --mode predict        # Get current crash probability
    python main.py --mode backtest       # Run backtest on historical data
    python main.py --mode visualize      # Create visualizations
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add src to path
sys.path.append('src')

from data.data_fetcher import MarketDataFetcher
from data.label_generator import CrashLabelGenerator
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor
from utils.backtester import CrashBacktester
from utils.visualizer import CrashVisualizer


class CrashProbabilitySystem:
    """Main system for crash probability prediction"""

    def __init__(
        self,
        start_date: str = "2005-01-01",
        model_type: str = "xgboost",
        crash_threshold: float = -0.15,
        lookforward_days: int = 20
    ):
        """
        Initialize crash probability system

        Args:
            start_date: Start date for historical data
            model_type: Type of ML model to use
            crash_threshold: Threshold for defining crash (default: -15%)
            lookforward_days: Days to look forward for crash (default: 20)
        """
        self.start_date = start_date
        self.model_type = model_type
        self.crash_threshold = crash_threshold
        self.lookforward_days = lookforward_days

        self.data_fetcher = MarketDataFetcher(start_date=start_date)
        self.label_generator = CrashLabelGenerator(
            crash_threshold=crash_threshold,
            lookforward_days=lookforward_days
        )
        self.feature_engine = CrashFeatureEngine()
        self.predictor = CrashPredictor(model_type=model_type)
        self.backtester = CrashBacktester()
        self.visualizer = CrashVisualizer()

        self.data = None
        self.feature_names = None

    def load_and_prepare_data(self):
        """Load and prepare all data"""
        print("=" * 80)
        print("LOADING AND PREPARING DATA")
        print("=" * 80)

        # Fetch market data
        print("\n1. Fetching market data (SPY, QQQ, VIX)...")
        self.data = self.data_fetcher.fetch_data()

        # Generate crash labels
        print("\n2. Generating crash labels...")
        self.data = self.label_generator.generate_labels(self.data)

        # Get label statistics
        stats = self.label_generator.get_label_statistics(self.data)
        print(f"   Total days: {stats['total_days']}")
        print(f"   Crash days: {stats['crash_days']} ({stats['crash_rate']*100:.2f}%)")
        print(f"   Normal days: {stats['normal_days']}")
        print(f"   Crash events: {stats['num_crash_events']}")

        # Create features
        print("\n3. Engineering features...")
        self.data = self.feature_engine.create_features(self.data)
        self.feature_names = self.feature_engine.get_feature_names(self.data)
        print(f"   Created {len(self.feature_names)} features")

        print("\nData preparation complete!")
        return self.data

    def train_model(self, test_size: float = 0.2):
        """Train the crash prediction model"""
        print("\n" + "=" * 80)
        print("TRAINING CRASH PREDICTION MODEL")
        print("=" * 80)

        if self.data is None:
            self.load_and_prepare_data()

        # Prepare data
        X_train, X_test, y_train, y_test, train_dates, test_dates = self.predictor.prepare_data(
            self.data, self.feature_names, test_size=test_size
        )

        # Train
        train_metrics = self.predictor.train(X_train, y_train)

        # Evaluate
        test_metrics = self.predictor.evaluate(X_test, y_test)

        # Show top features
        print("\nTop 15 Most Important Features:")
        print(self.predictor.get_top_features(15))

        # Save model
        model_path = "models/crash_predictor.pkl"
        os.makedirs("models", exist_ok=True)
        self.predictor.save_model(model_path)

        return train_metrics, test_metrics

    def predict_current_crash_probability(self):
        """Get current crash probability"""
        print("\n" + "=" * 80)
        print("CURRENT CRASH PROBABILITY INDEX")
        print("=" * 80)

        # Load model if not trained
        model_path = "models/crash_predictor.pkl"
        if os.path.exists(model_path):
            self.predictor.load_model(model_path)
            print(f"Loaded model from {model_path}")
        else:
            print("No trained model found. Training new model...")
            self.train_model()

        # Get latest data
        if self.data is None:
            self.load_and_prepare_data()

        # Get most recent data point
        cols_to_check = self.feature_names + ['crash_label']
        data_clean = self.data.dropna(subset=cols_to_check)
        latest_data = data_clean.iloc[-1:]

        X_latest = latest_data[self.feature_names].values
        crash_prob = self.predictor.get_crash_probability_index(X_latest)[0]

        # Get recent history
        recent_data = data_clean.tail(10)
        X_recent = recent_data[self.feature_names].values
        recent_probs = self.predictor.get_crash_probability_index(X_recent)

        # Display results
        print(f"\nDate: {latest_data.index[0].strftime('%Y-%m-%d')}")
        print(f"SPY: ${latest_data['SPY'].values[0]:.2f}")
        print(f"QQQ: ${latest_data['QQQ'].values[0]:.2f}")
        print(f"VIX: {latest_data['VIX'].values[0]:.2f}")
        print(f"\n{'='*40}")
        print(f"CRASH PROBABILITY INDEX: {crash_prob:.1f}/100")
        print(f"{'='*40}")

        # Interpretation
        if crash_prob < 20:
            risk_level = "LOW"
            interpretation = "Market conditions appear stable"
        elif crash_prob < 40:
            risk_level = "MODERATE"
            interpretation = "Elevated risk - monitor closely"
        elif crash_prob < 60:
            risk_level = "HIGH"
            interpretation = "High crash risk - consider defensive positioning"
        else:
            risk_level = "EXTREME"
            interpretation = "EXTREME crash risk - urgent action recommended"

        print(f"\nRisk Level: {risk_level}")
        print(f"Interpretation: {interpretation}")

        print(f"\nRecent 10-day probability history:")
        for date, prob in zip(recent_data.index, recent_probs):
            print(f"  {date.strftime('%Y-%m-%d')}: {prob:.1f}")

        return crash_prob

    def run_backtest(self, threshold: float = 30.0):
        """Run comprehensive backtest"""
        print("\n" + "=" * 80)
        print("RUNNING BACKTEST")
        print("=" * 80)

        # Load model
        model_path = "models/crash_predictor.pkl"
        if os.path.exists(model_path):
            self.predictor.load_model(model_path)
        else:
            print("Training model first...")
            self.train_model()

        if self.data is None:
            self.load_and_prepare_data()

        # Get predictions for all data
        cols_to_check = self.feature_names + ['crash_label']
        data_clean = self.data.dropna(subset=cols_to_check)
        X_all = data_clean[self.feature_names].values
        data_clean['crash_probability'] = self.predictor.get_crash_probability_index(X_all)

        # Generate report
        report = self.backtester.generate_backtest_report(
            data_clean,
            probability_col='crash_probability',
            threshold=threshold
        )

        print(report)

        # Save report
        os.makedirs("reports", exist_ok=True)
        report_path = f"reports/backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"\nReport saved to {report_path}")

        return data_clean

    def create_visualizations(self):
        """Create all visualizations"""
        print("\n" + "=" * 80)
        print("CREATING VISUALIZATIONS")
        print("=" * 80)

        # Load model and data
        model_path = "models/crash_predictor.pkl"
        if os.path.exists(model_path):
            self.predictor.load_model(model_path)
        else:
            print("Training model first...")
            self.train_model()

        if self.data is None:
            self.load_and_prepare_data()

        # Get predictions
        cols_to_check = self.feature_names + ['crash_label']
        data_clean = self.data.dropna(subset=cols_to_check)
        X_all = data_clean[self.feature_names].values
        data_clean['crash_probability'] = self.predictor.get_crash_probability_index(X_all)

        os.makedirs("visualizations", exist_ok=True)

        # Timeline plot
        print("\n1. Creating timeline plot...")
        self.visualizer.plot_crash_probability_timeline(
            data_clean,
            save_path="visualizations/crash_probability_timeline.png"
        )

        # Feature importance
        print("2. Creating feature importance plot...")
        self.visualizer.plot_feature_importance(
            self.predictor.get_top_features(20),
            save_path="visualizations/feature_importance.png"
        )

        # Crash events
        print("3. Creating crash events plot...")
        self.visualizer.plot_crash_events(
            data_clean,
            self.backtester.known_crashes,
            save_path="visualizations/crash_events.png"
        )

        print("\nAll visualizations saved to visualizations/ directory")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Crash Probability Index - Systematic Market Crash Prediction"
    )
    parser.add_argument(
        '--mode',
        type=str,
        required=True,
        choices=['train', 'predict', 'backtest', 'visualize', 'all'],
        help='Operation mode'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2005-01-01',
        help='Start date for historical data (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--model-type',
        type=str,
        default='xgboost',
        choices=['xgboost', 'lightgbm', 'random_forest', 'gradient_boosting', 'logistic'],
        help='Type of ML model'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=30.0,
        help='Probability threshold for crash warning (0-100)'
    )

    args = parser.parse_args()

    # Initialize system
    system = CrashProbabilitySystem(
        start_date=args.start_date,
        model_type=args.model_type
    )

    # Execute requested mode
    if args.mode == 'train':
        system.train_model()

    elif args.mode == 'predict':
        system.predict_current_crash_probability()

    elif args.mode == 'backtest':
        system.run_backtest(threshold=args.threshold)

    elif args.mode == 'visualize':
        system.create_visualizations()

    elif args.mode == 'all':
        print("Running complete pipeline...")
        system.train_model()
        system.predict_current_crash_probability()
        system.run_backtest(threshold=args.threshold)
        system.create_visualizations()

    print("\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
