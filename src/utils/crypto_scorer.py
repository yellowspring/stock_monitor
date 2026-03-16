"""
Crypto Entry Scorer - BTC/ETH Entry Scoring System (0-100)

Evaluates entry timing for BTC and ETH based on:
1. Valuation (40 pts): MVRV + Realized Price ratio
2. Trend (20 pts): 200-week MA position + Weekly RSI
3. Sentiment (20 pts): Fear & Greed + Narrative
4. Macro (20 pts): Rate regime + Risk appetite

Higher score = better long-term expected return/risk ratio (not a price prediction)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from enum import Enum


class RateRegime(Enum):
    EASING = "easing"           # Clear rate cuts / QE / liquidity improvement
    PAUSE = "pause"             # Rate pause / neutral
    TIGHTENING = "tightening"   # Rate hikes or QT
    HARD_TIGHT = "hard_tight"   # Aggressive tightening


class RiskAppetite(Enum):
    RISK_OFF_CRISIS = "risk_off_crisis"  # Credit event / systemic panic
    RISK_OFF = "risk_off"                # High vol, flight to safety
    NEUTRAL = "neutral"                  # Normal conditions
    RISK_ON = "risk_on"                  # Risk euphoria


class NarrativeSentiment(Enum):
    """Manual narrative sentiment classification"""
    ZERO_SCAM = "zero_scam"      # "Going to zero" / "It's a scam" narrative
    NEGATIVE = "negative"        # Clearly negative but not hopeless
    NEUTRAL = "neutral"          # Mixed / no clear narrative
    EUPHORIA = "euphoria"        # "To the moon" / extreme hype


@dataclass
class CryptoSubscores:
    """Subscores for each module"""
    # Valuation (40 pts total)
    mvrv_score: float = 0.0           # 0-20
    rp_ratio_score: float = 0.0       # 0-20
    valuation_total: float = 0.0      # 0-40

    # Trend (20 pts total)
    ma200w_score: float = 0.0         # 0-10
    rsi_score: float = 0.0            # 0-10
    trend_total: float = 0.0          # 0-20

    # Sentiment (20 pts total)
    fear_greed_score: float = 0.0     # 0-10
    narrative_score: float = 0.0      # 0-10
    sentiment_total: float = 0.0      # 0-20

    # Macro (20 pts total)
    rate_score: float = 0.0           # 0-10
    risk_score: float = 0.0           # 0-10
    macro_total: float = 0.0          # 0-20


@dataclass
class CryptoScore:
    """Complete scoring result for a crypto asset"""
    asset: str                        # BTC or ETH
    date: str                         # Evaluation date
    score: float                      # Final smoothed score (0-100)
    score_raw: float                  # Raw score before smoothing (0-100)
    subscores: CryptoSubscores        # Detailed subscores
    reason_tags: List[str]            # Reasons for high scores
    recommendation: str               # Action recommendation

    # Input data for transparency
    price: Optional[float] = None
    realized_price: Optional[float] = None
    mvrv: Optional[float] = None
    ratio_rp: Optional[float] = None
    ratio_200w: Optional[float] = None
    rsi_weekly: Optional[float] = None
    fear_greed: Optional[int] = None
    rate_regime: Optional[str] = None
    risk_appetite: Optional[str] = None
    narrative: Optional[str] = None

    # Data quality flags
    stale_chain_data: bool = False  # True if chain data is estimated (not from API)
    chain_data_source: str = "api"  # "api", "estimated", or "manual"

    def __str__(self):
        return f"{self.asset}: {self.score:.0f}/100 ({self.recommendation})"


class CryptoScorer:
    """
    BTC/ETH Entry Scoring System

    Principle: Don't chase rallies - higher prices usually mean lower scores
    unless macro is extremely accommodative and valuation still reasonable.
    """

    # ETH has higher volatility - slightly wider thresholds
    ETH_THRESHOLD_ADJUSTMENT = 0.05

    # Realized Price estimation coefficients (based on historical analysis)
    # RP typically trades between 0.5x and 0.8x of the 200-week MA during accumulation
    # and 0.7x-1.2x during normal markets
    RP_ESTIMATION_FACTOR = {
        'BTC': 0.75,  # RP is typically ~75% of 200wMA in normal conditions
        'ETH': 0.70,  # ETH RP is typically ~70% of 200wMA
    }

    def __init__(self):
        self.cache = {}
        self.previous_scores: Dict[str, float] = {}  # For EMA smoothing
        self._chain_data_cache = {}  # Cache for chain data

    # ==================== DATA FETCHING ====================

    def _get_price_data(self, symbol: str, period: str = "5y") -> Optional[pd.DataFrame]:
        """Get historical price data"""
        cache_key = f"{symbol}_{period}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if len(hist) > 0:
                self.cache[cache_key] = hist
                return hist
        except Exception as e:
            print(f"Warning: Could not fetch {symbol}: {e}")
        return None

    def _get_current_price(self, asset: str) -> Optional[float]:
        """Get current price for BTC or ETH"""
        symbol = f"{asset}-USD"
        hist = self._get_price_data(symbol, "5d")
        if hist is not None and len(hist) > 0:
            return float(hist['Close'].iloc[-1])
        return None

    def _get_200w_ma(self, asset: str) -> Optional[float]:
        """Calculate 200-week moving average"""
        symbol = f"{asset}-USD"
        hist = self._get_price_data(symbol, "5y")

        if hist is None or len(hist) < 200 * 5:  # Need ~1000 trading days
            return None

        # Resample to weekly and calculate 200-week MA
        weekly = hist['Close'].resample('W').last()
        if len(weekly) >= 200:
            return float(weekly.rolling(200).mean().iloc[-1])
        return None

    def _get_weekly_rsi(self, asset: str, periods: int = 14) -> Optional[float]:
        """Calculate weekly RSI"""
        symbol = f"{asset}-USD"
        hist = self._get_price_data(symbol, "2y")

        if hist is None or len(hist) < periods * 7:
            return None

        # Resample to weekly
        weekly = hist['Close'].resample('W').last()

        if len(weekly) < periods + 1:
            return None

        # Calculate RSI
        delta = weekly.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

    def _get_fear_greed(self) -> Optional[int]:
        """Fetch Fear & Greed Index from alternative.me API"""
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return int(data['data'][0]['value'])
        except Exception as e:
            print(f"Warning: Could not fetch Fear & Greed: {e}")
        return None

    # ==================== CHAIN DATA (MVRV / Realized Price) ====================

    def _fetch_coinglass_mvrv(self, asset: str) -> Optional[float]:
        """
        Fetch MVRV from CoinGlass API (free tier)
        Returns MVRV ratio or None if unavailable
        """
        cache_key = f"coinglass_mvrv_{asset}"
        if cache_key in self._chain_data_cache:
            return self._chain_data_cache[cache_key]

        try:
            # CoinGlass public API for MVRV
            symbol = asset.upper()
            url = f"https://open-api.coinglass.com/public/v2/index/mvrv?symbol={symbol}"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    mvrv = float(data['data'].get('mvrv', 0))
                    if mvrv > 0:
                        self._chain_data_cache[cache_key] = mvrv
                        return mvrv
        except Exception as e:
            print(f"  Note: CoinGlass MVRV not available: {e}")
        return None

    def _fetch_blockchain_com_data(self, asset: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch chain data from blockchain.com API (BTC only, free)
        Returns (realized_price, mvrv) or (None, None)
        """
        if asset != "BTC":
            return None, None

        cache_key = f"blockchain_data_{asset}"
        if cache_key in self._chain_data_cache:
            return self._chain_data_cache[cache_key]

        try:
            # Market cap
            mc_url = "https://api.blockchain.info/stats"
            mc_resp = requests.get(mc_url, timeout=10)
            if mc_resp.status_code != 200:
                return None, None

            stats = mc_resp.json()
            market_cap = stats.get('market_price_usd', 0) * 21000000  # Approximate

            # For realized cap, we need to estimate or use alternative source
            # blockchain.com doesn't provide realized cap directly
            # We'll use estimation method instead
        except Exception as e:
            print(f"  Note: blockchain.com data not available: {e}")

        return None, None

    def _estimate_realized_price(self, asset: str, current_price: float, ma_200w: float) -> float:
        """
        Estimate Realized Price based on 200-week MA

        Historical observation:
        - BTC Realized Price typically ~75% of 200wMA in normal markets
        - During deep bears, RP can be 60-70% of 200wMA
        - During bulls, RP rises to 80-90% of 200wMA

        This is an approximation when actual chain data is unavailable.
        """
        factor = self.RP_ESTIMATION_FACTOR.get(asset, 0.75)

        # Adjust factor based on price position
        price_ratio = current_price / ma_200w if ma_200w > 0 else 1.0

        if price_ratio < 0.8:
            # Deep bear - RP is higher relative to MA (less profit taking)
            adj_factor = factor * 0.95
        elif price_ratio > 2.0:
            # Strong bull - RP rises faster
            adj_factor = factor * 1.15
        else:
            adj_factor = factor

        return ma_200w * adj_factor

    def _estimate_mvrv(self, current_price: float, realized_price: float) -> float:
        """
        Estimate MVRV from price and realized price
        MVRV = Market Value / Realized Value ≈ Price / Realized Price
        """
        if realized_price <= 0:
            return 1.0
        return current_price / realized_price

    def _get_chain_data(self, asset: str, price: float, ma_200w: float) -> Tuple[float, float, bool]:
        """
        Get chain data (realized_price, mvrv) with fallback to estimation

        Returns: (realized_price, mvrv, is_estimated)
        """
        is_estimated = False

        # Try CoinGlass MVRV first
        mvrv = self._fetch_coinglass_mvrv(asset)

        if mvrv is not None and mvrv > 0:
            # We got MVRV, calculate RP from it
            realized_price = price / mvrv if mvrv > 0 else price
            return realized_price, mvrv, False

        # Try blockchain.com for BTC
        if asset == "BTC":
            rp, mv = self._fetch_blockchain_com_data(asset)
            if rp is not None and mv is not None:
                return rp, mv, False

        # Fallback to estimation
        if ma_200w and ma_200w > 0:
            realized_price = self._estimate_realized_price(asset, price, ma_200w)
            mvrv = self._estimate_mvrv(price, realized_price)
            is_estimated = True
            return realized_price, mvrv, is_estimated

        return price * 0.7, 1.0, True  # Last resort fallback

    # ==================== SCORING FUNCTIONS ====================

    def _score_mvrv(self, mvrv: Optional[float]) -> Tuple[float, List[str]]:
        """
        MVRV scoring (0-20 points)
        MVRV < 1 = market below realized value = historically rare cheap window
        """
        if mvrv is None:
            return 0, []

        tags = []
        if mvrv < 0.8:
            score = 20
            tags.append("MVRV<0.8 (极度低估)")
        elif mvrv < 1.0:
            score = 15
            tags.append("MVRV<1 (整体浮亏区)")
        elif mvrv < 1.5:
            score = 8
        else:
            score = 0

        return score, tags

    def _score_rp_ratio(self, ratio_rp: Optional[float], asset: str) -> Tuple[float, List[str]]:
        """
        Realized Price ratio scoring (0-20 points)
        Price below/near average cost = lower long-term risk
        """
        if ratio_rp is None:
            return 0, []

        # ETH has wider thresholds due to higher volatility
        adj = self.ETH_THRESHOLD_ADJUSTMENT if asset == "ETH" else 0

        tags = []
        if ratio_rp <= 0.9 + adj:
            score = 20
            tags.append("P<RP (价格低于全网成本)")
        elif ratio_rp <= 1.0 + adj:
            score = 15
            tags.append("P≈RP (接近全网成本)")
        elif ratio_rp <= 1.2 + adj:
            score = 8
        else:
            score = 0

        return score, tags

    def _score_200w_ma(self, ratio_200w: Optional[float]) -> Tuple[float, List[str]]:
        """
        200-week MA position scoring (0-10 points)
        Near/below long-term MA = structurally cheap
        """
        if ratio_200w is None:
            return 0, []

        tags = []
        if ratio_200w <= 1.0:
            score = 10
            tags.append("P≤200wMA (结构性便宜)")
        elif ratio_200w <= 1.2:
            score = 6
        else:
            score = 0

        return score, tags

    def _score_weekly_rsi(self, rsi: Optional[float]) -> Tuple[float, List[str]]:
        """
        Weekly RSI scoring (0-10 points)
        Low RSI = oversold on weekly timeframe
        """
        if rsi is None:
            return 0, []

        tags = []
        if rsi < 30:
            score = 10
            tags.append(f"RSI_w<30 (周线超卖)")
        elif rsi < 40:
            score = 6
            tags.append(f"RSI_w<40")
        elif rsi < 50:
            score = 3
        else:
            score = 0

        return score, tags

    def _score_fear_greed(self, fg: Optional[int]) -> Tuple[float, List[str]]:
        """
        Fear & Greed scoring (0-10 points)
        Extreme fear = contrarian opportunity
        """
        if fg is None:
            return 0, []

        tags = []
        if fg <= 10:
            score = 10
            tags.append(f"FG≤10 (极度恐惧)")
        elif fg <= 25:
            score = 6
            tags.append(f"FG<25 (恐惧)")
        elif fg <= 50:
            score = 3
        else:
            score = 0

        return score, tags

    def _score_narrative(self, narrative: NarrativeSentiment) -> Tuple[float, List[str]]:
        """
        Narrative sentiment scoring (0-10 points)
        "Going to zero" narrative = contrarian buy signal
        """
        tags = []

        if narrative == NarrativeSentiment.ZERO_SCAM:
            score = 10
            tags.append("归零/骗局叙事 (极度悲观)")
        elif narrative == NarrativeSentiment.NEGATIVE:
            score = 6
            tags.append("负面叙事")
        elif narrative == NarrativeSentiment.NEUTRAL:
            score = 3
        else:  # EUPHORIA
            score = 0

        return score, tags

    def _score_rate_regime(self, regime: RateRegime) -> Tuple[float, List[str]]:
        """
        Rate/liquidity regime scoring (0-10 points)
        Easing = liquidity tailwind for risk assets
        """
        tags = []

        if regime == RateRegime.EASING:
            score = 10
            tags.append("宽松周期")
        elif regime == RateRegime.PAUSE:
            score = 6
        elif regime == RateRegime.TIGHTENING:
            score = 2
        else:  # HARD_TIGHT
            score = 0
            tags.append("强紧缩周期")

        return score, tags

    def _score_risk_appetite(self, appetite: RiskAppetite) -> Tuple[float, List[str]]:
        """
        Risk appetite scoring (0-10 points)
        Crisis = contrarian opportunity (if valuation supports)
        """
        tags = []

        if appetite == RiskAppetite.RISK_OFF_CRISIS:
            score = 10
            tags.append("系统性恐慌")
        elif appetite == RiskAppetite.RISK_OFF:
            score = 6
            tags.append("Risk-Off")
        elif appetite == RiskAppetite.NEUTRAL:
            score = 3
        else:  # RISK_ON
            score = 0

        return score, tags

    # ==================== MAIN SCORING ====================

    def score_asset(
        self,
        asset: str,
        # Macro regime (can be inferred from CycleDetector or provided)
        rate_regime: RateRegime = RateRegime.PAUSE,
        risk_appetite: RiskAppetite = RiskAppetite.NEUTRAL,
        # Sentiment (manual input, defaults to neutral)
        narrative: NarrativeSentiment = NarrativeSentiment.NEUTRAL,
        # Optional overrides (for manual chain data if you have it)
        realized_price_override: Optional[float] = None,
        mvrv_override: Optional[float] = None,
        price_override: Optional[float] = None,
        fear_greed_override: Optional[int] = None,
    ) -> CryptoScore:
        """
        Calculate entry score for BTC or ETH

        Chain data (MVRV, Realized Price) is automatically fetched from APIs.
        If APIs are unavailable, estimation based on 200wMA is used.

        Args:
            asset: "BTC" or "ETH"
            rate_regime: Current rate/liquidity regime
            risk_appetite: Current risk appetite regime
            narrative: Manual narrative sentiment classification
            realized_price_override: Manual override for realized price
            mvrv_override: Manual override for MVRV
            price_override: Override current price (for backtesting)
            fear_greed_override: Override F&G index

        Returns:
            CryptoScore with all details
        """
        assert asset in ["BTC", "ETH"], "Asset must be BTC or ETH"

        today = datetime.now().strftime("%Y-%m-%d")
        reason_tags = []

        # 1. Get price and technical data
        price = price_override or self._get_current_price(asset)
        ma_200w = self._get_200w_ma(asset)
        rsi_weekly = self._get_weekly_rsi(asset)
        fear_greed = fear_greed_override if fear_greed_override is not None else self._get_fear_greed()

        # 2. Get chain data (auto-fetch or estimate)
        chain_data_source = "api"
        if realized_price_override is not None and mvrv_override is not None:
            # Use manual overrides
            realized_price = realized_price_override
            mvrv = mvrv_override
            stale_chain_data = False
            chain_data_source = "manual"
        elif price and ma_200w:
            # Auto-fetch or estimate
            realized_price, mvrv, stale_chain_data = self._get_chain_data(asset, price, ma_200w)
            if stale_chain_data:
                reason_tags.append("链上数据: 估算值")
                chain_data_source = "estimated"
            else:
                chain_data_source = "api"
        else:
            realized_price = None
            mvrv = None
            stale_chain_data = True
            chain_data_source = "unavailable"

        # 3. Calculate ratios
        ratio_rp = price / realized_price if (price and realized_price) else None
        ratio_200w = price / ma_200w if (price and ma_200w) else None

        # 3. Calculate subscores
        subscores = CryptoSubscores()

        # Valuation (40 pts)
        subscores.mvrv_score, mvrv_tags = self._score_mvrv(mvrv)
        subscores.rp_ratio_score, rp_tags = self._score_rp_ratio(ratio_rp, asset)
        subscores.valuation_total = subscores.mvrv_score + subscores.rp_ratio_score
        reason_tags.extend(mvrv_tags + rp_tags)

        # Trend (20 pts)
        subscores.ma200w_score, ma_tags = self._score_200w_ma(ratio_200w)
        subscores.rsi_score, rsi_tags = self._score_weekly_rsi(rsi_weekly)
        subscores.trend_total = subscores.ma200w_score + subscores.rsi_score
        reason_tags.extend(ma_tags + rsi_tags)

        # Sentiment (20 pts)
        subscores.fear_greed_score, fg_tags = self._score_fear_greed(fear_greed)
        subscores.narrative_score, narr_tags = self._score_narrative(narrative)
        subscores.sentiment_total = subscores.fear_greed_score + subscores.narrative_score
        reason_tags.extend(fg_tags + narr_tags)

        # Macro (20 pts)
        subscores.rate_score, rate_tags = self._score_rate_regime(rate_regime)
        subscores.risk_score, risk_tags = self._score_risk_appetite(risk_appetite)
        subscores.macro_total = subscores.rate_score + subscores.risk_score
        reason_tags.extend(rate_tags + risk_tags)

        # 4. Calculate raw score
        score_raw = (
            subscores.valuation_total +
            subscores.trend_total +
            subscores.sentiment_total +
            subscores.macro_total
        )

        # 5. Apply EMA smoothing
        prev_score = self.previous_scores.get(asset, score_raw)
        score = 0.7 * prev_score + 0.3 * score_raw
        self.previous_scores[asset] = score

        # 6. Generate recommendation
        if score >= 80:
            recommendation = "STRONG_BUY"  # 历史级便宜
        elif score >= 65:
            recommendation = "ACCUMULATE"   # 加大定投
        elif score >= 50:
            recommendation = "DCA"          # 正常定投
        else:
            recommendation = "WAIT"         # 不主动提示

        return CryptoScore(
            asset=asset,
            date=today,
            score=score,
            score_raw=score_raw,
            subscores=subscores,
            reason_tags=reason_tags,
            recommendation=recommendation,
            price=price,
            realized_price=realized_price,
            mvrv=mvrv,
            ratio_rp=ratio_rp,
            ratio_200w=ratio_200w,
            rsi_weekly=rsi_weekly,
            fear_greed=fear_greed,
            rate_regime=rate_regime.value if rate_regime else None,
            risk_appetite=risk_appetite.value if risk_appetite else None,
            narrative=narrative.value if narrative else None,
            stale_chain_data=stale_chain_data,
            chain_data_source=chain_data_source,
        )

    def format_score_report(self, score: CryptoScore) -> str:
        """Format score as text report"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"{score.asset} ENTRY SCORE: {score.score:.0f}/100")
        lines.append("=" * 60)

        # Recommendation
        rec_emoji = {
            "STRONG_BUY": "🟢🟢",
            "ACCUMULATE": "🟢",
            "DCA": "⚪",
            "WAIT": "🔴"
        }.get(score.recommendation, "")

        rec_text = {
            "STRONG_BUY": "强提醒 (历史级便宜)",
            "ACCUMULATE": "加大定投",
            "DCA": "正常定投",
            "WAIT": "暂不建议"
        }.get(score.recommendation, score.recommendation)

        lines.append(f"\nRecommendation: {rec_text} {rec_emoji}")
        lines.append(f"Raw Score: {score.score_raw:.0f} | Smoothed: {score.score:.0f}")

        # Price info
        lines.append(f"\n{'='*20} PRICE DATA {'='*20}")
        if score.price:
            lines.append(f"Current Price: ${score.price:,.0f}")
        if score.realized_price:
            lines.append(f"Realized Price: ${score.realized_price:,.0f}")
        if score.ratio_rp:
            lines.append(f"P/RP Ratio: {score.ratio_rp:.2f}")
        if score.ratio_200w:
            lines.append(f"P/200wMA Ratio: {score.ratio_200w:.2f}")
        if score.rsi_weekly:
            lines.append(f"Weekly RSI: {score.rsi_weekly:.1f}")
        if score.fear_greed is not None:
            lines.append(f"Fear & Greed: {score.fear_greed}")

        # Subscores breakdown
        s = score.subscores
        lines.append(f"\n{'='*20} SUBSCORES {'='*20}")
        lines.append(f"{'Module':<20} {'Score':>8} {'Max':>8}")
        lines.append("-" * 40)
        lines.append(f"{'Valuation':<20} {s.valuation_total:>8.0f} {40:>8}")
        lines.append(f"  - MVRV{'':<12} {s.mvrv_score:>8.0f} {20:>8}")
        lines.append(f"  - RP Ratio{'':<8} {s.rp_ratio_score:>8.0f} {20:>8}")
        lines.append(f"{'Trend':<20} {s.trend_total:>8.0f} {20:>8}")
        lines.append(f"  - 200w MA{'':<9} {s.ma200w_score:>8.0f} {10:>8}")
        lines.append(f"  - Weekly RSI{'':<6} {s.rsi_score:>8.0f} {10:>8}")
        lines.append(f"{'Sentiment':<20} {s.sentiment_total:>8.0f} {20:>8}")
        lines.append(f"  - Fear & Greed{'':<4} {s.fear_greed_score:>8.0f} {10:>8}")
        lines.append(f"  - Narrative{'':<7} {s.narrative_score:>8.0f} {10:>8}")
        lines.append(f"{'Macro':<20} {s.macro_total:>8.0f} {20:>8}")
        lines.append(f"  - Rate Regime{'':<5} {s.rate_score:>8.0f} {10:>8}")
        lines.append(f"  - Risk Appetite{'':<3} {s.risk_score:>8.0f} {10:>8}")
        lines.append("-" * 40)
        lines.append(f"{'TOTAL':<20} {score.score_raw:>8.0f} {100:>8}")

        # Reason tags
        if score.reason_tags:
            lines.append(f"\n{'='*20} SIGNALS {'='*20}")
            for tag in score.reason_tags:
                lines.append(f"  • {tag}")

        # Data source info
        source_text = {
            "api": "API (实时)",
            "estimated": "估算 (基于200wMA)",
            "manual": "手动输入",
            "unavailable": "不可用"
        }.get(score.chain_data_source, score.chain_data_source)
        lines.append(f"\n📊 Chain Data Source: {source_text}")

        # Warning only if data is unavailable
        if score.chain_data_source == "unavailable":
            lines.append(f"⚠️  Warning: Chain data unavailable - valuation score is 0")

        return "\n".join(lines)


def get_macro_regimes_from_cycle_detector():
    """
    Helper to get rate/risk regimes from CycleDetector
    Returns (RateRegime, RiskAppetite)
    """
    try:
        from .cycle_detector import CycleDetector

        detector = CycleDetector()
        state = detector.detect_cycles()

        # Map rate regime
        if state.rate_regime == 'ease':
            rate = RateRegime.EASING
        elif state.rate_regime == 'tight':
            rate = RateRegime.TIGHTENING
        else:
            rate = RateRegime.PAUSE

        # Map risk regime
        if state.risk_regime == 'risk_off':
            risk = RiskAppetite.RISK_OFF
        elif state.risk_regime == 'risk_on':
            risk = RiskAppetite.RISK_ON
        else:
            risk = RiskAppetite.NEUTRAL

        return rate, risk

    except Exception as e:
        print(f"Warning: Could not get regimes from CycleDetector: {e}")
        return RateRegime.PAUSE, RiskAppetite.NEUTRAL


# ==================== DEMO / CLI ====================

if __name__ == "__main__":
    print("Running Crypto Entry Scorer...")
    print()

    scorer = CryptoScorer()

    # Get macro regimes from cycle detector
    rate_regime, risk_appetite = get_macro_regimes_from_cycle_detector()
    print(f"Macro from CycleDetector: Rate={rate_regime.value}, Risk={risk_appetite.value}")
    print()

    # Score BTC - chain data is auto-fetched
    print("Scoring BTC (auto-fetch chain data)...")
    btc_score = scorer.score_asset(
        asset="BTC",
        rate_regime=rate_regime,
        risk_appetite=risk_appetite,
        narrative=NarrativeSentiment.NEUTRAL,
    )

    print(scorer.format_score_report(btc_score))
    print()

    # Score ETH - chain data is auto-fetched
    print("Scoring ETH (auto-fetch chain data)...")
    eth_score = scorer.score_asset(
        asset="ETH",
        rate_regime=rate_regime,
        risk_appetite=risk_appetite,
        narrative=NarrativeSentiment.NEUTRAL,
    )

    print(scorer.format_score_report(eth_score))
