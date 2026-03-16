"""
Shiller CAPE (Cyclically Adjusted Price-to-Earnings) Fetcher
Fetches CAPE data from multpl.com and provides analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class CAPEAnalysis:
    """CAPE analysis result"""
    current_cape: float
    cape_percentile: float  # Historical percentile (0-100)
    cape_level: str  # EXTREME, HIGH, ELEVATED, NORMAL, LOW
    historical_avg: float
    historical_median: float
    implied_return_10y: float  # Rough estimate based on CAPE
    date: str


class CAPEFetcher:
    """Fetch and analyze Shiller CAPE data"""

    # Historical CAPE reference points
    CAPE_THRESHOLDS = {
        'extreme': 35,    # Top ~5% historically
        'high': 28,       # Top ~15%
        'elevated': 22,   # Above average
        'normal': 15,     # Around historical average
        'low': 12         # Below average - attractive
    }

    # Historical stats (1881-2024)
    HISTORICAL_AVG = 17.6
    HISTORICAL_MEDIAN = 16.0

    def __init__(self):
        self.cape_data: Optional[pd.DataFrame] = None
        self.last_fetch: Optional[datetime] = None

    def fetch_cape_data(self, months: int = 120) -> Optional[pd.DataFrame]:
        """
        Fetch CAPE data from multpl.com

        Args:
            months: Number of months of history to fetch

        Returns:
            DataFrame with Date and CAPE values
        """
        try:
            url = 'https://www.multpl.com/shiller-pe/table/by-month'
            tables = pd.read_html(url)

            if not tables:
                print("Warning: No CAPE data found")
                return None

            df = tables[0]
            df.columns = ['Date', 'CAPE']

            # Parse dates
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
            df = df.sort_values('Date').reset_index(drop=True)

            # Keep last N months
            df = df.tail(months)

            self.cape_data = df
            self.last_fetch = datetime.now()

            return df

        except Exception as e:
            print(f"Error fetching CAPE data: {e}")
            return None

    def get_current_cape(self) -> Optional[float]:
        """Get the most recent CAPE value"""
        if self.cape_data is None:
            self.fetch_cape_data()

        if self.cape_data is not None and len(self.cape_data) > 0:
            return self.cape_data['CAPE'].iloc[-1]
        return None

    def calculate_percentile(self, cape_value: float) -> float:
        """
        Calculate historical percentile for a CAPE value
        Based on data from 1881-present

        Args:
            cape_value: CAPE value to evaluate

        Returns:
            Percentile (0-100)
        """
        # Historical CAPE distribution (approximate percentiles)
        # Based on 140+ years of data
        historical_percentiles = {
            10: 10.5,   # 10th percentile
            25: 12.5,   # 25th percentile
            50: 16.0,   # median
            75: 21.5,   # 75th percentile
            90: 27.0,   # 90th percentile
            95: 32.0,   # 95th percentile
            99: 40.0    # 99th percentile
        }

        if cape_value <= historical_percentiles[10]:
            return (cape_value / historical_percentiles[10]) * 10
        elif cape_value <= historical_percentiles[25]:
            return 10 + ((cape_value - historical_percentiles[10]) /
                        (historical_percentiles[25] - historical_percentiles[10])) * 15
        elif cape_value <= historical_percentiles[50]:
            return 25 + ((cape_value - historical_percentiles[25]) /
                        (historical_percentiles[50] - historical_percentiles[25])) * 25
        elif cape_value <= historical_percentiles[75]:
            return 50 + ((cape_value - historical_percentiles[50]) /
                        (historical_percentiles[75] - historical_percentiles[50])) * 25
        elif cape_value <= historical_percentiles[90]:
            return 75 + ((cape_value - historical_percentiles[75]) /
                        (historical_percentiles[90] - historical_percentiles[75])) * 15
        elif cape_value <= historical_percentiles[95]:
            return 90 + ((cape_value - historical_percentiles[90]) /
                        (historical_percentiles[95] - historical_percentiles[90])) * 5
        elif cape_value <= historical_percentiles[99]:
            return 95 + ((cape_value - historical_percentiles[95]) /
                        (historical_percentiles[99] - historical_percentiles[95])) * 4
        else:
            return min(99.9, 99 + (cape_value - historical_percentiles[99]) / 10)

    def get_cape_level(self, cape_value: float) -> str:
        """Determine CAPE level category"""
        if cape_value >= self.CAPE_THRESHOLDS['extreme']:
            return 'EXTREME'
        elif cape_value >= self.CAPE_THRESHOLDS['high']:
            return 'HIGH'
        elif cape_value >= self.CAPE_THRESHOLDS['elevated']:
            return 'ELEVATED'
        elif cape_value >= self.CAPE_THRESHOLDS['normal']:
            return 'NORMAL'
        else:
            return 'LOW'

    def estimate_10y_return(self, cape_value: float) -> float:
        """
        Estimate expected 10-year annualized return based on CAPE
        Based on historical relationship between CAPE and subsequent returns

        This is a rough estimate - actual returns vary significantly!

        Args:
            cape_value: Current CAPE

        Returns:
            Estimated 10-year annualized return (%)
        """
        # Approximate formula: Expected Return ≈ 1/CAPE + real growth
        # Historical real earnings growth ~1.5-2%
        earnings_yield = 100 / cape_value
        real_growth = 1.5
        inflation = 2.5  # assumed

        # Adjust for mean reversion tendency
        mean_reversion_factor = 0
        if cape_value > 25:
            mean_reversion_factor = -0.5 * (cape_value - 25) / 10
        elif cape_value < 15:
            mean_reversion_factor = 0.5 * (15 - cape_value) / 5

        estimated_return = earnings_yield + real_growth + mean_reversion_factor

        return round(estimated_return, 1)

    def analyze(self) -> Optional[CAPEAnalysis]:
        """
        Perform full CAPE analysis

        Returns:
            CAPEAnalysis object with all metrics
        """
        if self.cape_data is None:
            self.fetch_cape_data()

        if self.cape_data is None or len(self.cape_data) == 0:
            return None

        current_cape = self.cape_data['CAPE'].iloc[-1]
        current_date = self.cape_data['Date'].iloc[-1].strftime('%Y-%m-%d')

        return CAPEAnalysis(
            current_cape=current_cape,
            cape_percentile=self.calculate_percentile(current_cape),
            cape_level=self.get_cape_level(current_cape),
            historical_avg=self.HISTORICAL_AVG,
            historical_median=self.HISTORICAL_MEDIAN,
            implied_return_10y=self.estimate_10y_return(current_cape),
            date=current_date
        )

    def format_cape_text(self, analysis: CAPEAnalysis) -> str:
        """Format CAPE analysis as text for report"""
        level_emoji = {
            'EXTREME': '🔴',
            'HIGH': '🟠',
            'ELEVATED': '🟡',
            'NORMAL': '🟢',
            'LOW': '🟢'
        }.get(analysis.cape_level, '⚪')

        lines = [
            "SHILLER CAPE VALUATION",
            "-" * 40,
            f"Current CAPE: {analysis.current_cape:.1f} {level_emoji} {analysis.cape_level}",
            f"Historical Percentile: {analysis.cape_percentile:.0f}%",
            f"Historical Average: {analysis.historical_avg:.1f}",
            f"Historical Median: {analysis.historical_median:.1f}",
            f"Premium to Median: {((analysis.current_cape / analysis.historical_median) - 1) * 100:+.0f}%",
            "",
            f"Implied 10Y Return: ~{analysis.implied_return_10y:.1f}% p.a.",
            "",
            "CAPE Reference:",
            f"  > 35: EXTREME (top 5%)",
            f"  28-35: HIGH (top 15%)",
            f"  22-28: ELEVATED",
            f"  15-22: NORMAL",
            f"  < 15: LOW (attractive)",
        ]

        return "\n".join(lines)


if __name__ == "__main__":
    # Test CAPE fetcher
    fetcher = CAPEFetcher()

    print("Fetching CAPE data...")
    df = fetcher.fetch_cape_data(months=24)

    if df is not None:
        print(f"\nRecent CAPE values:")
        print(df.tail(12).to_string(index=False))

        print("\n" + "=" * 50)
        analysis = fetcher.analyze()
        if analysis:
            print(fetcher.format_cape_text(analysis))
