"""
Crypto Trend Analyzer - BTC/ETH Trend Detection & Prediction
多时间周期趋势识别 + 技术指标信号

Components:
1. Multi-timeframe Trend: Daily, Weekly, Monthly MA alignment
2. Momentum: RSI, MACD
3. Trend Strength: ADX-like measure
4. Signal Summary: BULLISH / BEARISH / NEUTRAL with confidence
"""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta


@dataclass
class TrendSignal:
    """Individual timeframe trend signal"""
    timeframe: str          # daily, weekly, monthly
    trend: str              # BULLISH, BEARISH, NEUTRAL
    strength: float         # 0-100, how strong the trend is
    price_vs_ma: float      # % above/below key MA
    ma_slope: float         # MA slope (momentum)
    note: str               # Brief description


@dataclass
class MomentumSignal:
    """Momentum indicator signals"""
    rsi_14: float           # RSI(14)
    rsi_signal: str         # OVERSOLD, NEUTRAL, OVERBOUGHT
    macd_signal: str        # BULLISH, BEARISH, NEUTRAL
    macd_histogram: float   # MACD histogram value
    momentum_score: int     # -2 to +2 aggregate


@dataclass
class CryptoTrend:
    """Complete trend analysis for a crypto asset"""
    symbol: str             # BTC-USD, ETH-USD
    name: str               # Bitcoin, Ethereum
    timestamp: str

    # Current price info
    price: float
    change_24h: float       # % change
    change_7d: float        # % change
    change_30d: float       # % change

    # Multi-timeframe trends
    daily_trend: TrendSignal
    weekly_trend: TrendSignal
    monthly_trend: TrendSignal

    # Momentum
    momentum: MomentumSignal

    # Overall assessment
    overall_trend: str      # STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR
    trend_score: int        # -100 to +100
    confidence: str         # HIGH, MEDIUM, LOW
    prediction: str         # Chinese description of expected direction
    key_levels: Dict[str, float]  # Support/Resistance levels

    def __str__(self):
        arrow = {'STRONG_BULL': '⬆️⬆️', 'BULL': '⬆️', 'NEUTRAL': '➡️',
                 'BEAR': '⬇️', 'STRONG_BEAR': '⬇️⬇️'}.get(self.overall_trend, '➡️')
        return f"{self.name}: {arrow} {self.overall_trend} ({self.trend_score:+d})"


