"""
Backtesting module for crash prediction model
Validates performance on known crash events: 2008, 2020, 2022
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns


class CrashBacktester:
    """Backtesting framework for crash prediction"""

    def __init__(self):
        """Initialize backtester"""
        self.known_crashes = {
            '2008_financial_crisis': {
                'period': ('2008-09-01', '2008-11-30'),
                'description': '2008 Financial Crisis'
            },
            '2020_covid': {
                'period': ('2020-02-15', '2020-04-30'),
                'description': '2020 COVID-19 Crash'
            },
            '2022_bear_market': {
                'period': ('2022-01-01', '2022-10-31'),
                'description': '2022 Bear Market'
            },
            '2011_debt_crisis': {
                'period': ('2011-07-01', '2011-10-31'),
                'description': '2011 US Debt Crisis'
            },
            '2015_china_crash': {
                'period': ('2015-08-01', '2015-09-30'),
                'description': '2015 China Market Crash'
            },
            '2018_q4_selloff': {
                'period': ('2018-10-01', '2018-12-31'),
                'description': '2018 Q4 Selloff'
            }
        }

    def evaluate_crash_detection(
        self,
        df: pd.DataFrame,
        probability_col: str = 'crash_probability',
        threshold: float = 30.0
    ) -> Dict:
        """
        Evaluate crash detection performance

        Args:
            df: DataFrame with dates, crash_probability, and crash_label
            probability_col: Name of probability column
            threshold: Probability threshold for crash signal

        Returns:
            Dictionary with evaluation metrics
        """
        results = {}

        for crash_name, crash_info in self.known_crashes.items():
            start_date, end_date = crash_info['period']

            # Check if this period is in the data
            try:
                crash_data = df.loc[start_date:end_date]
            except KeyError:
                print(f"Warning: {crash_name} period not in data")
                continue

            if len(crash_data) == 0:
                continue

            # Calculate metrics for this crash period
            avg_probability = crash_data[probability_col].mean()
            max_probability = crash_data[probability_col].max()
            days_above_threshold = (crash_data[probability_col] > threshold).sum()
            pct_days_above_threshold = days_above_threshold / len(crash_data) * 100

            # Calculate lead time (days before crash when signal first appeared)
            # Look at 60 days before crash period
            lookback_start = pd.to_datetime(start_date) - pd.Timedelta(days=60)
            try:
                pre_crash_data = df.loc[lookback_start:start_date]
                days_before_warning = None

                for i, (idx, row) in enumerate(reversed(list(pre_crash_data.iterrows()))):
                    if row[probability_col] > threshold:
                        days_before_warning = i
                        break
            except:
                days_before_warning = None

            results[crash_name] = {
                'description': crash_info['description'],
                'period': crash_info['period'],
                'avg_probability': avg_probability,
                'max_probability': max_probability,
                'days_above_threshold': days_above_threshold,
                'pct_days_above_threshold': pct_days_above_threshold,
                'days_before_warning': days_before_warning,
                'num_days': len(crash_data)
            }

        return results

    def calculate_warning_statistics(
        self,
        df: pd.DataFrame,
        probability_col: str = 'crash_probability',
        threshold: float = 30.0
    ) -> Dict:
        """
        Calculate statistics about crash warnings

        Args:
            df: DataFrame with crash probabilities and labels
            probability_col: Name of probability column
            threshold: Probability threshold

        Returns:
            Dictionary with warning statistics
        """
        # Get signals
        df['signal'] = (df[probability_col] > threshold).astype(int)

        # True positives: signal=1 and crash_label=1
        tp = ((df['signal'] == 1) & (df['crash_label'] == 1)).sum()

        # False positives: signal=1 and crash_label=0
        fp = ((df['signal'] == 1) & (df['crash_label'] == 0)).sum()

        # True negatives: signal=0 and crash_label=0
        tn = ((df['signal'] == 0) & (df['crash_label'] == 0)).sum()

        # False negatives: signal=0 and crash_label=1
        fn = ((df['signal'] == 0) & (df['crash_label'] == 1)).sum()

        # Metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / len(df)

        stats = {
            'threshold': threshold,
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'accuracy': accuracy
        }

        return stats

    def find_optimal_threshold(
        self,
        df: pd.DataFrame,
        probability_col: str = 'crash_probability',
        metric: str = 'f1'
    ) -> Tuple[float, Dict]:
        """
        Find optimal probability threshold

        Args:
            df: DataFrame with probabilities and labels
            probability_col: Name of probability column
            metric: Metric to optimize ('f1', 'precision', 'recall')

        Returns:
            Tuple of (optimal_threshold, metrics_at_threshold)
        """
        thresholds = np.arange(0, 101, 5)
        results = []

        for threshold in thresholds:
            stats = self.calculate_warning_statistics(df, probability_col, threshold)
            stats['threshold'] = threshold
            results.append(stats)

        results_df = pd.DataFrame(results)

        # Find optimal threshold based on metric
        if metric == 'f1':
            optimal_idx = results_df['f1_score'].idxmax()
        elif metric == 'precision':
            optimal_idx = results_df['precision'].idxmax()
        elif metric == 'recall':
            optimal_idx = results_df['recall'].idxmax()
        else:
            raise ValueError(f"Unknown metric: {metric}")

        optimal_threshold = results_df.loc[optimal_idx, 'threshold']
        optimal_metrics = results_df.loc[optimal_idx].to_dict()

        return optimal_threshold, optimal_metrics

    def generate_backtest_report(
        self,
        df: pd.DataFrame,
        probability_col: str = 'crash_probability',
        threshold: float = 30.0
    ) -> str:
        """
        Generate comprehensive backtest report

        Args:
            df: DataFrame with probabilities and labels
            probability_col: Name of probability column
            threshold: Probability threshold

        Returns:
            String with formatted report
        """
        report = []
        report.append("=" * 80)
        report.append("CRASH PREDICTION BACKTEST REPORT")
        report.append("=" * 80)

        # Overall statistics
        overall_stats = self.calculate_warning_statistics(df, probability_col, threshold)
        report.append("\nOVERALL PERFORMANCE")
        report.append(f"Threshold: {threshold}")
        report.append(f"Precision: {overall_stats['precision']:.4f}")
        report.append(f"Recall: {overall_stats['recall']:.4f}")
        report.append(f"F1 Score: {overall_stats['f1_score']:.4f}")
        report.append(f"Accuracy: {overall_stats['accuracy']:.4f}")

        # Known crash detection
        crash_results = self.evaluate_crash_detection(df, probability_col, threshold)
        report.append("\n" + "=" * 80)
        report.append("KNOWN CRASH EVENTS DETECTION")
        report.append("=" * 80)

        for crash_name, metrics in crash_results.items():
            report.append(f"\n{metrics['description']}")
            report.append(f"  Period: {metrics['period'][0]} to {metrics['period'][1]}")
            report.append(f"  Average Probability: {metrics['avg_probability']:.2f}")
            report.append(f"  Max Probability: {metrics['max_probability']:.2f}")
            report.append(f"  Days Above Threshold: {metrics['days_above_threshold']}/{metrics['num_days']} "
                         f"({metrics['pct_days_above_threshold']:.1f}%)")
            if metrics['days_before_warning'] is not None:
                report.append(f"  Warning Lead Time: {metrics['days_before_warning']} days before")

        # Optimal threshold
        optimal_threshold, optimal_metrics = self.find_optimal_threshold(df, probability_col, 'f1')
        report.append("\n" + "=" * 80)
        report.append("OPTIMAL THRESHOLD ANALYSIS")
        report.append("=" * 80)
        report.append(f"\nOptimal Threshold (F1): {optimal_threshold}")
        report.append(f"  Precision: {optimal_metrics['precision']:.4f}")
        report.append(f"  Recall: {optimal_metrics['recall']:.4f}")
        report.append(f"  F1 Score: {optimal_metrics['f1_score']:.4f}")

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def backtest_stress_rules(
        self,
        df: pd.DataFrame,
        stress_col: str = 'stress_composite',
        price_col: str = 'SPY',
        rule_1_threshold: float = 80,
        rule_1_consecutive_days: int = 3,
        rule_1_drop_target: float = 5,
        rule_1_forward_days: int = 30,
        rule_2_threshold: float = 85,
        rule_2_drop_target: float = 10,
        rule_2_forward_days: int = 40
    ) -> Dict:
        """
        Backtest the empirical stress score rules:
        Rule 1: >threshold for N consecutive days → expect drop within forward days
        Rule 2: >threshold + price breakdown → expect larger drop

        Args:
            df: DataFrame with stress_composite and price data
            stress_col: Name of stress score column
            price_col: Name of price column for measuring drops
            rule_1_threshold: Stress threshold for Rule 1 (default 80)
            rule_1_consecutive_days: Consecutive days required (default 3)
            rule_1_drop_target: Expected drop % for success (default 5)
            rule_1_forward_days: Days to look forward (default 30)
            rule_2_threshold: Stress threshold for Rule 2 (default 85)
            rule_2_drop_target: Expected drop % for success (default 10)
            rule_2_forward_days: Days to look forward (default 40)

        Returns:
            Dictionary with backtest results for each rule
        """
        results = {
            'rule_1_high_stress_consecutive': [],
            'rule_2_extreme_stress_breakdown': [],
            'summary': {}
        }

        if stress_col not in df.columns:
            print(f"Warning: {stress_col} not found in DataFrame")
            return results

        df = df.copy()

        # Calculate forward returns for different horizons
        for days in [5, 10, 15, 20, 30]:
            df[f'fwd_return_{days}d'] = (
                df[price_col].shift(-days) / df[price_col] - 1
            ) * 100
            df[f'fwd_min_return_{days}d'] = df[price_col].rolling(days).apply(
                lambda x: (x.iloc[-1] / x.iloc[0] - 1) * 100 if len(x) == days else np.nan
            ).shift(-days)

        # Calculate max drawdown in forward window
        def forward_max_drawdown(prices, window):
            """Calculate maximum drawdown in forward window"""
            result = []
            for i in range(len(prices)):
                if i + window >= len(prices):
                    result.append(np.nan)
                else:
                    future_prices = prices.iloc[i:i+window+1]
                    cummax = future_prices.cummax()
                    drawdown = (future_prices - cummax) / cummax
                    result.append(drawdown.min() * 100)
            return pd.Series(result, index=prices.index)

        df['fwd_max_dd_20d'] = forward_max_drawdown(df[price_col], 20)
        df['fwd_max_dd_30d'] = forward_max_drawdown(df[price_col], 30)
        df['fwd_max_dd_40d'] = forward_max_drawdown(df[price_col], 40)

        # ========== RULE 1: >threshold for N consecutive days ==========
        df['stress_above_threshold'] = (df[stress_col] > rule_1_threshold).astype(int)

        # Count consecutive days above threshold
        df['consecutive_above_threshold'] = df['stress_above_threshold'].groupby(
            (df['stress_above_threshold'] != df['stress_above_threshold'].shift()).cumsum()
        ).cumsum()

        # Find signal triggers (first day of N+ consecutive days above threshold)
        df['rule_1_trigger'] = (
            (df['consecutive_above_threshold'] == rule_1_consecutive_days) &
            (df['stress_above_threshold'] == 1)
        ).astype(int)

        # Analyze each trigger
        rule_1_triggers = df[df['rule_1_trigger'] == 1].index.tolist()

        for trigger_date in rule_1_triggers:
            try:
                trigger_row = df.loc[trigger_date]
                consecutive_days = trigger_row['consecutive_above_threshold']

                # Get forward drawdown based on configured forward days
                fwd_dd_key = f'fwd_max_dd_{rule_1_forward_days}d'
                if fwd_dd_key not in df.columns:
                    df[fwd_dd_key] = forward_max_drawdown(df[price_col], rule_1_forward_days)

                fwd_dd = trigger_row.get(fwd_dd_key, np.nan)
                fwd_dd_20d = trigger_row.get('fwd_max_dd_20d', np.nan)
                fwd_dd_30d = trigger_row.get('fwd_max_dd_30d', np.nan)

                # Check if target drop occurred
                drop_occurred = fwd_dd <= -rule_1_drop_target if pd.notna(fwd_dd) else False

                results['rule_1_high_stress_consecutive'].append({
                    'date': str(trigger_date.date()) if hasattr(trigger_date, 'date') else str(trigger_date),
                    'stress_score': trigger_row[stress_col],
                    'consecutive_days': int(consecutive_days),
                    'fwd_max_dd_20d': round(fwd_dd_20d, 2) if pd.notna(fwd_dd_20d) else None,
                    'fwd_max_dd_30d': round(fwd_dd_30d, 2) if pd.notna(fwd_dd_30d) else None,
                    f'fwd_max_dd_{rule_1_forward_days}d': round(fwd_dd, 2) if pd.notna(fwd_dd) else None,
                    'drop_occurred': drop_occurred
                })
            except Exception as e:
                continue

        # ========== RULE 2: >threshold + price breakdown ==========
        # Price breakdown = price below 20-day MA AND below 50-day MA

        df['ma_20'] = df[price_col].rolling(20).mean()
        df['ma_50'] = df[price_col].rolling(50).mean()

        df['price_breakdown'] = (
            (df[price_col] < df['ma_20']) &
            (df[price_col] < df['ma_50'])
        ).astype(int)

        df['rule_2_trigger'] = (
            (df[stress_col] > rule_2_threshold) &
            (df['price_breakdown'] == 1)
        ).astype(int)

        # Only take first trigger in each episode (avoid counting same event multiple times)
        df['rule_2_trigger_first'] = (
            (df['rule_2_trigger'] == 1) &
            (df['rule_2_trigger'].shift(1) != 1)
        ).astype(int)

        rule_2_triggers = df[df['rule_2_trigger_first'] == 1].index.tolist()

        for trigger_date in rule_2_triggers:
            try:
                trigger_row = df.loc[trigger_date]

                # Get forward drawdown based on configured forward days
                fwd_dd_key = f'fwd_max_dd_{rule_2_forward_days}d'
                if fwd_dd_key not in df.columns:
                    df[fwd_dd_key] = forward_max_drawdown(df[price_col], rule_2_forward_days)

                fwd_dd = trigger_row.get(fwd_dd_key, np.nan)
                fwd_dd_20d = trigger_row.get('fwd_max_dd_20d', np.nan)
                fwd_dd_30d = trigger_row.get('fwd_max_dd_30d', np.nan)

                # Check if target drop occurred
                drop_occurred = fwd_dd <= -rule_2_drop_target if pd.notna(fwd_dd) else False

                results['rule_2_extreme_stress_breakdown'].append({
                    'date': str(trigger_date.date()) if hasattr(trigger_date, 'date') else str(trigger_date),
                    'stress_score': round(trigger_row[stress_col], 2),
                    'price': round(trigger_row[price_col], 2),
                    'ma_20': round(trigger_row['ma_20'], 2),
                    'ma_50': round(trigger_row['ma_50'], 2),
                    'fwd_max_dd_20d': round(fwd_dd_20d, 2) if pd.notna(fwd_dd_20d) else None,
                    'fwd_max_dd_30d': round(fwd_dd_30d, 2) if pd.notna(fwd_dd_30d) else None,
                    f'fwd_max_dd_{rule_2_forward_days}d': round(fwd_dd, 2) if pd.notna(fwd_dd) else None,
                    'drop_occurred': drop_occurred
                })
            except Exception as e:
                continue

        # ========== SUMMARY STATISTICS ==========
        rule_1_results = results['rule_1_high_stress_consecutive']
        rule_2_results = results['rule_2_extreme_stress_breakdown']

        fwd_dd_key_1 = f'fwd_max_dd_{rule_1_forward_days}d'
        fwd_dd_key_2 = f'fwd_max_dd_{rule_2_forward_days}d'

        if rule_1_results:
            rule_1_success = sum(1 for r in rule_1_results if r['drop_occurred'])
            rule_1_total = len(rule_1_results)
            rule_1_avg_dd = np.nanmean([r[fwd_dd_key_1] for r in rule_1_results if r.get(fwd_dd_key_1) is not None])
        else:
            rule_1_success, rule_1_total, rule_1_avg_dd = 0, 0, 0

        if rule_2_results:
            rule_2_success = sum(1 for r in rule_2_results if r['drop_occurred'])
            rule_2_total = len(rule_2_results)
            rule_2_avg_dd = np.nanmean([r[fwd_dd_key_2] for r in rule_2_results if r.get(fwd_dd_key_2) is not None])
        else:
            rule_2_success, rule_2_total, rule_2_avg_dd = 0, 0, 0

        results['summary'] = {
            'rule_1': {
                'description': f'Stress >{rule_1_threshold} for {rule_1_consecutive_days}+ consecutive days → ≥{rule_1_drop_target}% drop in {rule_1_forward_days} days',
                'total_signals': rule_1_total,
                'successful_predictions': rule_1_success,
                'success_rate': round(rule_1_success / rule_1_total * 100, 1) if rule_1_total > 0 else 0,
                'avg_forward_drawdown': round(rule_1_avg_dd, 2) if rule_1_avg_dd else 0
            },
            'rule_2': {
                'description': f'Stress >{rule_2_threshold} + price breakdown → ≥{rule_2_drop_target}% drop in {rule_2_forward_days} days',
                'total_signals': rule_2_total,
                'successful_predictions': rule_2_success,
                'success_rate': round(rule_2_success / rule_2_total * 100, 1) if rule_2_total > 0 else 0,
                'avg_forward_drawdown': round(rule_2_avg_dd, 2) if rule_2_avg_dd else 0
            },
            'parameters': {
                'rule_1_threshold': rule_1_threshold,
                'rule_1_consecutive_days': rule_1_consecutive_days,
                'rule_1_drop_target': rule_1_drop_target,
                'rule_1_forward_days': rule_1_forward_days,
                'rule_2_threshold': rule_2_threshold,
                'rule_2_drop_target': rule_2_drop_target,
                'rule_2_forward_days': rule_2_forward_days
            }
        }

        return results

    def generate_stress_rules_report(
        self,
        df: pd.DataFrame,
        stress_col: str = 'stress_composite',
        price_col: str = 'SPY',
        rule_1_threshold: float = 80,
        rule_1_consecutive_days: int = 3,
        rule_1_drop_target: float = 5,
        rule_1_forward_days: int = 30,
        rule_2_threshold: float = 85,
        rule_2_drop_target: float = 10,
        rule_2_forward_days: int = 40
    ) -> str:
        """
        Generate a formatted report for stress score empirical rules backtest

        Args:
            df: DataFrame with stress_composite and price data
            stress_col: Name of stress score column
            price_col: Name of price column
            rule_1_threshold: Stress threshold for Rule 1
            rule_1_consecutive_days: Consecutive days required
            rule_1_drop_target: Expected drop % for success
            rule_1_forward_days: Days to look forward
            rule_2_threshold: Stress threshold for Rule 2
            rule_2_drop_target: Expected drop % for success
            rule_2_forward_days: Days to look forward

        Returns:
            Formatted string report
        """
        results = self.backtest_stress_rules(
            df, stress_col, price_col,
            rule_1_threshold, rule_1_consecutive_days, rule_1_drop_target, rule_1_forward_days,
            rule_2_threshold, rule_2_drop_target, rule_2_forward_days
        )

        report = []
        report.append("=" * 80)
        report.append("STRESS SCORE EMPIRICAL RULES BACKTEST REPORT")
        report.append("=" * 80)

        # Rule 1 Summary
        r1 = results['summary']['rule_1']
        report.append(f"\n📌 RULE 1: {r1['description']}")
        report.append("-" * 60)
        report.append(f"   Total Signals:        {r1['total_signals']}")
        report.append(f"   Successful (≥{rule_1_drop_target}% drop): {r1['successful_predictions']}")
        report.append(f"   Success Rate:         {r1['success_rate']}%")
        report.append(f"   Avg Forward Drawdown: {r1['avg_forward_drawdown']}%")

        # Rule 1 Details
        fwd_dd_key_1 = f'fwd_max_dd_{rule_1_forward_days}d'
        if results['rule_1_high_stress_consecutive']:
            report.append("\n   Signal Details:")
            for signal in results['rule_1_high_stress_consecutive'][-10:]:  # Last 10
                status = "✅" if signal['drop_occurred'] else "❌"
                fwd_dd = signal.get(fwd_dd_key_1, signal.get('fwd_max_dd_30d'))
                report.append(
                    f"   {status} {signal['date']}: Stress={signal['stress_score']:.1f}, "
                    f"Consecutive={signal['consecutive_days']}d, MaxDD={fwd_dd}%"
                )

        # Rule 2 Summary
        r2 = results['summary']['rule_2']
        report.append(f"\n\n📌 RULE 2: {r2['description']}")
        report.append("-" * 60)
        report.append(f"   Total Signals:        {r2['total_signals']}")
        report.append(f"   Successful (≥{rule_2_drop_target}% drop): {r2['successful_predictions']}")
        report.append(f"   Success Rate:         {r2['success_rate']}%")
        report.append(f"   Avg Forward Drawdown: {r2['avg_forward_drawdown']}%")

        # Rule 2 Details
        fwd_dd_key_2 = f'fwd_max_dd_{rule_2_forward_days}d'
        if results['rule_2_extreme_stress_breakdown']:
            report.append("\n   Signal Details:")
            for signal in results['rule_2_extreme_stress_breakdown'][-10:]:  # Last 10
                status = "✅" if signal['drop_occurred'] else "❌"
                fwd_dd = signal.get(fwd_dd_key_2, signal.get('fwd_max_dd_40d'))
                report.append(
                    f"   {status} {signal['date']}: Stress={signal['stress_score']}, "
                    f"Price={signal['price']}, MA20={signal['ma_20']}, MaxDD={fwd_dd}%"
                )

        # Conclusion
        report.append("\n" + "=" * 80)
        report.append("CONCLUSION")
        report.append("=" * 80)

        if r1['success_rate'] >= 60:
            report.append(f"✅ Rule 1 is VALID: {r1['success_rate']}% success rate (threshold: 60%)")
        else:
            report.append(f"⚠️  Rule 1 needs refinement: {r1['success_rate']}% success rate (below 60%)")

        if r2['success_rate'] >= 60:
            report.append(f"✅ Rule 2 is VALID: {r2['success_rate']}% success rate (threshold: 60%)")
        else:
            report.append(f"⚠️  Rule 2 needs refinement: {r2['success_rate']}% success rate (below 60%)")

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def optimize_stress_rules(
        self,
        df: pd.DataFrame,
        stress_col: str = 'stress_composite',
        price_col: str = 'SPY',
        min_success_rate: float = 50.0
    ) -> Dict:
        """
        Find optimal parameters for stress rules by grid search

        Args:
            df: DataFrame with stress_composite and price data
            stress_col: Name of stress score column
            price_col: Name of price column
            min_success_rate: Minimum acceptable success rate

        Returns:
            Dictionary with optimal parameters and results
        """
        # Parameter grid
        thresholds = [70, 75, 80, 85, 90]
        consecutive_days = [3, 5, 7]
        drop_targets = [3, 5, 7, 10]
        forward_days = [20, 30, 40, 60]

        best_rule_1 = {'success_rate': 0, 'params': None, 'results': None}
        best_rule_2 = {'success_rate': 0, 'params': None, 'results': None}

        print("Optimizing Rule 1...")
        for threshold in thresholds:
            for cons_days in consecutive_days:
                for drop in drop_targets:
                    for fwd in forward_days:
                        try:
                            results = self.backtest_stress_rules(
                                df, stress_col, price_col,
                                rule_1_threshold=threshold,
                                rule_1_consecutive_days=cons_days,
                                rule_1_drop_target=drop,
                                rule_1_forward_days=fwd,
                                rule_2_threshold=90,  # Placeholder
                                rule_2_drop_target=10,
                                rule_2_forward_days=40
                            )
                            r1 = results['summary']['rule_1']
                            if r1['total_signals'] >= 10 and r1['success_rate'] > best_rule_1['success_rate']:
                                best_rule_1 = {
                                    'success_rate': r1['success_rate'],
                                    'params': {
                                        'threshold': threshold,
                                        'consecutive_days': cons_days,
                                        'drop_target': drop,
                                        'forward_days': fwd
                                    },
                                    'results': r1
                                }
                        except:
                            continue

        print("Optimizing Rule 2...")
        for threshold in thresholds:
            for drop in drop_targets:
                for fwd in forward_days:
                    try:
                        results = self.backtest_stress_rules(
                            df, stress_col, price_col,
                            rule_1_threshold=80,  # Placeholder
                            rule_1_consecutive_days=3,
                            rule_1_drop_target=5,
                            rule_1_forward_days=30,
                            rule_2_threshold=threshold,
                            rule_2_drop_target=drop,
                            rule_2_forward_days=fwd
                        )
                        r2 = results['summary']['rule_2']
                        if r2['total_signals'] >= 10 and r2['success_rate'] > best_rule_2['success_rate']:
                            best_rule_2 = {
                                'success_rate': r2['success_rate'],
                                'params': {
                                    'threshold': threshold,
                                    'drop_target': drop,
                                    'forward_days': fwd
                                },
                                'results': r2
                            }
                    except:
                        continue

        return {
            'rule_1_optimal': best_rule_1,
            'rule_2_optimal': best_rule_2
        }


if __name__ == "__main__":
    # Test backtester
    import sys
    sys.path.append('..')

    from data.data_fetcher import MarketDataFetcher
    from data.label_generator import CrashLabelGenerator
    from features.feature_engineering import CrashFeatureEngine
    from models.crash_predictor import CrashPredictor

    # Fetch data
    print("Fetching data...")
    fetcher = MarketDataFetcher(start_date="2005-01-01", end_date="2023-12-31")
    data = fetcher.fetch_data()

    # Generate labels
    print("Generating labels...")
    label_gen = CrashLabelGenerator()
    data = label_gen.generate_labels(data)

    # Create features
    print("Creating features...")
    feature_engine = CrashFeatureEngine()
    data = feature_engine.create_features(data)
    feature_names = feature_engine.get_feature_names(data)

    # Train model
    print("Training model...")
    predictor = CrashPredictor(model_type='xgboost')
    X_train, X_test, y_train, y_test, train_dates, test_dates = predictor.prepare_data(
        data, feature_names, test_size=0.2
    )
    predictor.train(X_train, y_train)

    # Get predictions for all data
    cols_to_check = feature_names + ['crash_label']
    data_clean = data.dropna(subset=cols_to_check)
    X_all = data_clean[feature_names].values
    data_clean['crash_probability'] = predictor.get_crash_probability_index(X_all)

    # Run backtest
    print("\nRunning backtest...")
    backtester = CrashBacktester()
    report = backtester.generate_backtest_report(data_clean, threshold=30.0)
    print(report)
