"""
Smart alerting with trend detection
Combines threshold-based and trend-based alerts
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class SmartCrashAlerter:
    """
    Smart alerting system with multiple trigger conditions:
    1. Fixed threshold (e.g., >60% = EXTREME)
    2. Moderate threshold with rising trend (e.g., >20% AND rising fast)
    3. Acceleration detection (rapid increase in probability)
    """

    def __init__(
        self,
        extreme_threshold: float = 60.0,
        moderate_threshold: float = 20.0,
        trend_window: int = 3,
        trend_increase_threshold: float = 10.0,
        acceleration_threshold: float = 30.0
    ):
        """
        Initialize smart alerter

        Args:
            extreme_threshold: Immediate alert level (default: 60%)
            moderate_threshold: Alert if rising trend (default: 20%)
            trend_window: Days to check for trend (default: 3)
            trend_increase_threshold: % increase to trigger trend alert (default: 10%)
            acceleration_threshold: Single-day jump to trigger alert (default: 30%)
        """
        self.extreme_threshold = extreme_threshold
        self.moderate_threshold = moderate_threshold
        self.trend_window = trend_window
        self.trend_increase_threshold = trend_increase_threshold
        self.acceleration_threshold = acceleration_threshold

    def check_alert_conditions(
        self,
        current_prob: float,
        recent_probs: List[float]
    ) -> Dict[str, any]:
        """
        Check all alert conditions

        Args:
            current_prob: Current crash probability (0-100)
            recent_probs: List of recent probabilities [oldest, ..., newest]
                         Should include at least trend_window values

        Returns:
            Dictionary with alert status and details
        """
        alert_triggered = False
        alert_reasons = []
        alert_level = "NONE"
        urgency = "LOW"

        # Condition 1: EXTREME threshold
        if current_prob >= self.extreme_threshold:
            alert_triggered = True
            alert_reasons.append(f"Probability ({current_prob:.1f}%) exceeds EXTREME threshold ({self.extreme_threshold}%)")
            alert_level = "EXTREME"
            urgency = "CRITICAL" if current_prob >= 80 else "HIGH"

        # Condition 2: Acceleration (sudden spike)
        if len(recent_probs) > 0:
            prev_prob = recent_probs[-1]
            single_day_change = current_prob - prev_prob

            if single_day_change >= self.acceleration_threshold:
                alert_triggered = True
                alert_reasons.append(
                    f"Rapid acceleration: +{single_day_change:.1f}% in 1 day (from {prev_prob:.1f}% to {current_prob:.1f}%)"
                )
                if alert_level == "NONE":
                    alert_level = "HIGH"
                urgency = "HIGH"

        # Condition 3: Rising trend above moderate threshold
        if len(recent_probs) >= self.trend_window and current_prob >= self.moderate_threshold:
            # Get trend window data
            trend_data = recent_probs[-self.trend_window:]
            trend_start = trend_data[0]
            trend_increase = current_prob - trend_start

            # Check if rising trend
            is_rising = all(trend_data[i] <= trend_data[i+1] for i in range(len(trend_data)-1))

            if is_rising and trend_increase >= self.trend_increase_threshold:
                alert_triggered = True
                alert_reasons.append(
                    f"Rising trend: +{trend_increase:.1f}% over {self.trend_window} days (from {trend_start:.1f}% to {current_prob:.1f}%)"
                )
                if alert_level == "NONE":
                    alert_level = "MODERATE"
                if urgency == "LOW":
                    urgency = "MODERATE"

        # Determine overall risk level based on current probability
        if current_prob >= 80:
            risk_level = "EXTREME"
        elif current_prob >= 60:
            risk_level = "EXTREME"
        elif current_prob >= 40:
            risk_level = "HIGH"
        elif current_prob >= 20:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        return {
            'alert_triggered': alert_triggered,
            'alert_level': alert_level,
            'risk_level': risk_level,
            'urgency': urgency,
            'reasons': alert_reasons,
            'current_probability': current_prob,
            'trend_detected': len([r for r in alert_reasons if 'trend' in r.lower()]) > 0,
            'acceleration_detected': len([r for r in alert_reasons if 'acceleration' in r.lower()]) > 0
        }

    def analyze_historical_alerts(
        self,
        probabilities: pd.Series,
        dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        Analyze when alerts would have been triggered historically

        Args:
            probabilities: Series of crash probabilities
            dates: Corresponding dates

        Returns:
            DataFrame with alert history
        """
        alerts = []

        for i in range(self.trend_window, len(probabilities)):
            current_prob = probabilities.iloc[i]
            recent_probs = probabilities.iloc[i-self.trend_window:i].tolist()
            date = dates[i]

            alert_info = self.check_alert_conditions(current_prob, recent_probs)

            if alert_info['alert_triggered']:
                alerts.append({
                    'date': date,
                    'probability': current_prob,
                    'alert_level': alert_info['alert_level'],
                    'urgency': alert_info['urgency'],
                    'reasons': '; '.join(alert_info['reasons']),
                    'trend': alert_info['trend_detected'],
                    'acceleration': alert_info['acceleration_detected']
                })

        return pd.DataFrame(alerts)

    def create_alert_summary(self, alert_info: Dict) -> str:
        """Create formatted alert summary"""
        if not alert_info['alert_triggered']:
            return "No alert triggered"

        summary = f"""
{'='*60}
🚨 CRASH ALERT - {alert_info['alert_level']} LEVEL
{'='*60}

Current Probability: {alert_info['current_probability']:.1f}%
Risk Level: {alert_info['risk_level']}
Urgency: {alert_info['urgency']}

Alert Reasons:
"""
        for i, reason in enumerate(alert_info['reasons'], 1):
            summary += f"  {i}. {reason}\n"

        summary += f"\n{'='*60}\n"
        return summary


