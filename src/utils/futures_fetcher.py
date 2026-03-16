"""
Futures Premium/Discount Fetcher
Calculates the premium/discount of index futures (ES, NQ) relative to spot prices (SPY, QQQ)

Premium (Contango): Futures > Spot - typically indicates bullish sentiment
Discount (Backwardation): Futures < Spot - typically indicates bearish/risk-off sentiment
"""
import yfinance as yf
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import pandas as pd


@dataclass
class FuturesPremium:
    """Futures premium/discount data"""
    # Identifiers
    futures_symbol: str  # ES=F, NQ=F
    spot_symbol: str     # SPY, QQQ
    index_name: str      # S&P 500, Nasdaq-100

    # Prices
    futures_price: float
    spot_price: float

    # Premium/Discount
    premium_points: float   # Futures - Spot (in points)
    premium_pct: float      # (Futures - Spot) / Spot * 100

    # Interpretation
    signal: str             # BULLISH, NEUTRAL, BEARISH
    interpretation: str     # Chinese description

    # Metadata
    timestamp: str

    def __str__(self):
        sign = "+" if self.premium_pct > 0 else ""
        return f"{self.index_name}: {sign}{self.premium_pct:.2f}% ({self.signal})"


@dataclass
class FuturesData:
    """Combined futures data for all tracked indices"""
    sp500: Optional[FuturesPremium]  # ES vs SPY
    nasdaq: Optional[FuturesPremium]  # NQ vs QQQ
    timestamp: str

    # Aggregate signal
    overall_signal: str  # BULLISH, NEUTRAL, BEARISH
    overall_interpretation: str

    def __str__(self):
        parts = []
        if self.sp500:
            parts.append(str(self.sp500))
        if self.nasdaq:
            parts.append(str(self.nasdaq))
        return " | ".join(parts) if parts else "No futures data"


