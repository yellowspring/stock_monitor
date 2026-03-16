"""
CFQ Model - Individual Stock Quick Evaluation
Cashflow × Quality × Price

A simple, fast valuation model that doesn't require 10-year projections or complex DCF.
Based on Warren Buffett's core principle: Real Cash / Price

Total Score = FCF Score + Quality Score + Price Score (0-15 scale)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class CFQScore:
    """CFQ evaluation result for a single stock"""
    symbol: str
    name: str
    price: float
    market_cap: float

    # FCF Component
    fcf_ttm: float
    fcf_yield: float
    fcf_score: int  # 1-5

    # Quality Component
    roic: Optional[float]
    debt_to_equity: Optional[float]
    quality_score: int  # 1-5
    quality_notes: List[str]

    # Price Component
    ev_to_fcf: Optional[float]
    price_score: int  # 1-5

    # Total
    total_score: int  # 3-15
    recommendation: str  # BUY, WATCH, AVOID, SKIP

    def __str__(self):
        return f"{self.symbol}: {self.total_score}/15 ({self.recommendation})"


class CFQEvaluator:
    """
    CFQ Model Evaluator

    Scores stocks on three dimensions:
    1. FCF Yield - How much cash flow per dollar invested
    2. Quality - Is this a compounding machine?
    3. Price Discipline - Are you paying too much?
    """

    # FCF Yield scoring thresholds
    FCF_THRESHOLDS = {
        5: 0.08,   # ≥ 8% = score 5
        4: 0.05,   # 5-8% = score 4
        3: 0.03,   # 3-5% = score 3
        2: 0.01,   # 1-3% = score 2
        1: 0.00,   # < 1% = score 1
    }

    # EV/FCF scoring thresholds
    PRICE_THRESHOLDS = {
        5: 12,    # ≤ 12 = score 5
        4: 18,    # 12-18 = score 4
        3: 25,    # 18-25 = score 3
        2: 35,    # 25-35 = score 2
        1: 999,   # > 35 = score 1
    }

    # Decision thresholds
    DECISION_THRESHOLDS = {
        'buy': 12,      # ≥ 12: Worth investigating / can build position
        'watch': 9,     # 9-11: Watch / small position
        'avoid': 6,     # 6-8: Price or quality issue
        'skip': 0,      # < 6: Skip entirely
    }

    def __init__(self):
        self.cache = {}

    def _get_fcf_score(self, fcf_yield: float) -> int:
        """Score FCF yield (1-5)"""
        if fcf_yield >= self.FCF_THRESHOLDS[5]:
            return 5
        elif fcf_yield >= self.FCF_THRESHOLDS[4]:
            return 4
        elif fcf_yield >= self.FCF_THRESHOLDS[3]:
            return 3
        elif fcf_yield >= self.FCF_THRESHOLDS[2]:
            return 2
        else:
            return 1

    def _get_price_score(self, ev_to_fcf: float) -> int:
        """Score EV/FCF (1-5)"""
        if ev_to_fcf is None or ev_to_fcf <= 0:
            return 1  # Can't calculate or negative FCF

        if ev_to_fcf <= self.PRICE_THRESHOLDS[5]:
            return 5
        elif ev_to_fcf <= self.PRICE_THRESHOLDS[4]:
            return 4
        elif ev_to_fcf <= self.PRICE_THRESHOLDS[3]:
            return 3
        elif ev_to_fcf <= self.PRICE_THRESHOLDS[2]:
            return 2
        else:
            return 1

    def _get_quality_score(self, info: dict) -> tuple:
        """
        Score quality factors (1-5)

        Returns: (score, notes)
        """
        score = 0
        notes = []

        # ROIC check (≥ 15% = +2)
        roic = info.get('returnOnEquity')  # Using ROE as proxy
        if roic is not None and roic >= 0.15:
            score += 2
            notes.append(f"ROIC/ROE: {roic*100:.1f}% ✓")
        elif roic is not None:
            notes.append(f"ROIC/ROE: {roic*100:.1f}%")

        # Debt check (manageable = +1)
        debt_to_equity = info.get('debtToEquity')
        if debt_to_equity is not None:
            if debt_to_equity < 100:  # < 1x D/E
                score += 1
                notes.append(f"D/E: {debt_to_equity:.0f}% ✓")
            else:
                notes.append(f"D/E: {debt_to_equity:.0f}% (high)")

        # Business stability (use profit margins as proxy)
        profit_margin = info.get('profitMargins')
        if profit_margin is not None and profit_margin > 0.10:
            score += 1
            notes.append(f"Margin: {profit_margin*100:.1f}% ✓")
        elif profit_margin is not None:
            notes.append(f"Margin: {profit_margin*100:.1f}%")

        # Moat indicator (use gross margin as proxy - high margins suggest pricing power)
        gross_margin = info.get('grossMargins')
        if gross_margin is not None and gross_margin > 0.40:
            score += 1
            notes.append(f"Gross: {gross_margin*100:.1f}% ✓")
        elif gross_margin is not None:
            notes.append(f"Gross: {gross_margin*100:.1f}%")

        # Ensure minimum score of 1
        return max(1, min(5, score)), notes

    def _get_recommendation(self, total_score: int) -> str:
        """Get recommendation based on total score"""
        if total_score >= self.DECISION_THRESHOLDS['buy']:
            return "BUY"
        elif total_score >= self.DECISION_THRESHOLDS['watch']:
            return "WATCH"
        elif total_score >= self.DECISION_THRESHOLDS['avoid']:
            return "AVOID"
        else:
            return "SKIP"

    def evaluate(self, symbol: str, name: str = None) -> Optional[CFQScore]:
        """
        Evaluate a single stock using CFQ model

        Args:
            symbol: Stock ticker
            name: Display name (optional, will use symbol if not provided)

        Returns:
            CFQScore object or None if data unavailable
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                print(f"Warning: No data for {symbol}")
                return None

            # Get basic info
            name = name or info.get('shortName', symbol)
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            market_cap = info.get('marketCap', 0)

            if market_cap == 0:
                print(f"Warning: No market cap for {symbol}")
                return None

            # Get FCF (try multiple sources)
            fcf_ttm = info.get('freeCashflow', 0)

            # If no FCF in info, try to calculate from cash flow statement
            if fcf_ttm == 0:
                try:
                    cf = ticker.cashflow
                    if cf is not None and len(cf) > 0:
                        # Get operating cash flow - capex
                        if 'Operating Cash Flow' in cf.index:
                            ocf = cf.loc['Operating Cash Flow'].iloc[0]
                        elif 'Total Cash From Operating Activities' in cf.index:
                            ocf = cf.loc['Total Cash From Operating Activities'].iloc[0]
                        else:
                            ocf = 0

                        if 'Capital Expenditure' in cf.index:
                            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
                        elif 'Capital Expenditures' in cf.index:
                            capex = abs(cf.loc['Capital Expenditures'].iloc[0])
                        else:
                            capex = 0

                        if ocf != 0:
                            fcf_ttm = ocf - capex
                except Exception:
                    pass

            # Calculate FCF Yield
            fcf_yield = fcf_ttm / market_cap if market_cap > 0 else 0
            fcf_score = self._get_fcf_score(fcf_yield)

            # Get Enterprise Value for EV/FCF
            enterprise_value = info.get('enterpriseValue', 0)
            if enterprise_value > 0 and fcf_ttm > 0:
                ev_to_fcf = enterprise_value / fcf_ttm
            else:
                ev_to_fcf = None

            price_score = self._get_price_score(ev_to_fcf)

            # Quality assessment
            quality_score, quality_notes = self._get_quality_score(info)

            # Total score
            total_score = fcf_score + quality_score + price_score
            recommendation = self._get_recommendation(total_score)

            return CFQScore(
                symbol=symbol,
                name=name,
                price=price,
                market_cap=market_cap,
                fcf_ttm=fcf_ttm,
                fcf_yield=fcf_yield,
                fcf_score=fcf_score,
                roic=info.get('returnOnEquity'),
                debt_to_equity=info.get('debtToEquity'),
                quality_score=quality_score,
                quality_notes=quality_notes,
                ev_to_fcf=ev_to_fcf,
                price_score=price_score,
                total_score=total_score,
                recommendation=recommendation
            )

        except Exception as e:
            print(f"Error evaluating {symbol}: {e}")
            return None

    def evaluate_multiple(self, stocks: List[tuple]) -> List[CFQScore]:
        """
        Evaluate multiple stocks

        Args:
            stocks: List of (symbol, name) tuples

        Returns:
            List of CFQScore objects, sorted by total score (highest first)
        """
        results = []
        for symbol, name in stocks:
            score = self.evaluate(symbol, name)
            if score:
                results.append(score)

        # Sort by total score (highest first)
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def format_scores_text(self, scores: List[CFQScore]) -> str:
        """Format CFQ scores as text for report"""
        if not scores:
            return "No CFQ scores available.\n"

        lines = []
        lines.append("CFQ STOCK VALUATION (Cashflow × Quality × Price)")
        lines.append("-" * 60)
        lines.append(f"{'Stock':<12} {'Price':>10} {'FCF':>4} {'Qual':>4} {'Price':>5} {'Total':>6} {'Action':>8}")
        lines.append("-" * 60)

        for s in scores:
            action_emoji = {
                'BUY': '✅',
                'WATCH': '👀',
                'AVOID': '⚠️',
                'SKIP': '❌'
            }.get(s.recommendation, '')

            lines.append(
                f"{s.name:<12} ${s.price:>8.2f} "
                f"{s.fcf_score:>4} {s.quality_score:>4} {s.price_score:>5} "
                f"{s.total_score:>5}/15 {action_emoji} {s.recommendation}"
            )

        # Add legend
        lines.append("")
        lines.append("Score Guide:")
        lines.append("  ≥12: BUY - Worth investigating / can build position")
        lines.append("  9-11: WATCH - Observe / small position only")
        lines.append("  6-8: AVOID - Price or quality concerns")
        lines.append("  <6: SKIP - Not investable")

        # Highlight top picks
        buy_stocks = [s for s in scores if s.recommendation == 'BUY']
        if buy_stocks:
            lines.append("")
            lines.append("💡 TOP PICKS (Score ≥ 12):")
            for s in buy_stocks:
                lines.append(f"   • {s.name} ({s.symbol}): {s.total_score}/15")
                lines.append(f"     FCF Yield: {s.fcf_yield*100:.1f}%, EV/FCF: {s.ev_to_fcf:.1f}x" if s.ev_to_fcf else f"     FCF Yield: {s.fcf_yield*100:.1f}%")

        return "\n".join(lines)

    def format_scores_html(self, scores: List[CFQScore]) -> str:
        """Format CFQ scores as HTML table"""
        if not scores:
            return "<p>No CFQ scores available.</p>"

        html = ['<table style="border-collapse: collapse; width: 100%;">']
        html.append('<tr style="background-color: #2c5282; color: white;">')
        html.append('<th style="padding: 8px;">Stock</th>')
        html.append('<th style="padding: 8px;">Price</th>')
        html.append('<th style="padding: 8px;">FCF</th>')
        html.append('<th style="padding: 8px;">Quality</th>')
        html.append('<th style="padding: 8px;">Price</th>')
        html.append('<th style="padding: 8px;">Total</th>')
        html.append('<th style="padding: 8px;">Action</th>')
        html.append('</tr>')

        for i, s in enumerate(scores):
            bg_color = "#f7fafc" if i % 2 == 0 else "#ffffff"

            action_color = {
                'BUY': '#276749',
                'WATCH': '#c05621',
                'AVOID': '#c53030',
                'SKIP': '#718096'
            }.get(s.recommendation, '#718096')

            html.append(f'<tr style="background-color: {bg_color};">')
            html.append(f'<td style="padding: 8px;"><b>{s.name}</b><br><small>{s.symbol}</small></td>')
            html.append(f'<td style="padding: 8px; text-align: right;">${s.price:.2f}</td>')
            html.append(f'<td style="padding: 8px; text-align: center;">{s.fcf_score}/5</td>')
            html.append(f'<td style="padding: 8px; text-align: center;">{s.quality_score}/5</td>')
            html.append(f'<td style="padding: 8px; text-align: center;">{s.price_score}/5</td>')
            html.append(f'<td style="padding: 8px; text-align: center; font-weight: bold;">{s.total_score}/15</td>')
            html.append(f'<td style="padding: 8px; text-align: center; color: {action_color}; font-weight: bold;">{s.recommendation}</td>')
            html.append('</tr>')

        html.append('</table>')

        return '\n'.join(html)