def compare_alert_strategies(
    probabilities: pd.Series,
    dates: pd.DatetimeIndex,
    actual_crashes: pd.Series
) -> pd.DataFrame:
    """
    Compare different alert strategies

    Args:
        probabilities: Crash probabilities
        dates: Dates
        actual_crashes: Actual crash labels (0/1)

    Returns:
        Comparison DataFrame
    """
    strategies = {
        'Conservative (>20%)': {'extreme': 20, 'moderate': 10, 'trend': 5, 'accel': 10},
        'Balanced (>40%)': {'extreme': 40, 'moderate': 20, 'trend': 10, 'accel': 20},
        'Aggressive (>60%)': {'extreme': 60, 'moderate': 40, 'trend': 15, 'accel': 30},
        'Smart Trend (>20% rising)': {'extreme': 60, 'moderate': 20, 'trend': 10, 'accel': 30}
    }

    results = []

    for name, params in strategies.items():
        alerter = SmartCrashAlerter(
            extreme_threshold=params['extreme'],
            moderate_threshold=params['moderate'],
            trend_increase_threshold=params['trend'],
            acceleration_threshold=params['accel']
        )

        alerts_df = alerter.analyze_historical_alerts(probabilities, dates)

        # Calculate metrics
        total_alerts = len(alerts_df)

        # True positives: alerts within 20 days before a crash
        tp = 0
        for _, alert in alerts_df.iterrows():
            alert_date = alert['date']
            # Check if crash occurs within next 20 days
            future_window = actual_crashes.loc[alert_date:].iloc[:20]
            if future_window.sum() > 0:
                tp += 1

        fp = total_alerts - tp
        precision = tp / total_alerts if total_alerts > 0 else 0

        # Lead time: average days before crash
        lead_times = []
        for _, alert in alerts_df.iterrows():
            alert_date = alert['date']
            future_crashes = actual_crashes.loc[alert_date:]
            future_crashes_idx = future_crashes[future_crashes == 1]
            if len(future_crashes_idx) > 0:
                first_crash = future_crashes_idx.index[0]
                days_before = (first_crash - alert_date).days
                if days_before <= 20:
                    lead_times.append(days_before)

        avg_lead_time = np.mean(lead_times) if lead_times else 0

        results.append({
            'Strategy': name,
            'Total Alerts': total_alerts,
            'True Alerts': tp,
            'False Alerts': fp,
            'Precision': f"{precision:.2%}",
            'Avg Lead Time': f"{avg_lead_time:.1f} days"
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("=" * 80)
    print("SMART CRASH ALERTING - STRATEGY COMPARISON")
    print("=" * 80)

    # Example: Test on COVID period
    print("\nExample 1: Detecting COVID crash build-up")
    print("-" * 80)

    # Simulate COVID probability progression
    dates = pd.date_range('2020-02-01', '2020-02-15', freq='D')
    probs = [1.0, 1.2, 5.1, 7.3, 21.6, 96.5, 98.9, 99.0, 99.1, 99.3, 99.1, 99.3, 98.7, 97.9, 93.0]

    alerter = SmartCrashAlerter(
        extreme_threshold=60.0,
        moderate_threshold=20.0,
        trend_increase_threshold=10.0,
        acceleration_threshold=30.0
    )

    for i in range(3, len(probs)):
        date = dates[i]
        current = probs[i]
        recent = probs[max(0, i-3):i]

        alert = alerter.check_alert_conditions(current, recent)

        if alert['alert_triggered']:
            print(f"\n{date.strftime('%Y-%m-%d')}: {current:.1f}%")
            print(f"  Alert Level: {alert['alert_level']}")
            print(f"  Urgency: {alert['urgency']}")
            for reason in alert['reasons']:
                print(f"  - {reason}")

    print("\n" + "=" * 80)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 80)
    print("""
For optimal crash detection, use:

1. EXTREME Threshold: 60%
   - Immediate alert
   - High urgency action required

2. MODERATE Threshold: 20%
   - BUT only if RISING TREND detected
   - Catches early build-up phase (like Feb 6, 2020)

3. Trend Parameters:
   - Window: 3 days
   - Increase threshold: 10% over 3 days
   - This catches sustained rise, filters noise

4. Acceleration Detection: 30%
   - Single-day spike (like Feb 6→7: +75%)
   - Urgent warning of sudden regime change

This combination gives you:
✓ Early warnings (when trend emerges)
✓ Fewer false positives (trend filter)
✓ Catches black swans (acceleration detection)
""")