class FuturesFetcher:
    """
    Fetches and analyzes futures premium/discount

    Key Symbols:
    - ES=F: E-mini S&P 500 Futures (CME)
    - NQ=F: E-mini Nasdaq-100 Futures (CME)
    - YM=F: E-mini Dow Futures (CBOT)
    - RTY=F: E-mini Russell 2000 Futures (CME)

    Spot ETFs:
    - SPY: S&P 500 ETF
    - QQQ: Nasdaq-100 ETF
    - DIA: Dow 30 ETF
    - IWM: Russell 2000 ETF
    """

    # Futures to Spot mapping
    FUTURES_MAP = {
        'ES=F': {'spot': 'SPY', 'name': 'S&P 500', 'multiplier': 10.0},  # SPY is 1/10 of S&P 500
        'NQ=F': {'spot': 'QQQ', 'name': 'Nasdaq-100', 'multiplier': 40.0},  # QQQ is ~1/40 of Nasdaq-100
    }

    # Premium thresholds (in %)
    PREMIUM_THRESHOLDS = {
        'strong_bullish': 0.3,    # >0.3% premium
        'bullish': 0.1,           # 0.1-0.3% premium
        'neutral_high': 0.05,     # 0.05-0.1%
        'neutral_low': -0.05,     # -0.05 to 0.05%
        'bearish': -0.1,          # -0.1 to -0.05%
        'strong_bearish': -0.3,   # < -0.3%
    }

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache

    def _get_signal(self, premium_pct: float) -> Tuple[str, str]:
        """
        Determine signal and interpretation based on premium percentage

        Returns:
            Tuple of (signal, interpretation)
        """
        if premium_pct > self.PREMIUM_THRESHOLDS['strong_bullish']:
            return 'BULLISH', '期货溢价明显，市场情绪偏乐观'
        elif premium_pct > self.PREMIUM_THRESHOLDS['bullish']:
            return 'BULLISH', '期货小幅溢价，情绪中性偏多'
        elif premium_pct > self.PREMIUM_THRESHOLDS['neutral_high']:
            return 'NEUTRAL', '期货接近平价，情绪中性'
        elif premium_pct > self.PREMIUM_THRESHOLDS['neutral_low']:
            return 'NEUTRAL', '期现基差极小，无明显方向'
        elif premium_pct > self.PREMIUM_THRESHOLDS['bearish']:
            return 'NEUTRAL', '期货小幅折价，情绪中性偏空'
        elif premium_pct > self.PREMIUM_THRESHOLDS['strong_bearish']:
            return 'BEARISH', '期货折价，市场存在避险情绪'
        else:
            return 'BEARISH', '期货深度折价，市场恐慌/极度避险'

    def fetch_futures_premium(self, futures_symbol: str = 'ES=F') -> Optional[FuturesPremium]:
        """
        Fetch futures premium/discount for a single futures contract

        Args:
            futures_symbol: Futures ticker (e.g., 'ES=F', 'NQ=F')

        Returns:
            FuturesPremium object or None if data unavailable
        """
        if futures_symbol not in self.FUTURES_MAP:
            print(f"Warning: Unknown futures symbol {futures_symbol}")
            return None

        mapping = self.FUTURES_MAP[futures_symbol]
        spot_symbol = mapping['spot']
        index_name = mapping['name']
        multiplier = mapping['multiplier']

        try:
            # Fetch futures price
            futures_ticker = yf.Ticker(futures_symbol)
            futures_info = futures_ticker.info
            futures_price = futures_info.get('regularMarketPrice') or futures_info.get('previousClose')

            if not futures_price:
                # Try history as fallback
                hist = futures_ticker.history(period='1d')
                if len(hist) > 0:
                    futures_price = hist['Close'].iloc[-1]

            if not futures_price:
                print(f"Warning: No price data for {futures_symbol}")
                return None

            # Fetch spot price
            spot_ticker = yf.Ticker(spot_symbol)
            spot_info = spot_ticker.info
            spot_price = spot_info.get('regularMarketPrice') or spot_info.get('previousClose')

            if not spot_price:
                hist = spot_ticker.history(period='1d')
                if len(hist) > 0:
                    spot_price = hist['Close'].iloc[-1]

            if not spot_price:
                print(f"Warning: No price data for {spot_symbol}")
                return None

            # Convert spot price to index-equivalent
            # SPY ~= S&P 500 / 10, QQQ ~= Nasdaq-100 / 40
            spot_index_equiv = spot_price * multiplier

            # Calculate premium/discount
            premium_points = futures_price - spot_index_equiv
            premium_pct = (premium_points / spot_index_equiv) * 100

            # Get signal
            signal, interpretation = self._get_signal(premium_pct)

            return FuturesPremium(
                futures_symbol=futures_symbol,
                spot_symbol=spot_symbol,
                index_name=index_name,
                futures_price=futures_price,
                spot_price=spot_price,
                premium_points=premium_points,
                premium_pct=premium_pct,
                signal=signal,
                interpretation=interpretation,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

        except Exception as e:
            print(f"Error fetching {futures_symbol}: {e}")
            return None

    def fetch_all_futures(self) -> FuturesData:
        """
        Fetch premium/discount for all tracked futures

        Returns:
            FuturesData object with all futures data
        """
        sp500 = self.fetch_futures_premium('ES=F')
        nasdaq = self.fetch_futures_premium('NQ=F')

        # Determine overall signal
        signals = []
        if sp500:
            signals.append(sp500.signal)
        if nasdaq:
            signals.append(nasdaq.signal)

        if not signals:
            overall_signal = 'UNKNOWN'
            overall_interpretation = '无法获取期货数据'
        else:
            bullish_count = signals.count('BULLISH')
            bearish_count = signals.count('BEARISH')

            if bullish_count > bearish_count:
                overall_signal = 'BULLISH'
                overall_interpretation = '期货整体溢价，市场情绪偏乐观'
            elif bearish_count > bullish_count:
                overall_signal = 'BEARISH'
                overall_interpretation = '期货整体折价，市场存在避险情绪'
            else:
                overall_signal = 'NEUTRAL'
                overall_interpretation = '期货信号中性，无明显方向'

        return FuturesData(
            sp500=sp500,
            nasdaq=nasdaq,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            overall_signal=overall_signal,
            overall_interpretation=overall_interpretation
        )

    def format_futures_text(self, data: FuturesData) -> str:
        """Format futures data as text for report"""
        lines = []
        lines.append("📈 FUTURES PREMIUM/DISCOUNT (期货溢价/折价)")
        lines.append("-" * 60)
        lines.append(f"{'Index':<12} {'Futures':>10} {'Spot×M':>10} {'Premium':>10} {'Signal':>10}")
        lines.append("-" * 60)

        if data.sp500:
            fp = data.sp500
            spot_equiv = fp.spot_price * self.FUTURES_MAP['ES=F']['multiplier']
            premium_str = f"{fp.premium_pct:+.2f}%"
            signal_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(fp.signal, '⚪')
            lines.append(
                f"{'S&P 500':<12} {fp.futures_price:>10.2f} {spot_equiv:>10.2f} "
                f"{premium_str:>10} {signal_emoji} {fp.signal}"
            )

        if data.nasdaq:
            fp = data.nasdaq
            spot_equiv = fp.spot_price * self.FUTURES_MAP['NQ=F']['multiplier']
            premium_str = f"{fp.premium_pct:+.2f}%"
            signal_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(fp.signal, '⚪')
            lines.append(
                f"{'Nasdaq-100':<12} {fp.futures_price:>10.2f} {spot_equiv:>10.2f} "
                f"{premium_str:>10} {signal_emoji} {fp.signal}"
            )

        if not data.sp500 and not data.nasdaq:
            lines.append("  No futures data available")

        # Overall interpretation
        lines.append("")
        overall_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴', 'UNKNOWN': '⚪'}.get(data.overall_signal, '⚪')
        lines.append(f"Overall Signal: {overall_emoji} {data.overall_signal}")
        lines.append(f"  {data.overall_interpretation}")

        # Add explanation
        lines.append("")
        lines.append("Note: Premium = (Futures - Spot×Multiplier) / Spot×Multiplier")
        lines.append("  • Contango (溢价) > 0: 通常表示市场看涨")
        lines.append("  • Backwardation (折价) < 0: 通常表示避险/看跌情绪")

        return "\n".join(lines)

    def format_futures_html(self, data: FuturesData) -> str:
        """Format futures data as HTML for email"""
        html = ['<table style="border-collapse: collapse; width: 100%; margin: 10px 0;">']
        html.append('<tr style="background-color: #2c5282; color: white;">')
        html.append('<th style="padding: 8px;">Index</th>')
        html.append('<th style="padding: 8px;">Futures</th>')
        html.append('<th style="padding: 8px;">Spot Equiv</th>')
        html.append('<th style="padding: 8px;">Premium</th>')
        html.append('<th style="padding: 8px;">Signal</th>')
        html.append('</tr>')

        futures_list = []
        if data.sp500:
            futures_list.append(('S&P 500 (ES)', data.sp500, 'ES=F'))
        if data.nasdaq:
            futures_list.append(('Nasdaq-100 (NQ)', data.nasdaq, 'NQ=F'))

        for i, (name, fp, sym) in enumerate(futures_list):
            bg_color = "#f7fafc" if i % 2 == 0 else "#ffffff"
            spot_equiv = fp.spot_price * self.FUTURES_MAP[sym]['multiplier']
            sign = "+" if fp.premium_pct > 0 else ""

            signal_color = {
                'BULLISH': '#276749',
                'NEUTRAL': '#c05621',
                'BEARISH': '#c53030'
            }.get(fp.signal, '#718096')

            html.append(f'<tr style="background-color: {bg_color};">')
            html.append(f'<td style="padding: 8px;">{name}</td>')
            html.append(f'<td style="padding: 8px; text-align: right;">{fp.futures_price:,.2f}</td>')
            html.append(f'<td style="padding: 8px; text-align: right;">{spot_equiv:,.2f}</td>')
            html.append(f'<td style="padding: 8px; text-align: right;">{sign}{fp.premium_pct:.2f}%</td>')
            html.append(f'<td style="padding: 8px; text-align: center; color: {signal_color}; font-weight: bold;">{fp.signal}</td>')
            html.append('</tr>')

        html.append('</table>')

        # Add overall signal
        overall_color = {
            'BULLISH': '#276749',
            'NEUTRAL': '#c05621',
            'BEARISH': '#c53030',
            'UNKNOWN': '#718096'
        }.get(data.overall_signal, '#718096')

        html.append(f'<p style="margin-top: 10px;"><strong>Overall: </strong>')
        html.append(f'<span style="color: {overall_color}; font-weight: bold;">{data.overall_signal}</span>')
        html.append(f' - {data.overall_interpretation}</p>')

        return '\n'.join(html)


# Convenience function
def get_futures_premium() -> FuturesData:
    """Quick function to get current futures premium data"""
    fetcher = FuturesFetcher()
    return fetcher.fetch_all_futures()


if __name__ == "__main__":
    print("=" * 60)
    print("FUTURES PREMIUM/DISCOUNT ANALYSIS")
    print("=" * 60)

    fetcher = FuturesFetcher()
    data = fetcher.fetch_all_futures()

    print()
    print(fetcher.format_futures_text(data))

    # Show detailed data
    print()
    print("=" * 60)
    print("DETAILED DATA")
    print("=" * 60)

    if data.sp500:
        fp = data.sp500
        print(f"\nS&P 500 (ES=F vs SPY):")
        print(f"  Futures Price: {fp.futures_price:,.2f}")
        print(f"  Spot Price (SPY): ${fp.spot_price:.2f}")
        print(f"  Spot Index Equivalent: {fp.spot_price * 10:,.2f}")
        print(f"  Premium Points: {fp.premium_points:+.2f}")
        print(f"  Premium %: {fp.premium_pct:+.3f}%")
        print(f"  Signal: {fp.signal}")
        print(f"  {fp.interpretation}")

    if data.nasdaq:
        fp = data.nasdaq
        print(f"\nNasdaq-100 (NQ=F vs QQQ):")
        print(f"  Futures Price: {fp.futures_price:,.2f}")
        print(f"  Spot Price (QQQ): ${fp.spot_price:.2f}")
        print(f"  Spot Index Equivalent: {fp.spot_price * 40:,.2f}")
        print(f"  Premium Points: {fp.premium_points:+.2f}")
        print(f"  Premium %: {fp.premium_pct:+.3f}%")
        print(f"  Signal: {fp.signal}")
        print(f"  {fp.interpretation}")