class CryptoTrendAnalyzer:
    """
    Analyzes crypto trends using technical analysis

    Key indicators:
    - EMA 20/50/200 alignment (Golden/Death cross)
    - RSI(14) for overbought/oversold
    - MACD for momentum
    - Price action vs key MAs
    """

    SYMBOLS = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
    }

    def __init__(self):
        self.cache = {}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series,
                        fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD indicator"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _get_trend_signal(self, prices: pd.Series, timeframe: str) -> TrendSignal:
        """
        Analyze trend for a specific timeframe

        Uses EMA alignment and slope with timeframe-appropriate periods:
        - Daily: 20/50/200 EMA
        - Weekly: 10/20/50 EMA (~50/100/250 daily equivalent)
        - Monthly: 6/12/24 EMA (~130/260/520 daily equivalent)
        """
        # Timeframe-specific MA periods
        ma_config = {
            'daily': {'short': 20, 'mid': 50, 'long': 200, 'min_data': 200, 'slope_period': 20},
            'weekly': {'short': 10, 'mid': 20, 'long': 50, 'min_data': 50, 'slope_period': 4},
            'monthly': {'short': 6, 'mid': 12, 'long': 24, 'min_data': 24, 'slope_period': 3},
        }
        config = ma_config.get(timeframe, ma_config['daily'])

        if len(prices) < config['min_data']:
            return TrendSignal(
                timeframe=timeframe,
                trend='NEUTRAL',
                strength=0,
                price_vs_ma=0,
                ma_slope=0,
                note=f'数据不足 ({len(prices)}/{config["min_data"]})'
            )

        current_price = prices.iloc[-1]

        # Calculate EMAs with timeframe-appropriate periods
        ema_short = prices.ewm(span=config['short'], adjust=False).mean()
        ema_mid = prices.ewm(span=config['mid'], adjust=False).mean()
        ema_long = prices.ewm(span=config['long'], adjust=False).mean()

        # Current values
        ema_short_now = ema_short.iloc[-1]
        ema_mid_now = ema_mid.iloc[-1]
        ema_long_now = ema_long.iloc[-1]

        # Price vs mid EMA
        price_vs_ma = ((current_price / ema_mid_now) - 1) * 100

        # MA slope
        slope_period = config['slope_period']
        if len(ema_mid) >= slope_period:
            ma_slope = ((ema_mid_now / ema_mid.iloc[-slope_period]) - 1) * 100
        else:
            ma_slope = 0

        # Determine trend based on EMA alignment
        # Bullish: Price > EMA_short > EMA_mid > EMA_long
        # Bearish: Price < EMA_short < EMA_mid < EMA_long
        bullish_points = 0
        if current_price > ema_short_now:
            bullish_points += 1
        if current_price > ema_mid_now:
            bullish_points += 1
        if current_price > ema_long_now:
            bullish_points += 1
        if ema_short_now > ema_mid_now:
            bullish_points += 1
        if ema_mid_now > ema_long_now:
            bullish_points += 1

        # Trend determination
        if bullish_points >= 4:
            trend = 'BULLISH'
            strength = min(100, bullish_points * 20)
            note = f'价格在关键均线之上，均线多头排列'
        elif bullish_points <= 1:
            trend = 'BEARISH'
            strength = min(100, (5 - bullish_points) * 20)
            note = f'价格在关键均线之下，均线空头排列'
        else:
            trend = 'NEUTRAL'
            strength = 50
            note = f'均线交织，趋势不明朗'

        return TrendSignal(
            timeframe=timeframe,
            trend=trend,
            strength=strength,
            price_vs_ma=price_vs_ma,
            ma_slope=ma_slope,
            note=note
        )

    def _get_momentum_signal(self, prices: pd.Series) -> MomentumSignal:
        """Calculate momentum indicators"""
        # RSI
        rsi = self._calculate_rsi(prices)
        rsi_14 = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50

        if rsi_14 < 30:
            rsi_signal = 'OVERSOLD'
        elif rsi_14 > 70:
            rsi_signal = 'OVERBOUGHT'
        else:
            rsi_signal = 'NEUTRAL'

        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(prices)
        macd_hist = histogram.iloc[-1] if not np.isnan(histogram.iloc[-1]) else 0
        macd_hist_prev = histogram.iloc[-2] if len(histogram) > 1 and not np.isnan(histogram.iloc[-2]) else 0

        # MACD signal based on histogram direction
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            macd_signal = 'BULLISH'
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            macd_signal = 'BEARISH'
        else:
            macd_signal = 'NEUTRAL'

        # Aggregate momentum score (-2 to +2)
        momentum_score = 0
        if rsi_signal == 'OVERSOLD':
            momentum_score += 1  # Potential bounce
        elif rsi_signal == 'OVERBOUGHT':
            momentum_score -= 1  # Potential pullback

        if macd_signal == 'BULLISH':
            momentum_score += 1
        elif macd_signal == 'BEARISH':
            momentum_score -= 1

        return MomentumSignal(
            rsi_14=rsi_14,
            rsi_signal=rsi_signal,
            macd_signal=macd_signal,
            macd_histogram=macd_hist,
            momentum_score=momentum_score
        )

    def _calculate_key_levels(self, prices: pd.Series) -> Dict[str, float]:
        """Calculate support and resistance levels"""
        current = prices.iloc[-1]
        high_52w = prices.tail(252).max() if len(prices) >= 252 else prices.max()
        low_52w = prices.tail(252).min() if len(prices) >= 252 else prices.min()

        # Recent swing levels (last 30 days)
        recent = prices.tail(30)
        recent_high = recent.max()
        recent_low = recent.min()

        # Key MAs as dynamic support/resistance
        ema_50 = prices.ewm(span=50, adjust=False).mean().iloc[-1]
        ema_200 = prices.ewm(span=200, adjust=False).mean().iloc[-1]

        return {
            '52w_high': high_52w,
            '52w_low': low_52w,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'current': current
        }

    def analyze(self, asset: str = 'BTC') -> Optional[CryptoTrend]:
        """
        Perform complete trend analysis for a crypto asset

        Args:
            asset: 'BTC' or 'ETH'

        Returns:
            CryptoTrend object with full analysis
        """
        symbol = self.SYMBOLS.get(asset.upper(), f'{asset.upper()}-USD')
        name = {'BTC': 'Bitcoin', 'ETH': 'Ethereum'}.get(asset.upper(), asset)

        try:
            # Fetch data - need enough for 200-day MA
            ticker = yf.Ticker(symbol)

            # Daily data for detailed analysis
            daily = ticker.history(period='2y')
            if len(daily) < 50:
                print(f"Warning: Insufficient data for {symbol}")
                return None

            prices_daily = daily['Close']

            # Weekly data (resample from daily)
            prices_weekly = prices_daily.resample('W-SUN').last().dropna()

            # Monthly data (resample from daily)
            prices_monthly = prices_daily.resample('ME').last().dropna()

            # Current price and changes
            current_price = prices_daily.iloc[-1]

            # Calculate changes
            change_24h = 0
            change_7d = 0
            change_30d = 0

            if len(prices_daily) >= 2:
                change_24h = ((current_price / prices_daily.iloc[-2]) - 1) * 100
            if len(prices_daily) >= 7:
                change_7d = ((current_price / prices_daily.iloc[-7]) - 1) * 100
            if len(prices_daily) >= 30:
                change_30d = ((current_price / prices_daily.iloc[-30]) - 1) * 100

            # Multi-timeframe trend analysis
            daily_trend = self._get_trend_signal(prices_daily, 'daily')
            weekly_trend = self._get_trend_signal(prices_weekly, 'weekly')
            monthly_trend = self._get_trend_signal(prices_monthly, 'monthly')

            # Momentum analysis (on daily)
            momentum = self._get_momentum_signal(prices_daily)

            # Key levels
            key_levels = self._calculate_key_levels(prices_daily)

            # Overall trend score (-100 to +100)
            trend_score = 0

            # Timeframe weights: Daily 20%, Weekly 40%, Monthly 40%
            trend_map = {'BULLISH': 1, 'NEUTRAL': 0, 'BEARISH': -1}
            trend_score += trend_map.get(daily_trend.trend, 0) * 20
            trend_score += trend_map.get(weekly_trend.trend, 0) * 40
            trend_score += trend_map.get(monthly_trend.trend, 0) * 40

            # Add momentum contribution (-20 to +20)
            trend_score += momentum.momentum_score * 10

            # Determine overall trend
            if trend_score >= 60:
                overall_trend = 'STRONG_BULL'
                prediction = '强势上升趋势，多周期共振看涨'
            elif trend_score >= 20:
                overall_trend = 'BULL'
                prediction = '上升趋势中，短期可能有回调但方向向上'
            elif trend_score <= -60:
                overall_trend = 'STRONG_BEAR'
                prediction = '强势下降趋势，多周期共振看跌'
            elif trend_score <= -20:
                overall_trend = 'BEAR'
                prediction = '下降趋势中，反弹可能是卖出机会'
            else:
                overall_trend = 'NEUTRAL'
                prediction = '趋势不明朗，建议观望等待方向明确'

            # Confidence based on timeframe alignment
            trends = [daily_trend.trend, weekly_trend.trend, monthly_trend.trend]
            if trends.count(trends[0]) == 3:  # All same
                confidence = 'HIGH'
            elif trends.count('NEUTRAL') >= 2:
                confidence = 'LOW'
            else:
                confidence = 'MEDIUM'

            return CryptoTrend(
                symbol=symbol,
                name=name,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                price=current_price,
                change_24h=change_24h,
                change_7d=change_7d,
                change_30d=change_30d,
                daily_trend=daily_trend,
                weekly_trend=weekly_trend,
                monthly_trend=monthly_trend,
                momentum=momentum,
                overall_trend=overall_trend,
                trend_score=trend_score,
                confidence=confidence,
                prediction=prediction,
                key_levels=key_levels
            )

        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return None

    def analyze_all(self) -> List[CryptoTrend]:
        """Analyze all tracked crypto assets"""
        results = []
        for asset in ['BTC', 'ETH']:
            trend = self.analyze(asset)
            if trend:
                results.append(trend)
        return results

    def format_trend_text(self, trends: List[CryptoTrend]) -> str:
        """Format trend analysis as text for report"""
        if not trends:
            return "No crypto trend data available.\n"

        lines = []
        lines.append("₿ CRYPTO TREND ANALYSIS (加密货币趋势分析)")
        lines.append("=" * 70)

        for t in trends:
            arrow = {'STRONG_BULL': '⬆️⬆️', 'BULL': '⬆️', 'NEUTRAL': '➡️',
                     'BEAR': '⬇️', 'STRONG_BEAR': '⬇️⬇️'}.get(t.overall_trend, '➡️')

            lines.append(f"\n{t.name} ({t.symbol})")
            lines.append("-" * 50)
            lines.append(f"  Price: ${t.price:,.2f}")
            lines.append(f"  24h: {t.change_24h:+.1f}%  |  7d: {t.change_7d:+.1f}%  |  30d: {t.change_30d:+.1f}%")
            lines.append("")
            lines.append(f"  Overall: {arrow} {t.overall_trend} (Score: {t.trend_score:+d}, Confidence: {t.confidence})")
            lines.append(f"  预测: {t.prediction}")
            lines.append("")

            # Timeframe breakdown
            lines.append("  Timeframe Trends:")
            for tf, trend in [('Daily', t.daily_trend), ('Weekly', t.weekly_trend), ('Monthly', t.monthly_trend)]:
                tf_arrow = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(trend.trend, '⚪')
                lines.append(f"    {tf:<8}: {tf_arrow} {trend.trend:<8} | Price vs MA: {trend.price_vs_ma:+.1f}%")

            # Momentum
            lines.append("")
            lines.append("  Momentum:")
            rsi_emoji = {'OVERSOLD': '🟢', 'NEUTRAL': '🟡', 'OVERBOUGHT': '🔴'}.get(t.momentum.rsi_signal, '⚪')
            macd_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(t.momentum.macd_signal, '⚪')
            lines.append(f"    RSI(14): {t.momentum.rsi_14:.1f} {rsi_emoji} {t.momentum.rsi_signal}")
            lines.append(f"    MACD:    {macd_emoji} {t.momentum.macd_signal}")

            # Key levels
            lines.append("")
            lines.append("  Key Levels:")
            lines.append(f"    52w High: ${t.key_levels['52w_high']:,.0f}  ({((t.price/t.key_levels['52w_high'])-1)*100:+.1f}% from high)")
            lines.append(f"    EMA 50:   ${t.key_levels['ema_50']:,.0f}")
            lines.append(f"    EMA 200:  ${t.key_levels['ema_200']:,.0f}")
            lines.append(f"    52w Low:  ${t.key_levels['52w_low']:,.0f}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("Note: Trend Score = Daily(20%) + Weekly(40%) + Monthly(40%) + Momentum")
        lines.append("  Score > +60: STRONG_BULL | +20~+60: BULL | -20~+20: NEUTRAL")
        lines.append("  Score < -60: STRONG_BEAR | -60~-20: BEAR")

        return "\n".join(lines)


def get_crypto_trends() -> List[CryptoTrend]:
    """Quick function to get current crypto trends"""
    analyzer = CryptoTrendAnalyzer()
    return analyzer.analyze_all()


if __name__ == "__main__":
    print("=" * 70)
    print("CRYPTO TREND ANALYSIS")
    print("=" * 70)

    analyzer = CryptoTrendAnalyzer()
    trends = analyzer.analyze_all()

    print(analyzer.format_trend_text(trends))
