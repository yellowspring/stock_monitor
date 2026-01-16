"""
Visualization utilities for crash prediction
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional


class CrashVisualizer:
    """Visualization tools for crash prediction analysis"""

    def __init__(self, style: str = 'seaborn-v0_8-darkgrid'):
        """Initialize visualizer"""
        plt.style.use('default')
        sns.set_palette("husl")

    def plot_crash_probability_timeline(
        self,
        df: pd.DataFrame,
        probability_col: str = 'crash_probability',
        threshold: float = 30.0,
        highlight_crashes: bool = True,
        figsize: tuple = (16, 8),
        save_path: Optional[str] = None
    ):
        """
        Plot crash probability over time

        Args:
            df: DataFrame with dates and crash probabilities
            probability_col: Name of probability column
            threshold: Warning threshold to highlight
            highlight_crashes: Whether to highlight actual crash periods
            figsize: Figure size
            save_path: Path to save figure (None to display)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)

        # Plot 1: Market prices
        ax1.plot(df.index, df['SPY'], label='SPY', linewidth=1.5, alpha=0.8)
        ax1.plot(df.index, df['QQQ'], label='QQQ', linewidth=1.5, alpha=0.8)
        ax1.set_ylabel('Price ($)', fontsize=12)
        ax1.set_title('Market Prices and Crash Probability Index', fontsize=14, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Crash probability
        ax2.fill_between(df.index, 0, df[probability_col], alpha=0.3, label='Crash Probability')
        ax2.plot(df.index, df[probability_col], linewidth=2, color='darkred')
        ax2.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold ({threshold})')
        ax2.set_ylabel('Crash Probability Index (0-100)', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylim(0, 100)
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3)

        # Highlight actual crash periods
        if highlight_crashes and 'crash_label' in df.columns:
            crash_periods = df[df['crash_label'] == 1]
            for idx in crash_periods.index:
                ax1.axvspan(idx, idx, alpha=0.1, color='red')
                ax2.axvspan(idx, idx, alpha=0.1, color='red')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")
        else:
            plt.show()

    def plot_feature_importance(
        self,
        feature_importance: pd.DataFrame,
        top_n: int = 20,
        figsize: tuple = (12, 8),
        save_path: Optional[str] = None
    ):
        """
        Plot feature importance

        Args:
            feature_importance: DataFrame with feature and importance columns
            top_n: Number of top features to display
            figsize: Figure size
            save_path: Path to save figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        top_features = feature_importance.head(top_n)

        colors = sns.color_palette("viridis", len(top_features))
        ax.barh(range(len(top_features)), top_features['importance'], color=colors)
        ax.set_yticks(range(len(top_features)))
        ax.set_yticklabels(top_features['feature'])
        ax.set_xlabel('Importance', fontsize=12)
        ax.set_title(f'Top {top_n} Feature Importance', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")
        else:
            plt.show()

    def plot_crash_events(
        self,
        df: pd.DataFrame,
        crash_periods: dict,
        probability_col: str = 'crash_probability',
        figsize: tuple = (16, 12),
        save_path: Optional[str] = None
    ):
        """
        Plot specific crash events with probabilities

        Args:
            df: DataFrame with data
            crash_periods: Dictionary of crash periods
            probability_col: Name of probability column
            figsize: Figure size
            save_path: Path to save figure
        """
        n_crashes = len(crash_periods)
        fig, axes = plt.subplots(n_crashes, 1, figsize=figsize)

        if n_crashes == 1:
            axes = [axes]

        for idx, (crash_name, crash_info) in enumerate(crash_periods.items()):
            start, end = crash_info['period']

            # Extend range to show lead-up and aftermath
            extended_start = pd.to_datetime(start) - pd.Timedelta(days=90)
            extended_end = pd.to_datetime(end) + pd.Timedelta(days=30)

            try:
                period_data = df.loc[extended_start:extended_end]
            except:
                continue

            ax = axes[idx]

            # Create twin axis
            ax2 = ax.twinx()

            # Plot prices
            ax.plot(period_data.index, period_data['SPY'], label='SPY', linewidth=2, color='blue', alpha=0.7)
            ax.plot(period_data.index, period_data['QQQ'], label='QQQ', linewidth=2, color='green', alpha=0.7)

            # Plot probability
            ax2.fill_between(period_data.index, 0, period_data[probability_col],
                            alpha=0.3, color='red', label='Crash Probability')
            ax2.plot(period_data.index, period_data[probability_col],
                    linewidth=2, color='darkred')

            # Highlight crash period
            ax.axvspan(pd.to_datetime(start), pd.to_datetime(end),
                      alpha=0.2, color='red', label='Crash Period')

            ax.set_ylabel('Price ($)', fontsize=11)
            ax2.set_ylabel('Crash Probability', fontsize=11, color='darkred')
            ax.set_title(crash_info['description'], fontsize=12, fontweight='bold')
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            ax2.set_ylim(0, 100)
            ax2.tick_params(axis='y', labelcolor='darkred')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")
        else:
            plt.show()

    def plot_confusion_matrix(
        self,
        confusion_matrix: np.ndarray,
        figsize: tuple = (8, 6),
        save_path: Optional[str] = None
    ):
        """
        Plot confusion matrix

        Args:
            confusion_matrix: 2x2 confusion matrix
            figsize: Figure size
            save_path: Path to save figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        sns.heatmap(confusion_matrix, annot=True, fmt='d', cmap='Blues',
                   xticklabels=['Normal', 'Crash'],
                   yticklabels=['Normal', 'Crash'],
                   ax=ax, cbar_kws={'label': 'Count'})

        ax.set_xlabel('Predicted', fontsize=12)
        ax.set_ylabel('Actual', fontsize=12)
        ax.set_title('Confusion Matrix', fontsize=14, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")
        else:
            plt.show()


if __name__ == "__main__":
    # Test visualizer
    import sys
    sys.path.append('..')

    from data.data_fetcher import MarketDataFetcher
    from data.label_generator import CrashLabelGenerator
    from features.feature_engineering import CrashFeatureEngine
    from models.crash_predictor import CrashPredictor
    from utils.backtester import CrashBacktester

    print("Preparing data for visualization...")

    # Fetch and prepare data
    fetcher = MarketDataFetcher(start_date="2007-01-01", end_date="2023-12-31")
    data = fetcher.fetch_data()

    label_gen = CrashLabelGenerator()
    data = label_gen.generate_labels(data)

    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)
    feature_names = feature_engine.get_feature_names(data)

    # Train model
    predictor = CrashPredictor(model_type='xgboost')
    X_train, X_test, y_train, y_test, train_dates, test_dates = predictor.prepare_data(
        data, feature_names, test_size=0.2
    )
    predictor.train(X_train, y_train)

    # Get predictions
    cols_to_check = feature_names + ['crash_label']
    data_clean = data.dropna(subset=cols_to_check)
    X_all = data_clean[feature_names].values
    data_clean['crash_probability'] = predictor.get_crash_probability_index(X_all)

    # Visualize
    visualizer = CrashVisualizer()

    print("Creating timeline plot...")
    visualizer.plot_crash_probability_timeline(data_clean)

    print("Creating feature importance plot...")
    visualizer.plot_feature_importance(predictor.get_top_features(20))

    print("Creating crash events plot...")
    backtester = CrashBacktester()
    visualizer.plot_crash_events(data_clean, backtester.known_crashes)
