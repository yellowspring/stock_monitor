"""
Crash Probability Model
Binary classification model that outputs crash probability (0-100)
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import IsotonicRegression, calibration_curve
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, roc_curve, brier_score_loss
)
import xgboost as xgb
import lightgbm as lgb
import joblib
from typing import Dict, Tuple, Optional, List
import warnings
warnings.filterwarnings('ignore')


class CrashPredictor:
    """Binary classification model for crash prediction"""

    def __init__(self, model_type: str = 'xgboost'):
        """
        Initialize crash predictor

        Args:
            model_type: Type of model ('xgboost', 'lightgbm', 'random_forest', 'gradient_boosting', 'logistic')
        """
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.feature_importance: Optional[pd.DataFrame] = None
        self.calibrator: Optional[IsotonicRegression] = None
        self.is_calibrated: bool = False

    def _create_model(self):
        """Create the specified model type"""
        if self.model_type == 'xgboost':
            return xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=5,  # Handle class imbalance
                random_state=42,
                eval_metric='logloss'
            )
        elif self.model_type == 'lightgbm':
            return lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                class_weight='balanced',
                random_state=42
            )
        elif self.model_type == 'random_forest':
            return RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_split=20,
                min_samples_leaf=10,
                class_weight='balanced',
                random_state=42
            )
        elif self.model_type == 'gradient_boosting':
            return GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            )
        elif self.model_type == 'logistic':
            return LogisticRegression(
                class_weight='balanced',
                random_state=42,
                max_iter=1000
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def prepare_data(
        self,
        df: pd.DataFrame,
        feature_names: List[str],
        test_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex, pd.DatetimeIndex]:
        """
        Prepare data for training

        Args:
            df: DataFrame with features and labels
            feature_names: List of feature column names
            test_size: Proportion of data for testing

        Returns:
            X_train, X_test, y_train, y_test, train_dates, test_dates
        """
        # Remove NaN rows (only check feature columns and label)
        cols_to_check = feature_names + ['crash_label']
        df_clean = df.dropna(subset=cols_to_check)

        # Get features and labels
        X = df_clean[feature_names].values
        y = df_clean['crash_label'].values
        dates = df_clean.index

        # Time series split (preserve temporal order)
        split_idx = int(len(X) * (1 - test_size))

        X_train = X[:split_idx]
        X_test = X[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]
        train_dates = dates[:split_idx]
        test_dates = dates[split_idx:]

        # Scale features
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        self.feature_names = feature_names

        print(f"Training set: {len(X_train)} samples, {y_train.sum()} crashes ({y_train.mean()*100:.2f}%)")
        print(f"Test set: {len(X_test)} samples, {y_test.sum()} crashes ({y_test.mean()*100:.2f}%)")

        return X_train, X_test, y_train, y_test, train_dates, test_dates

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """
        Train the model

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Dictionary with training metrics
        """
        print(f"\nTraining {self.model_type} model...")

        self.model = self._create_model()
        self.model.fit(X_train, y_train)

        # Get feature importance
        if hasattr(self.model, 'feature_importances_'):
            self.feature_importance = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)

        # Training metrics
        y_train_pred = self.model.predict(X_train)
        y_train_proba = self.model.predict_proba(X_train)[:, 1]

        metrics = {
            'train_accuracy': (y_train_pred == y_train).mean(),
            'train_auc': roc_auc_score(y_train, y_train_proba)
        }

        print(f"Training accuracy: {metrics['train_accuracy']:.4f}")
        print(f"Training AUC: {metrics['train_auc']:.4f}")

        return metrics

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """
        Evaluate the model

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Dictionary with evaluation metrics
        """
        print("\nEvaluating model...")

        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            'test_accuracy': (y_pred == y_test).mean(),
            'test_auc': roc_auc_score(y_test, y_proba),
            'confusion_matrix': confusion_matrix(y_test, y_pred),
            'classification_report': classification_report(y_test, y_pred)
        }

        print(f"Test accuracy: {metrics['test_accuracy']:.4f}")
        print(f"Test AUC: {metrics['test_auc']:.4f}")
        print("\nConfusion Matrix:")
        print(metrics['confusion_matrix'])
        print("\nClassification Report:")
        print(metrics['classification_report'])

        return metrics

    def calibrate(self, X_cal: np.ndarray, y_cal: np.ndarray) -> Dict:
        """
        Calibrate model probabilities using Isotonic Regression

        This ensures that when model predicts 70%, approximately 70% of those
        cases actually result in crashes historically.

        Args:
            X_cal: Calibration set features (should be separate from train/test)
            y_cal: Calibration set labels

        Returns:
            Dictionary with calibration metrics
        """
        print("\nCalibrating probabilities with Isotonic Regression...")

        # Get raw probabilities
        raw_proba = self.model.predict_proba(X_cal)[:, 1]

        # Fit isotonic regression
        self.calibrator = IsotonicRegression(out_of_bounds='clip')
        self.calibrator.fit(raw_proba, y_cal)
        self.is_calibrated = True

        # Get calibrated probabilities
        cal_proba = self.calibrator.predict(raw_proba)

        # Calculate metrics
        raw_brier = brier_score_loss(y_cal, raw_proba)
        cal_brier = brier_score_loss(y_cal, cal_proba)

        # Calibration curve
        prob_true_raw, prob_pred_raw = calibration_curve(y_cal, raw_proba, n_bins=10, strategy='uniform')
        prob_true_cal, prob_pred_cal = calibration_curve(y_cal, cal_proba, n_bins=10, strategy='uniform')

        metrics = {
            'raw_brier_score': raw_brier,
            'calibrated_brier_score': cal_brier,
            'brier_improvement': (raw_brier - cal_brier) / raw_brier * 100,
            'calibration_curve_raw': (prob_pred_raw, prob_true_raw),
            'calibration_curve_cal': (prob_pred_cal, prob_true_cal)
        }

        print(f"Raw Brier Score: {raw_brier:.4f}")
        print(f"Calibrated Brier Score: {cal_brier:.4f}")
        print(f"Brier Improvement: {metrics['brier_improvement']:.1f}%")

        # Print calibration table
        print("\nCalibration Table (after calibration):")
        print(f"{'Predicted':^12} | {'Actual':^12} | {'Count':^8}")
        print("-" * 36)
        for i in range(len(prob_pred_cal)):
            # Count samples in this bin
            mask = (cal_proba >= (i/10)) & (cal_proba < ((i+1)/10))
            count = mask.sum()
            if count > 0:
                print(f"{prob_pred_cal[i]*100:^10.1f}% | {prob_true_cal[i]*100:^10.1f}% | {count:^8}")

        return metrics

    def evaluate_with_calibration(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """
        Evaluate model with calibration metrics

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Dictionary with evaluation metrics including Brier score
        """
        # Get base metrics
        metrics = self.evaluate(X_test, y_test)

        # Get probabilities
        y_proba_raw = self.model.predict_proba(X_test)[:, 1]

        if self.is_calibrated:
            y_proba = self.calibrator.predict(y_proba_raw)
        else:
            y_proba = y_proba_raw

        # Add Brier score
        metrics['brier_score'] = brier_score_loss(y_test, y_proba)

        # Calibration curve
        prob_true, prob_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy='uniform')
        metrics['calibration_curve'] = (prob_pred, prob_true)

        print(f"\nBrier Score: {metrics['brier_score']:.4f}")
        print("(Lower is better. Perfect calibration = 0)")

        return metrics

    def predict_probability(self, X: np.ndarray, calibrated: bool = True) -> np.ndarray:
        """
        Predict crash probability

        Args:
            X: Features
            calibrated: Whether to use calibrated probabilities (if available)

        Returns:
            Array of crash probabilities (0-1)
        """
        X_scaled = self.scaler.transform(X)
        raw_proba = self.model.predict_proba(X_scaled)[:, 1]

        # Apply calibration if available and requested
        if calibrated and self.is_calibrated and self.calibrator is not None:
            return self.calibrator.predict(raw_proba)
        return raw_proba

    def get_crash_probability_index(self, X: np.ndarray) -> np.ndarray:
        """
        Get Crash Probability Index (0-100)

        Args:
            X: Features

        Returns:
            Array of crash probability indices (0-100)
        """
        probabilities = self.predict_probability(X)
        return probabilities * 100

    def save_model(self, filepath: str):
        """Save model, scaler, and calibrator"""
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'feature_importance': self.feature_importance,
            'calibrator': self.calibrator,
            'is_calibrated': self.is_calibrated
        }, filepath)
        print(f"Model saved to {filepath}")
        if self.is_calibrated:
            print("  (includes probability calibration)")

    def load_model(self, filepath: str):
        """Load model, scaler, and calibrator"""
        data = joblib.load(filepath)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.model_type = data['model_type']
        self.feature_importance = data.get('feature_importance')
        self.calibrator = data.get('calibrator')
        self.is_calibrated = data.get('is_calibrated', False)
        print(f"Model loaded from {filepath}")
        if self.is_calibrated:
            print("  (probability calibration enabled)")

    def get_top_features(self, n: int = 20) -> pd.DataFrame:
        """
        Get top N most important features

        Args:
            n: Number of top features

        Returns:
            DataFrame with top features and their importance
        """
        if self.feature_importance is None:
            return None
        return self.feature_importance.head(n)


if __name__ == "__main__":
    # Test crash predictor
    import sys
    sys.path.append('..')

    from data.data_fetcher import MarketDataFetcher
    from data.label_generator import CrashLabelGenerator
    from features.feature_engineering import CrashFeatureEngine

    # Fetch data
    print("Fetching data...")
    fetcher = MarketDataFetcher(start_date="2005-01-01", end_date="2023-12-31")
    data = fetcher.fetch_data()

    # Generate labels
    print("\nGenerating labels...")
    label_gen = CrashLabelGenerator()
    data = label_gen.generate_labels(data)

    # Create features
    print("\nCreating features...")
    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)
    feature_names = feature_engine.get_feature_names(data)

    # Train model
    print("\nTraining model...")
    predictor = CrashPredictor(model_type='xgboost')

    X_train, X_test, y_train, y_test, train_dates, test_dates = predictor.prepare_data(
        data, feature_names, test_size=0.2
    )

    train_metrics = predictor.train(X_train, y_train)
    test_metrics = predictor.evaluate(X_test, y_test)

    # Feature importance
    print("\nTop 20 features:")
    print(predictor.get_top_features(20))

    # Predict on recent data
    print("\nRecent crash probabilities:")
    recent_proba = predictor.get_crash_probability_index(X_test[-10:])
    recent_df = pd.DataFrame({
        'date': test_dates[-10:],
        'crash_probability': recent_proba,
        'actual_crash': y_test[-10:]
    })
    print(recent_df)
