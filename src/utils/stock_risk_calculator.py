"""
Individual Stock Risk Calculator
Calculates crash probability for individual stocks based on:
1. Market-wide crash probability (from the main model)
2. Stock's beta (sensitivity to market)
3. Stock's own volatility
4. Stock's recent performance relative to market
"""
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class StockRisk:
    """Risk assessment for a single stock"""
    symbol: str
    name: str
    price: float
    crash_probability: float  # 0-100
    risk_level: str  # HIGH, MODERATE, LOW
    beta: float
    volatility_30d: float
    relative_strength: float  # vs SPY
    change_1d: float
    change_5d: float
    distance_from_high: float  # % from 52-week high


class StockRiskCalculator:
    """Calculate crash risk for individual stocks"""

    def __init__(self, thresholds: Optional[Dict] = None):
        """
        Initialize calculator

        Args:
            thresholds: Risk thresholds (high_risk, moderate_risk, low_risk)
        """
        self.thresholds = thresholds or {
            'high_risk': 60,
            'moderate_risk': 40,
            'low_risk': 25
        }

    def calculate_stock_risk(
        self,
        symbol: str,
        name: str,
        market_crash_prob: float,
        lookback_days: int = 252
    ) -> Optional[StockRisk]:
        """
        Calculate crash risk for a single stock

        Args:
            symbol: Stock ticker
            name: Display name
            market_crash_prob: Market-wide crash probability (0-100)
            lookback_days: Days of history for calculations

        Returns:
            StockRisk object or None if data unavailable
        """
        try:
            # Fetch stock data
            stock = yf.Ticker(symbol)
            hist = stock.history(period=f"{lookback_days}d")

            if len(hist) < 60:
                print(f"Warning: Insufficient data for {symbol}")
                return None

            # Get SPY for comparison
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period=f"{lookback_days}d")

            # Align dates
            common_dates = hist.index.intersection(spy_hist.index)
            hist = hist.loc[common_dates]
            spy_hist = spy_hist.loc[common_dates]

            if len(hist) < 60:
                return None

            # Calculate returns
            stock_returns = hist['Close'].pct_change().dropna()
            spy_returns = spy_hist['Close'].pct_change().dropna()

            # Beta calculation (60-day rolling)
            cov = stock_returns.tail(60).cov(spy_returns.tail(60))
            var = spy_returns.tail(60).var()
            beta = cov / var if var > 0 else 1.0

            # 30-day volatility (annualized)
            volatility_30d = stock_returns.tail(30).std() * np.sqrt(252) * 100

            # Relative strength vs SPY (30-day)
            stock_return_30d = (hist['Close'].iloc[-1] / hist['Close'].iloc[-30] - 1) * 100
            spy_return_30d = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-30] - 1) * 100
            relative_strength = stock_return_30d - spy_return_30d

            # Current price
            price = hist['Close'].iloc[-1]

            # Recent changes
            change_1d = stock_returns.iloc[-1] * 100 if len(stock_returns) > 0 else 0
            change_5d = (hist['Close'].iloc[-1] / hist['Close'].iloc[-5] - 1) * 100 if len(hist) >= 5 else 0

            # Distance from 52-week high
            high_52w = hist['High'].max()
            distance_from_high = (price / high_52w - 1) * 100

            # Calculate stock-specific crash probability
            # Formula: Market probability * beta adjustment * volatility adjustment
            # Higher beta = higher risk, Higher volatility = higher risk
            beta_adjustment = max(0.5, min(2.0, beta))  # Clamp beta between 0.5 and 2.0
            vol_adjustment = 1 + (volatility_30d - 20) / 100  # Normalize around 20% vol
            vol_adjustment = max(0.8, min(1.5, vol_adjustment))

            # Relative strength adjustment (underperforming = higher risk)
            rs_adjustment = 1 - relative_strength / 100
            rs_adjustment = max(0.8, min(1.3, rs_adjustment))

            # Combined probability
            stock_crash_prob = market_crash_prob * beta_adjustment * vol_adjustment * rs_adjustment
            stock_crash_prob = max(0, min(100, stock_crash_prob))

            # Determine risk level
            if stock_crash_prob >= self.thresholds['high_risk']:
                risk_level = "HIGH"
            elif stock_crash_prob >= self.thresholds['moderate_risk']:
                risk_level = "MODERATE"
            elif stock_crash_prob <= self.thresholds['low_risk']:
                risk_level = "LOW"
            else:
                risk_level = "NORMAL"

            return StockRisk(
                symbol=symbol,
                name=name,
                price=price,
                crash_probability=stock_crash_prob,
                risk_level=risk_level,
                beta=beta,
                volatility_30d=volatility_30d,
                relative_strength=relative_strength,
                change_1d=change_1d,
                change_5d=change_5d,
                distance_from_high=distance_from_high
            )

        except Exception as e:
            print(f"Error calculating risk for {symbol}: {e}")
            return None

    def calculate_multiple_stocks(
        self,
        stocks: List[Tuple[str, str]],  # List of (symbol, name)
        market_crash_prob: float
    ) -> List[StockRisk]:
        """
        Calculate risk for multiple stocks

        Args:
            stocks: List of (symbol, name) tuples
            market_crash_prob: Market-wide crash probability

        Returns:
            List of StockRisk objects
        """
        results = []

        for symbol, name in stocks:
            risk = self.calculate_stock_risk(symbol, name, market_crash_prob)
            if risk:
                results.append(risk)

        # Sort by crash probability (highest first)
        results.sort(key=lambda x: x.crash_probability, reverse=True)

        return results

    def format_stock_risks_text(self, risks: List[StockRisk]) -> str:
        """Format stock risks as text for email"""
        if not risks:
            return "No individual stocks monitored.\n"

        lines = []
        lines.append("INDIVIDUAL STOCK RISK ASSESSMENT")
        lines.append("-" * 50)
        lines.append(f"{'Stock':<15} {'Price':>10} {'Risk':>8} {'Level':>10} {'Beta':>6}")
        lines.append("-" * 50)

        for risk in risks:
            level_emoji = {
                'HIGH': '🔴',
                'MODERATE': '🟡',
                'NORMAL': '🟢',
                'LOW': '🟢'
            }.get(risk.risk_level, '⚪')

            lines.append(
                f"{risk.name:<15} ${risk.price:>8.2f} {risk.crash_probability:>6.1f}% "
                f"{level_emoji} {risk.risk_level:<8} {risk.beta:>5.2f}"
            )

        # High risk warnings
        high_risk_stocks = [r for r in risks if r.risk_level == 'HIGH']
        if high_risk_stocks:
            lines.append("")
            lines.append("⚠️  HIGH RISK STOCKS:")
            for risk in high_risk_stocks:
                lines.append(f"   • {risk.name} ({risk.symbol}): {risk.crash_probability:.1f}%")
                lines.append(f"     Beta: {risk.beta:.2f}, Vol: {risk.volatility_30d:.1f}%, "
                           f"From High: {risk.distance_from_high:.1f}%")

        return "\n".join(lines)

    def format_stock_risks_html(self, risks: List[StockRisk]) -> str:
        """Format stock risks as HTML table"""
        if not risks:
            return "<p>No individual stocks monitored.</p>"

        html = ['<table style="border-collapse: collapse; width: 100%;">']
        html.append('<tr style="background-color: #2c5282; color: white;">')
        html.append('<th style="padding: 8px;">Stock</th>')
        html.append('<th style="padding: 8px;">Price</th>')
        html.append('<th style="padding: 8px;">Risk</th>')
        html.append('<th style="padding: 8px;">Level</th>')
        html.append('<th style="padding: 8px;">Beta</th>')
        html.append('<th style="padding: 8px;">5D Change</th>')
        html.append('</tr>')

        for i, risk in enumerate(risks):
            bg_color = "#f7fafc" if i % 2 == 0 else "#ffffff"

            level_color = {
                'HIGH': '#c53030',
                'MODERATE': '#c05621',
                'NORMAL': '#276749',
                'LOW': '#276749'
            }.get(risk.risk_level, '#718096')

            html.append(f'<tr style="background-color: {bg_color};">')
            html.append(f'<td style="padding: 8px;"><b>{risk.name}</b><br><small>{risk.symbol}</small></td>')
            html.append(f'<td style="padding: 8px; text-align: right;">${risk.price:.2f}</td>')
            html.append(f'<td style="padding: 8px; text-align: right;">{risk.crash_probability:.1f}%</td>')
            html.append(f'<td style="padding: 8px; text-align: center; color: {level_color}; font-weight: bold;">{risk.risk_level}</td>')
            html.append(f'<td style="padding: 8px; text-align: right;">{risk.beta:.2f}</td>')
            change_color = '#c53030' if risk.change_5d < 0 else '#276749'
            html.append(f'<td style="padding: 8px; text-align: right; color: {change_color};">{risk.change_5d:+.1f}%</td>')
            html.append('</tr>')

        html.append('</table>')

        return '\n'.join(html)


if __name__ == "__main__":
    # Test stock risk calculator
    calculator = StockRiskCalculator()

    # Test with sample stocks
    stocks = [
        ("TSLA", "Tesla"),
        ("NVDA", "NVIDIA"),
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
    ]

    # Assume market crash probability is 15%
    market_prob = 15.0

    print(f"Market Crash Probability: {market_prob:.1f}%\n")

    risks = calculator.calculate_multiple_stocks(stocks, market_prob)

    print(calculator.format_stock_risks_text(risks))