if __name__ == "__main__":
    # Test CFQ evaluator
    evaluator = CFQEvaluator()

    # Test with sample stocks
    stocks = [
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
        ("GOOGL", "Google"),
        ("NVDA", "NVIDIA"),
        ("TSLA", "Tesla"),
        ("META", "Meta"),
    ]

    print("Evaluating stocks with CFQ Model...")
    print("=" * 60)

    scores = evaluator.evaluate_multiple(stocks)

    print(evaluator.format_scores_text(scores))

    # Show detailed breakdown for top stock
    if scores:
        top = scores[0]
        print("\n" + "=" * 60)
        print(f"DETAILED: {top.name} ({top.symbol})")
        print("=" * 60)
        print(f"Price: ${top.price:.2f}")
        print(f"Market Cap: ${top.market_cap/1e9:.1f}B")
        print(f"\nFCF Analysis:")
        print(f"  TTM FCF: ${top.fcf_ttm/1e9:.2f}B")
        print(f"  FCF Yield: {top.fcf_yield*100:.1f}%")
        print(f"  FCF Score: {top.fcf_score}/5")
        print(f"\nQuality Analysis:")
        for note in top.quality_notes:
            print(f"  {note}")
        print(f"  Quality Score: {top.quality_score}/5")
        print(f"\nPrice Analysis:")
        if top.ev_to_fcf:
            print(f"  EV/FCF: {top.ev_to_fcf:.1f}x")
        print(f"  Price Score: {top.price_score}/5")
        print(f"\n{'='*30}")
        print(f"TOTAL SCORE: {top.total_score}/15")
        print(f"RECOMMENDATION: {top.recommendation}")
