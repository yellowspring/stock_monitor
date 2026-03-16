"""
Stock Scanner - Individual Stock Entry Scoring System

Automatically scans the market to find top candidates worth researching.
Scoring based on:
1. Survival (30 pts): Cash runway, leverage, interest coverage
2. Valuation (30 pts): PE/EV percentile, FCF yield
3. Fear (20 pts): Drawdown, sentiment
4. Structure (20 pts): MA position, RSI

Core principle: Stocks can "die", so survival filter comes first.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
import random
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Rate limiter to prevent Yahoo Finance API throttling
class RateLimiter:
    """Thread-safe rate limiter for API calls"""
    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()

    def wait(self):
        """Wait if needed to respect rate limit"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed + random.uniform(0.1, 0.3)
                time.sleep(sleep_time)
            self.last_call = time.time()

# Global rate limiter (2 requests per second max)
_rate_limiter = RateLimiter(calls_per_second=2.0)

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


@dataclass
class StockSubscores:
    """Subscores for each module"""
    # Survival (30 pts)
    runway_score: float = 0.0         # 0-10
    leverage_score: float = 0.0       # 0-10
    interest_coverage_score: float = 0.0  # 0-10
    survival_total: float = 0.0       # 0-30

    # Valuation (30 pts)
    valuation_pct_score: float = 0.0  # 0-15
    fcf_yield_score: float = 0.0      # 0-15
    valuation_total: float = 0.0      # 0-30

    # Fear (20 pts)
    drawdown_score: float = 0.0       # 0-10
    sentiment_score: float = 0.0      # 0-10
    fear_total: float = 0.0           # 0-20

    # Structure (20 pts)
    ma_score: float = 0.0             # 0-10
    rsi_score: float = 0.0            # 0-10
    structure_total: float = 0.0      # 0-20


@dataclass
class StockScanResult:
    """Scan result for a single stock"""
    symbol: str
    name: str
    sector: str
    industry: str
    score: float                      # 0-100
    subscores: StockSubscores
    reason_tags: List[str]
    recommendation: str               # STRONG_BUY, RESEARCH, WATCH, AVOID

    # Key metrics for display
    price: float = 0.0
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    fcf_yield: Optional[float] = None
    ev_ebitda: Optional[float] = None
    debt_to_ebitda: Optional[float] = None
    drawdown_52w: float = 0.0
    rsi_14d: Optional[float] = None
    runway_years: Optional[float] = None

    # Flags
    passed_survival_filter: bool = True
    value_trap_warning: bool = False
    filter_reason: str = ""

    # New risk flags
    earnings_risk: bool = False         # True if earnings within 7 days
    earnings_date: str = ""             # Next earnings date
    trend_warning: bool = False         # True if in strong downtrend
    momentum_penalty: float = 0.0       # Penalty applied for bad momentum

    def __str__(self):
        return f"{self.symbol}: {self.score:.0f}/100 ({self.recommendation})"


class StockScanner:
    """
    Stock scanning and scoring system

    Scans a universe of stocks and scores them based on:
    - Survival ability (cash, debt, coverage)
    - Valuation (PE percentile, FCF yield)
    - Fear (drawdown, sentiment)
    - Structure (MA position, RSI)
    """

    # Default universe - can be customized
    DEFAULT_UNIVERSE = [
        # Top tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
        # Semiconductors
        'AMD', 'INTC', 'QCOM', 'AVGO', 'MU', 'AMAT', 'LRCX',
        # Software
        'CRM', 'ADBE', 'NOW', 'SNOW', 'PLTR', 'NET', 'DDOG',
        # Finance
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK',
        # Healthcare
        'JNJ', 'UNH', 'PFE', 'MRK', 'ABBV', 'LLY', 'TMO',
        # Consumer
        'WMT', 'COST', 'HD', 'NKE', 'SBUX', 'MCD', 'DIS',
        # Industrial
        'CAT', 'DE', 'BA', 'GE', 'HON', 'UPS', 'UNP',
        # Energy
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY',
        # Other
        'V', 'MA', 'PYPL', 'SQ', 'COIN', 'UBER', 'ABNB',
    ]

    def __init__(self, universe: List[str] = None, cache_hours: int = 12):
        self.universe = universe or self.DEFAULT_UNIVERSE
        self.cache = {}
        self._data_cache = {}
        self.cache_hours = cache_hours
        self.cache_file = CACHE_DIR / "stock_scan_cache.json"
        self.results_file = CACHE_DIR / "stock_scan_results.json"

    def _load_cache(self) -> Dict:
        """Load cache from file if not expired"""
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            # Check expiry
            cached_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(hours=self.cache_hours):
                return {}

            return data.get('stocks', {})
        except:
            return {}

    def _save_cache(self, stocks_data: Dict):
        """Save cache to file"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'stocks': stocks_data
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def save_results(self, results: List['StockScanResult']):
        """Save scan results to JSON file for later use"""
        try:
            results_data = {
                'timestamp': datetime.now().isoformat(),
                'count': len(results),
                'results': []
            }
            for r in results:
                results_data['results'].append({
                    'symbol': r.symbol,
                    'name': r.name,
                    'sector': r.sector,
                    'industry': r.industry,
                    'score': r.score,
                    'recommendation': r.recommendation,
                    'pe_ratio': r.pe_ratio,
                    'fcf_yield': r.fcf_yield,
                    'debt_to_ebitda': r.debt_to_ebitda,
                    'drawdown_52w': r.drawdown_52w,
                    'rsi_14d': r.rsi_14d,
                    'reason_tags': r.reason_tags,
                    'value_trap_warning': r.value_trap_warning,
                    'subscores': {
                        'survival': r.subscores.survival_total,
                        'valuation': r.subscores.valuation_total,
                        'fear': r.subscores.fear_total,
                        'structure': r.subscores.structure_total,
                    }
                })

            with open(self.results_file, 'w') as f:
                json.dump(results_data, f, indent=2, default=str)

            print(f"Results saved to {self.results_file}")
        except Exception as e:
            print(f"Warning: Could not save results: {e}")

    def load_cached_results(self) -> Optional[List[Dict]]:
        """Load cached results if available and fresh"""
        if not self.results_file.exists():
            return None

        try:
            with open(self.results_file, 'r') as f:
                data = json.load(f)

            cached_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(hours=self.cache_hours):
                return None

            return data.get('results', [])
        except:
            return None

    def _get_stock_info(self, symbol: str, max_retries: int = 3) -> Optional[Dict]:
        """Get comprehensive stock info from yfinance with rate limiting and retry"""
        cache_key = f"info_{symbol}"
        if cache_key in self._data_cache:
            return self._data_cache[cache_key]

        for attempt in range(max_retries):
            try:
                # Rate limit before each API call
                _rate_limiter.wait()

                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Check if we got valid data (rate limit returns empty)
                if not info or info.get('regularMarketPrice') is None:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(1, 3)
                        time.sleep(wait_time)
                        continue
                    return None

                # Rate limit before history call
                _rate_limiter.wait()

                # Get historical data for technical indicators
                hist = ticker.history(period="1y")

                _rate_limiter.wait()
                hist_5y = ticker.history(period="5y")

                break  # Success, exit retry loop

            except Exception as e:
                error_msg = str(e).lower()
                if 'rate' in error_msg or 'too many' in error_msg or '429' in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 5 + random.uniform(2, 5)
                        print(f"  Rate limited on {symbol}, waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                print(f"  Warning: Could not fetch {symbol}: {e}")
                return None

        try:

            if len(hist) == 0:
                return None

            # Calculate technical indicators
            current_price = hist['Close'].iloc[-1]
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            drawdown_52w = (current_price - high_52w) / high_52w

            # Calculate RSI
            rsi_14d = self._calculate_rsi(hist['Close'], 14)

            # Calculate MAs
            ma_50d = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) >= 50 else None
            ma_200d = hist['Close'].rolling(200).mean().iloc[-1] if len(hist) >= 200 else None

            # Get financials (with rate limiting)
            try:
                _rate_limiter.wait()
                financials = ticker.financials
                _rate_limiter.wait()
                quarterly = ticker.quarterly_financials
                _rate_limiter.wait()
                balance = ticker.balance_sheet
                _rate_limiter.wait()
                cashflow = ticker.cashflow
            except:
                financials = quarterly = balance = cashflow = None

            result = {
                'symbol': symbol,
                'name': info.get('shortName', symbol),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'price': current_price,
                'market_cap': info.get('marketCap', 0),
                'high_52w': high_52w,
                'low_52w': low_52w,
                'drawdown_52w': drawdown_52w,
                'rsi_14d': rsi_14d,
                'ma_50d': ma_50d,
                'ma_200d': ma_200d,
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
                'ps_ratio': info.get('priceToSalesTrailing12Months'),
                'ev_ebitda': info.get('enterpriseToEbitda'),
                'fcf_yield': self._calculate_fcf_yield(info),
                'debt_to_equity': info.get('debtToEquity'),
                'current_ratio': info.get('currentRatio'),
                'total_debt': info.get('totalDebt', 0),
                'total_cash': info.get('totalCash', 0),
                'ebitda': info.get('ebitda', 0),
                'free_cashflow': info.get('freeCashflow', 0),
                'revenue': info.get('totalRevenue', 0),
                'revenue_growth': info.get('revenueGrowth'),
                'earnings_growth': info.get('earningsGrowth'),
                'profit_margin': info.get('profitMargins'),
                'hist': hist,
                'hist_5y': hist_5y,
            }

            self._data_cache[cache_key] = result
            return result

        except Exception as e:
            print(f"  Warning: Could not fetch {symbol}: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return None

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

    def _calculate_fcf_yield(self, info: Dict) -> Optional[float]:
        """Calculate FCF yield"""
        fcf = info.get('freeCashflow', 0)
        market_cap = info.get('marketCap', 0)

        if fcf and market_cap and market_cap > 0:
            return (fcf / market_cap) * 100
        return None

    def _calculate_pe_percentile(self, info: Dict, hist_5y: pd.DataFrame) -> Optional[float]:
        """Calculate current PE percentile vs 5-year history"""
        current_pe = info.get('pe_ratio')
        if current_pe is None or current_pe <= 0:
            return None

        # This is simplified - ideally would use historical PE data
        # For now, estimate based on price percentile as proxy
        if hist_5y is not None and len(hist_5y) > 0:
            current_price = hist_5y['Close'].iloc[-1]
            percentile = (hist_5y['Close'] <= current_price).sum() / len(hist_5y)
            return percentile
        return None

    # ==================== SURVIVAL FILTER ====================

    def _apply_survival_filter(self, info: Dict) -> Tuple[bool, str, float]:
        """
        Apply survival filter to eliminate high-risk stocks

        Returns: (passed, reason, runway_years)
        """
        fcf = info.get('free_cashflow', 0)
        cash = info.get('total_cash', 0)
        debt = info.get('total_debt', 0)
        ebitda = info.get('ebitda', 0)

        # Calculate runway
        runway_years = None
        if fcf and fcf < 0 and abs(fcf) > 0:
            runway_years = cash / abs(fcf) if cash else 0
        elif fcf and fcf > 0:
            runway_years = 99  # Positive FCF = infinite runway

        # Filter 1: Cash flow filter
        if fcf and fcf < 0 and cash:
            if cash / abs(fcf) < 1:
                return False, "Cash runway < 1 year (burning cash too fast)", runway_years

        # Filter 2: Debt pressure filter
        if debt and ebitda and ebitda > 0:
            debt_to_ebitda = debt / ebitda
            if debt_to_ebitda > 8 and cash < debt * 0.1:
                return False, f"Extreme leverage (Debt/EBITDA={debt_to_ebitda:.1f})", runway_years

        # Filter 3: Market cap filter (avoid penny stocks)
        market_cap = info.get('market_cap', 0)
        if market_cap < 500_000_000:  # $500M minimum
            return False, "Market cap too small (<$500M)", runway_years

        return True, "", runway_years

    # ==================== SCORING FUNCTIONS ====================

    def _score_survival(self, info: Dict) -> Tuple[StockSubscores, List[str]]:
        """Score survival ability (30 pts total)"""
        subscores = StockSubscores()
        tags = []

        fcf = info.get('free_cashflow', 0)
        cash = info.get('total_cash', 0)
        debt = info.get('total_debt', 0)
        ebitda = info.get('ebitda', 0)

        # Runway score (10 pts)
        if fcf and fcf > 0:
            subscores.runway_score = 10
            tags.append("现金流正 FCF+")
        elif fcf and fcf < 0 and cash:
            runway = cash / abs(fcf)
            if runway >= 3:
                subscores.runway_score = 10
                tags.append(f"跑道≥3年")
            elif runway >= 2:
                subscores.runway_score = 7
            elif runway >= 1:
                subscores.runway_score = 3
            else:
                subscores.runway_score = 0
        else:
            subscores.runway_score = 5  # No data, neutral

        # Leverage score (10 pts)
        if debt and ebitda and ebitda > 0:
            debt_to_ebitda = debt / ebitda
            if debt_to_ebitda < 2:
                subscores.leverage_score = 10
                tags.append("低杠杆 D/E<2")
            elif debt_to_ebitda < 4:
                subscores.leverage_score = 6
            elif debt_to_ebitda < 6:
                subscores.leverage_score = 2
            else:
                subscores.leverage_score = 0
        elif debt == 0 or (debt and debt < cash):
            subscores.leverage_score = 10
            tags.append("净现金 NetCash")
        else:
            subscores.leverage_score = 5  # No data

        # Interest coverage score (10 pts)
        # Simplified: use EBITDA margin as proxy
        revenue = info.get('revenue', 0)
        if ebitda and revenue and revenue > 0:
            ebitda_margin = ebitda / revenue
            if ebitda_margin > 0.25:
                subscores.interest_coverage_score = 10
                tags.append("高利润率 EBITDA>25%")
            elif ebitda_margin > 0.15:
                subscores.interest_coverage_score = 6
            elif ebitda_margin > 0.05:
                subscores.interest_coverage_score = 3
            else:
                subscores.interest_coverage_score = 0
        else:
            subscores.interest_coverage_score = 5

        subscores.survival_total = (
            subscores.runway_score +
            subscores.leverage_score +
            subscores.interest_coverage_score
        )

        return subscores, tags

    def _score_valuation(self, info: Dict) -> Tuple[float, float, List[str]]:
        """Score valuation (30 pts total)"""
        tags = []

        # Valuation percentile score (15 pts)
        pe = info.get('pe_ratio')
        forward_pe = info.get('forward_pe')
        ev_ebitda = info.get('ev_ebitda')

        val_pct_score = 0

        # Use forward PE or trailing PE
        use_pe = forward_pe if forward_pe and forward_pe > 0 else pe

        if use_pe and use_pe > 0:
            if use_pe < 10:
                val_pct_score = 15
                tags.append(f"极低PE {use_pe:.0f}")
            elif use_pe < 15:
                val_pct_score = 12
                tags.append(f"低PE {use_pe:.0f}")
            elif use_pe < 20:
                val_pct_score = 8
            elif use_pe < 30:
                val_pct_score = 4
            else:
                val_pct_score = 0
        elif ev_ebitda and ev_ebitda > 0:
            if ev_ebitda < 8:
                val_pct_score = 15
                tags.append(f"低EV/EBITDA {ev_ebitda:.0f}")
            elif ev_ebitda < 12:
                val_pct_score = 10
            elif ev_ebitda < 18:
                val_pct_score = 5
            else:
                val_pct_score = 0
        else:
            val_pct_score = 7  # No data, neutral

        # FCF yield score (15 pts)
        fcf_yield = info.get('fcf_yield')
        fcf_yield_score = 0

        if fcf_yield is not None:
            if fcf_yield >= 10:
                fcf_yield_score = 15
                tags.append(f"高FCF收益率 {fcf_yield:.0f}%")
            elif fcf_yield >= 6:
                fcf_yield_score = 10
                tags.append(f"良好FCF {fcf_yield:.0f}%")
            elif fcf_yield >= 3:
                fcf_yield_score = 5
            elif fcf_yield >= 0:
                fcf_yield_score = 2
            else:
                fcf_yield_score = 0
        else:
            fcf_yield_score = 7

        return val_pct_score, fcf_yield_score, tags

    def _score_fear(self, info: Dict) -> Tuple[float, float, List[str]]:
        """Score fear/sentiment (20 pts total)"""
        tags = []

        # Drawdown score (10 pts)
        drawdown = info.get('drawdown_52w', 0)
        drawdown_score = 0

        if drawdown <= -0.70:
            drawdown_score = 10
            tags.append(f"极度恐惧 跌{abs(drawdown)*100:.0f}%")
        elif drawdown <= -0.50:
            drawdown_score = 7
            tags.append(f"深度回调 跌{abs(drawdown)*100:.0f}%")
        elif drawdown <= -0.30:
            drawdown_score = 3
        else:
            drawdown_score = 0

        # Sentiment score (10 pts)
        # Simplified: use earnings growth as proxy for sentiment
        earnings_growth = info.get('earnings_growth')
        sentiment_score = 0

        if earnings_growth is not None:
            if earnings_growth < -0.5:
                sentiment_score = 8  # Very negative = contrarian opportunity
                tags.append("盈利骤降 逆向机会")
            elif earnings_growth < -0.2:
                sentiment_score = 5
            elif earnings_growth < 0:
                sentiment_score = 3
            else:
                sentiment_score = 0  # Positive = no fear signal
        else:
            sentiment_score = 5

        return drawdown_score, sentiment_score, tags

    def _score_structure(self, info: Dict) -> Tuple[float, float, List[str]]:
        """Score technical structure (20 pts total)"""
        tags = []

        # MA position score (10 pts)
        price = info.get('price', 0)
        ma_200d = info.get('ma_200d')
        ma_score = 0

        if ma_200d and ma_200d > 0 and price > 0:
            ratio = price / ma_200d
            if ratio <= 0.8:
                ma_score = 10
                tags.append(f"深度破均 P/MA={ratio:.2f}")
            elif ratio <= 1.0:
                ma_score = 6
                tags.append(f"均线下方 P/MA={ratio:.2f}")
            elif ratio <= 1.2:
                ma_score = 3
            else:
                ma_score = 0
        else:
            ma_score = 5

        # RSI score (10 pts)
        rsi = info.get('rsi_14d')
        rsi_score = 0

        if rsi is not None:
            if rsi < 30:
                rsi_score = 10
                tags.append(f"RSI超卖 {rsi:.0f}")
            elif rsi < 40:
                rsi_score = 6
                tags.append(f"RSI偏低 {rsi:.0f}")
            elif rsi < 50:
                rsi_score = 3
            else:
                rsi_score = 0
        else:
            rsi_score = 5

        return ma_score, rsi_score, tags

    def _detect_value_trap(self, info: Dict) -> Tuple[bool, List[str]]:
        """Detect value trap signals"""
        tags = []
        is_trap = False

        revenue_growth = info.get('revenue_growth')
        profit_margin = info.get('profit_margin')
        earnings_growth = info.get('earnings_growth')

        # Revenue declining + negative margin = value trap
        if revenue_growth is not None and revenue_growth < -0.1:
            if profit_margin is not None and profit_margin < 0:
                is_trap = True
                tags.append("价值陷阱: 收入下滑+亏损")

        # Severe earnings decline
        if earnings_growth is not None and earnings_growth < -0.5:
            if revenue_growth is not None and revenue_growth < -0.2:
                is_trap = True
                tags.append("价值陷阱: 收入盈利双降")

        return is_trap, tags

    def _check_earnings_risk(self, symbol: str) -> Tuple[bool, str, float]:
        """
        Check if earnings are within 7 days (high risk period)

        Returns:
            Tuple of (is_risky, earnings_date, penalty)
            - is_risky: True if earnings within 7 days
            - earnings_date: Next earnings date string
            - penalty: Score penalty to apply (0-15)
        """
        try:
            _rate_limiter.wait()
            ticker = yf.Ticker(symbol)

            # Try to get earnings date from calendar
            calendar = ticker.calendar
            if calendar is not None and not calendar.empty:
                # calendar can be DataFrame or dict
                if isinstance(calendar, pd.DataFrame):
                    if 'Earnings Date' in calendar.index:
                        earnings_dates = calendar.loc['Earnings Date']
                        if isinstance(earnings_dates, pd.Series):
                            next_earnings = earnings_dates.iloc[0]
                        else:
                            next_earnings = earnings_dates
                    else:
                        return False, "", 0
                elif isinstance(calendar, dict):
                    if 'Earnings Date' in calendar:
                        dates = calendar['Earnings Date']
                        next_earnings = dates[0] if isinstance(dates, list) else dates
                    else:
                        return False, "", 0
                else:
                    return False, "", 0

                # Convert to datetime if needed
                if isinstance(next_earnings, str):
                    next_earnings = pd.to_datetime(next_earnings)
                elif hasattr(next_earnings, 'to_pydatetime'):
                    next_earnings = next_earnings.to_pydatetime()

                if next_earnings is None or pd.isna(next_earnings):
                    return False, "", 0

                # Calculate days until earnings
                now = datetime.now()
                if hasattr(next_earnings, 'tzinfo') and next_earnings.tzinfo is not None:
                    next_earnings = next_earnings.replace(tzinfo=None)

                days_until = (next_earnings - now).days

                earnings_str = next_earnings.strftime('%Y-%m-%d')

                # Risk levels based on days until earnings
                if 0 <= days_until <= 3:
                    return True, earnings_str, 15  # Very high risk - imminent
                elif 4 <= days_until <= 7:
                    return True, earnings_str, 10  # High risk
                elif 8 <= days_until <= 14:
                    return False, earnings_str, 5  # Moderate caution
                else:
                    return False, earnings_str, 0

        except Exception as e:
            # If we can't get earnings data, don't penalize
            pass

        return False, "", 0

    def _check_trend_momentum(self, info: Dict) -> Tuple[bool, float, List[str]]:
        """
        Check trend momentum to detect "falling knife" situations

        Returns:
            Tuple of (is_bad_trend, penalty, tags)
            - is_bad_trend: True if in strong downtrend
            - penalty: Score penalty (0-20)
            - tags: Warning tags
        """
        tags = []
        penalty = 0
        is_bad = False

        price = info.get('price', 0)
        ma_50d = info.get('ma_50d')
        ma_200d = info.get('ma_200d')
        high_52w = info.get('high_52w')
        rsi = info.get('rsi_14d')

        if price <= 0:
            return False, 0, []

        # Check 1: Price significantly below both MAs (death cross territory)
        below_50 = ma_50d and price < ma_50d * 0.9  # >10% below 50MA
        below_200 = ma_200d and price < ma_200d * 0.85  # >15% below 200MA

        if below_50 and below_200:
            penalty += 10
            is_bad = True
            tags.append("趋势警告: 双均线下方")

        # Check 2: 50MA below 200MA (death cross)
        if ma_50d and ma_200d and ma_50d < ma_200d * 0.95:
            penalty += 5
            is_bad = True
            tags.append("均线死叉")

        # Check 3: Extreme drawdown (>40% from 52w high) + still falling
        if high_52w and high_52w > 0:
            drawdown = (high_52w - price) / high_52w
            if drawdown > 0.5:  # >50% drawdown
                penalty += 10
                is_bad = True
                tags.append(f"深度回撤 -{drawdown*100:.0f}%")
            elif drawdown > 0.4:  # >40% drawdown
                penalty += 5
                tags.append(f"大幅回撤 -{drawdown*100:.0f}%")

        # Check 4: Low RSI but in downtrend = falling knife, not opportunity
        if rsi and rsi < 35 and is_bad:
            # RSI low + bad trend = likely to go lower
            penalty += 5
            tags.append("超卖但趋势向下")

        return is_bad, min(penalty, 20), tags  # Cap at 20

    # ==================== MAIN SCANNING ====================

    def scan_stock(self, symbol: str) -> Optional[StockScanResult]:
        """Scan a single stock and return score"""
        info = self._get_stock_info(symbol)
        if info is None:
            return None

        # Apply survival filter
        passed, filter_reason, runway_years = self._apply_survival_filter(info)

        if not passed:
            return StockScanResult(
                symbol=symbol,
                name=info.get('name', symbol),
                sector=info.get('sector', 'Unknown'),
                industry=info.get('industry', 'Unknown'),
                score=0,
                subscores=StockSubscores(),
                reason_tags=[filter_reason],
                recommendation='FILTERED',
                price=info.get('price', 0),
                market_cap=info.get('market_cap', 0),
                passed_survival_filter=False,
                filter_reason=filter_reason
            )

        # Calculate scores
        all_tags = []

        # Survival (30 pts)
        subscores, survival_tags = self._score_survival(info)
        all_tags.extend(survival_tags)

        # Valuation (30 pts)
        val_pct_score, fcf_yield_score, val_tags = self._score_valuation(info)
        subscores.valuation_pct_score = val_pct_score
        subscores.fcf_yield_score = fcf_yield_score
        subscores.valuation_total = val_pct_score + fcf_yield_score
        all_tags.extend(val_tags)

        # Fear (20 pts)
        drawdown_score, sentiment_score, fear_tags = self._score_fear(info)
        subscores.drawdown_score = drawdown_score
        subscores.sentiment_score = sentiment_score
        subscores.fear_total = drawdown_score + sentiment_score
        all_tags.extend(fear_tags)

        # Structure (20 pts)
        ma_score, rsi_score, struct_tags = self._score_structure(info)
        subscores.ma_score = ma_score
        subscores.rsi_score = rsi_score
        subscores.structure_total = ma_score + rsi_score
        all_tags.extend(struct_tags)

        # Total score
        total_score = (
            subscores.survival_total +
            subscores.valuation_total +
            subscores.fear_total +
            subscores.structure_total
        )

        # Value trap detection
        is_trap, trap_tags = self._detect_value_trap(info)
        if is_trap:
            total_score -= 20  # Penalty for value trap
            all_tags.extend(trap_tags)

        # NEW: Earnings risk check
        earnings_risk, earnings_date, earnings_penalty = self._check_earnings_risk(symbol)
        if earnings_penalty > 0:
            total_score -= earnings_penalty
            if earnings_risk:
                all_tags.append(f"⚠️ 财报风险: {earnings_date} (扣{earnings_penalty}分)")
            else:
                all_tags.append(f"财报临近: {earnings_date}")

        # NEW: Trend/momentum check
        trend_warning, momentum_penalty, trend_tags = self._check_trend_momentum(info)
        if momentum_penalty > 0:
            total_score -= momentum_penalty
            all_tags.extend(trend_tags)

        total_score = max(0, min(100, total_score))

        # Generate recommendation (adjusted thresholds due to new penalties)
        if total_score >= 80:
            recommendation = 'STRONG_BUY'
        elif total_score >= 65:
            recommendation = 'RESEARCH'
        elif total_score >= 50:
            recommendation = 'WATCH'
        else:
            recommendation = 'AVOID'

        return StockScanResult(
            symbol=symbol,
            name=info.get('name', symbol),
            sector=info.get('sector', 'Unknown'),
            industry=info.get('industry', 'Unknown'),
            score=total_score,
            subscores=subscores,
            reason_tags=all_tags,
            recommendation=recommendation,
            price=info.get('price', 0),
            market_cap=info.get('market_cap', 0),
            pe_ratio=info.get('pe_ratio'),
            pb_ratio=info.get('pb_ratio'),
            fcf_yield=info.get('fcf_yield'),
            ev_ebitda=info.get('ev_ebitda'),
            debt_to_ebitda=info.get('total_debt', 0) / info.get('ebitda', 1) if info.get('ebitda') else None,
            drawdown_52w=info.get('drawdown_52w', 0),
            rsi_14d=info.get('rsi_14d'),
            runway_years=runway_years,
            passed_survival_filter=True,
            value_trap_warning=is_trap,
            earnings_risk=earnings_risk,
            earnings_date=earnings_date,
            trend_warning=trend_warning,
            momentum_penalty=earnings_penalty + momentum_penalty,
        )

    def scan_all(self, top_n: int = 20, min_score: int = 50, max_workers: int = 3) -> List[StockScanResult]:
        """
        Scan all stocks in universe and return top N

        Args:
            top_n: Number of top stocks to return
            min_score: Minimum score to include
            max_workers: Number of parallel workers (default 3 to avoid rate limiting)

        Returns:
            List of StockScanResult sorted by score descending
        """
        # Adjust workers based on universe size to avoid rate limiting
        # For large universes, use fewer workers
        effective_workers = min(max_workers, 3)  # Cap at 3 for safety
        if len(self.universe) > 200:
            effective_workers = min(effective_workers, 2)
            print(f"Large universe ({len(self.universe)} stocks), using {effective_workers} workers to avoid rate limits")

        print(f"Scanning {len(self.universe)} stocks with {effective_workers} workers...")
        print(f"(Rate limited to ~2 req/sec per worker, estimated time: {len(self.universe) * 3 // effective_workers // 60} min)")
        results = []
        start_time = time.time()

        # Parallel scanning with rate limiting
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_to_symbol = {
                executor.submit(self.scan_stock, symbol): symbol
                for symbol in self.universe
            }

            for i, future in enumerate(as_completed(future_to_symbol)):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result and result.passed_survival_filter:
                        results.append(result)
                    if (i + 1) % 20 == 0:
                        elapsed = time.time() - start_time
                        rate = (i + 1) / elapsed if elapsed > 0 else 0
                        remaining = (len(self.universe) - i - 1) / rate if rate > 0 else 0
                        print(f"  Scanned {i + 1}/{len(self.universe)} stocks... ({rate:.1f}/s, ~{remaining/60:.0f} min left)")
                except Exception as e:
                    print(f"  Error scanning {symbol}: {e}")

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        # Filter by min score and take top N
        filtered = [r for r in results if r.score >= min_score]

        print(f"Found {len(filtered)} stocks with score >= {min_score}")

        return filtered[:top_n]

    def format_scan_report(self, results: List[StockScanResult]) -> str:
        """Format scan results as text report"""
        lines = []
        lines.append("=" * 80)
        lines.append("STOCK SCANNER - TOP CANDIDATES")
        lines.append("=" * 80)
        lines.append(f"Scanned: {len(self.universe)} stocks | Found: {len(results)} candidates")
        lines.append("")

        # Summary table
        lines.append(f"{'Rank':<5} {'Symbol':<8} {'Name':<20} {'Score':>6} {'Rec':<12} {'PE':>8} {'FCF%':>6} {'DD%':>7}")
        lines.append("-" * 80)

        for i, r in enumerate(results, 1):
            pe_str = f"{r.pe_ratio:.1f}" if r.pe_ratio else "-"
            fcf_str = f"{r.fcf_yield:.1f}" if r.fcf_yield else "-"
            dd_str = f"{r.drawdown_52w * 100:.0f}%"
            name = r.name[:18] if len(r.name) > 18 else r.name

            lines.append(
                f"{i:<5} {r.symbol:<8} {name:<20} {r.score:>6.0f} {r.recommendation:<12} {pe_str:>8} {fcf_str:>6} {dd_str:>7}"
            )

        # Detailed breakdown for top 5
        lines.append("")
        lines.append("=" * 80)
        lines.append("TOP 5 DETAILED BREAKDOWN")
        lines.append("=" * 80)

        for r in results[:5]:
            lines.append("")
            lines.append(f"{'='*20} {r.symbol} - {r.name} {'='*20}")
            lines.append(f"Score: {r.score:.0f}/100 | Recommendation: {r.recommendation}")
            lines.append(f"Price: ${r.price:.2f} | Market Cap: ${r.market_cap/1e9:.1f}B")

            s = r.subscores
            lines.append(f"\nSubscores:")
            lines.append(f"  Survival:  {s.survival_total:>5.0f}/30 (Runway:{s.runway_score:.0f} Lever:{s.leverage_score:.0f} Cover:{s.interest_coverage_score:.0f})")
            lines.append(f"  Valuation: {s.valuation_total:>5.0f}/30 (ValPct:{s.valuation_pct_score:.0f} FCF:{s.fcf_yield_score:.0f})")
            lines.append(f"  Fear:      {s.fear_total:>5.0f}/20 (DD:{s.drawdown_score:.0f} Sent:{s.sentiment_score:.0f})")
            lines.append(f"  Structure: {s.structure_total:>5.0f}/20 (MA:{s.ma_score:.0f} RSI:{s.rsi_score:.0f})")

            if r.reason_tags:
                lines.append(f"\nSignals:")
                for tag in r.reason_tags[:5]:
                    lines.append(f"  • {tag}")

            if r.value_trap_warning:
                lines.append(f"\n⚠️  VALUE TRAP WARNING")

        return "\n".join(lines)


# ==================== S&P 500 Universe ====================

# Sample of top 80 S&P 500 stocks (for quick scan)
SP500_SAMPLE = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ',
    'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'ABBV', 'MRK', 'PFE',
    'KO', 'PEP', 'BAC', 'COST', 'TMO', 'AVGO', 'MCD', 'WMT', 'CSCO', 'ACN',
    'LLY', 'DHR', 'ABT', 'VZ', 'ADBE', 'CRM', 'CMCSA', 'NKE', 'INTC', 'AMD',
    'QCOM', 'TXN', 'NEE', 'PM', 'UNP', 'HON', 'IBM', 'LOW', 'AMGN', 'UPS',
    'CAT', 'BA', 'GE', 'RTX', 'DE', 'SBUX', 'GS', 'BLK', 'SPGI', 'AXP',
    'MS', 'BKNG', 'MDLZ', 'GILD', 'LMT', 'SYK', 'ISRG', 'ADI', 'MMC', 'CB',
    'PYPL', 'SQ', 'COIN', 'SNOW', 'PLTR', 'NET', 'DDOG', 'ZS', 'CRWD', 'PANW',
]

# Complete S&P 500 list (as of 2024, ~500 stocks)
SP500_FULL = [
    # ===== Information Technology =====
    'AAPL', 'MSFT', 'NVDA', 'AVGO', 'ORCL', 'CRM', 'CSCO', 'ACN', 'ADBE', 'IBM',
    'AMD', 'TXN', 'QCOM', 'INTU', 'AMAT', 'NOW', 'INTC', 'ADI', 'LRCX', 'MU',
    'KLAC', 'SNPS', 'CDNS', 'PANW', 'CRWD', 'FTNT', 'MCHP', 'APH', 'MSI', 'NXPI',
    'ON', 'KEYS', 'FSLR', 'HPQ', 'HPE', 'DELL', 'NTAP', 'GLW', 'CTSH',
    'IT', 'GDDY', 'WDC', 'ZBRA', 'GEN', 'AKAM', 'SWKS', 'TER', 'QRVO',
    'EPAM', 'FFIV', 'ENPH', 'SEDG', 'MPWR', 'SMCI', 'ANET', 'PLTR', 'SNOW', 'NET',
    'DDOG', 'ZS', 'MDB', 'TEAM', 'OKTA', 'TWLO', 'DOCU', 'ZM', 'VEEV',

    # ===== Communication Services =====
    'GOOGL', 'GOOG', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR',
    'EA', 'TTWO', 'WBD', 'LYV', 'MTCH', 'OMC', 'FOXA', 'FOX',
    'NWSA', 'NWS',

    # ===== Consumer Discretionary =====
    'AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TJX', 'BKNG', 'CMG',
    'MAR', 'ORLY', 'AZO', 'ROST', 'YUM', 'DHI', 'LEN', 'GM', 'F', 'EBAY',
    'APTV', 'BBY', 'DRI', 'HLT', 'LVS', 'MGM', 'WYNN', 'CZR', 'NVR', 'PHM',
    'GRMN', 'POOL', 'ULTA', 'DPZ', 'DECK', 'EXPE', 'RCL', 'CCL', 'NCLH', 'HAS',
    'GPC', 'KMX', 'BWA', 'LEG', 'WHR', 'MHK', 'TPR', 'VFC', 'PVH', 'RL',
    'ETSY', 'W', 'ABNB', 'DASH', 'UBER', 'LYFT', 'CVNA', 'RIVN', 'LCID',

    # ===== Consumer Staples =====
    'PG', 'KO', 'PEP', 'COST', 'WMT', 'PM', 'MO', 'MDLZ', 'CL', 'KMB',
    'GIS', 'K', 'STZ', 'KHC', 'SYY', 'KR', 'HSY', 'MKC', 'ADM', 'BG',
    'CAG', 'HRL', 'CPB', 'SJM', 'TSN', 'CLX', 'CHD', 'EL', 'MNST',
    'TAP', 'KDP', 'LW', 'TGT', 'DG', 'DLTR',

    # ===== Health Care =====
    'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'TMO', 'ABT', 'DHR', 'BMY',
    'AMGN', 'GILD', 'VRTX', 'ISRG', 'MDT', 'SYK', 'REGN', 'BSX', 'ELV', 'CI',
    'CVS', 'MCK', 'HCA', 'ZTS', 'BDX', 'EW', 'DXCM', 'IDXX', 'IQV', 'A',
    'MTD', 'BIIB', 'MRNA', 'HUM', 'CNC', 'MOH', 'CAH', 'ABC', 'ALGN', 'RMD',
    'HOLX', 'COO', 'TFX', 'WST', 'BAX', 'ZBH', 'LH', 'DGX', 'TECH', 'VTRS',
    'CTLT', 'CRL', 'INCY', 'ILMN', 'PKI',

    # ===== Financials =====
    'JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'BLK', 'SPGI', 'AXP',
    'C', 'SCHW', 'CB', 'MMC', 'PGR', 'AON', 'ICE', 'CME', 'USB', 'PNC',
    'TFC', 'AIG', 'MET', 'PRU', 'AFL', 'TRV', 'ALL', 'AJG', 'MSCI', 'MCO',
    'BK', 'COF', 'DFS', 'STT', 'NTRS', 'FITB', 'MTB', 'HBAN', 'CFG', 'RF',
    'KEY', 'CINF', 'L', 'WRB', 'RE', 'GL', 'CBOE', 'NDAQ', 'FDS', 'MKTX',
    'IVZ', 'BEN', 'TROW', 'JKHY', 'WTW', 'HIG', 'RJF', 'ZION', 'CMA',
    'WAL', 'ALLY', 'SYF', 'PYPL', 'SQ', 'COIN', 'HOOD', 'SOFI',

    # ===== Industrials =====
    'CAT', 'GE', 'HON', 'UNP', 'UPS', 'RTX', 'BA', 'DE', 'LMT', 'ADP',
    'MMM', 'GD', 'ITW', 'EMR', 'FDX', 'CSX', 'NSC', 'ETN', 'PH', 'WM',
    'CTAS', 'PCAR', 'JCI', 'ROK', 'TT', 'CARR', 'OTIS', 'FAST', 'VRSK', 'CPRT',
    'PAYX', 'RSG', 'AME', 'IR', 'GWW', 'LHX', 'TDG', 'NOC', 'HWM', 'WAB',
    'DOV', 'SWK', 'XYL', 'EXPD', 'JBHT', 'DAL', 'UAL', 'LUV', 'AAL', 'CHRW',
    'ODFL', 'GNRC', 'PWR', 'J', 'LDOS', 'SAIA', 'RHI', 'MAS', 'HII', 'TXT',
    'IEX', 'PNR', 'AOS', 'NDSN', 'WSO', 'ALLE', 'AXON',

    # ===== Energy =====
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'PXD',
    'WMB', 'KMI', 'HAL', 'DVN', 'FANG', 'BKR', 'OKE', 'CTRA', 'MRO',
    'APA', 'TRGP', 'EQT', 'CF',

    # ===== Utilities =====
    'NEE', 'DUK', 'SO', 'D', 'AEP', 'SRE', 'EXC', 'XEL', 'ED', 'WEC',
    'PEG', 'ES', 'AWK', 'EIX', 'DTE', 'ETR', 'PPL', 'FE', 'AEE', 'CMS',
    'EVRG', 'ATO', 'CNP', 'NI', 'LNT', 'PNW', 'NRG', 'CEG',

    # ===== Real Estate =====
    'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'WELL', 'SPG', 'DLR', 'O', 'VICI',
    'AVB', 'EQR', 'WY', 'VTR', 'ARE', 'EXR', 'IRM', 'MAA', 'UDR', 'SBAC',
    'KIM', 'ESS', 'HST', 'CPT', 'BXP', 'REG', 'FRT', 'SLG', 'VNO', 'AIV',
    'PEAK', 'DOC', 'CUBE', 'NLY', 'AGNC', 'STWD',

    # ===== Materials =====
    'LIN', 'APD', 'SHW', 'ECL', 'FCX', 'NEM', 'NUE', 'VMC', 'MLM', 'DOW',
    'DD', 'PPG', 'CTVA', 'ALB', 'EMN', 'CE', 'FMC', 'IFF', 'IP', 'PKG',
    'AVY', 'WRK', 'SEE', 'CF', 'MOS', 'BALL', 'AMCR', 'CCK',
]

# ==================== NASDAQ 100 ====================
# Top 100 non-financial stocks on NASDAQ (科技股集中，波动大)
NASDAQ_100 = [
    # Mega-cap Tech
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'AVGO', 'COST',
    # Software & Cloud
    'ADBE', 'CRM', 'NFLX', 'CSCO', 'AMD', 'INTC', 'QCOM', 'TXN', 'INTU', 'AMAT',
    'ISRG', 'BKNG', 'ADI', 'LRCX', 'MU', 'KLAC', 'SNPS', 'CDNS', 'MCHP', 'PANW',
    # Growth Tech
    'CRWD', 'FTNT', 'MRVL', 'NXPI', 'ON', 'TEAM', 'WDAY', 'ZS', 'DDOG', 'SNOW',
    'PLTR', 'NET', 'MDB', 'OKTA', 'DOCU', 'ZM', 'VEEV', 'SPLK', 'TWLO', 'ROKU',
    # Consumer & E-commerce
    'AMGN', 'GILD', 'VRTX', 'REGN', 'MRNA', 'BIIB', 'ILMN', 'DXCM', 'IDXX', 'ALGN',
    # Communications & Media
    'CMCSA', 'TMUS', 'CHTR', 'EA', 'TTWO', 'WBD', 'NTES', 'JD', 'PDD',
    # Consumer Discretionary
    'SBUX', 'MAR', 'ORLY', 'AZO', 'ROST', 'LULU', 'EBAY', 'ABNB', 'MELI', 'CPRT',
    # Food & Beverage
    'PEP', 'KHC', 'MDLZ', 'MNST', 'KDP',
    # Other
    'HON', 'ADP', 'PAYX', 'PCAR', 'CSX', 'CTAS', 'ODFL', 'FAST', 'VRSK', 'GEHC',
]

# ==================== S&P 400 Mid-Cap ====================
# S&P 400 中型股 (~400 stocks, 中型成长股)
MIDCAP_400 = [
    # Technology
    'SMCI', 'ANET', 'FFIV', 'MANH', 'PCTY', 'SAIA', 'EXLS', 'GLOB', 'LOGI', 'CGNX',
    'SWKS', 'QRVO', 'CRUS', 'NOVT', 'CACC', 'WEX', 'PLUS', 'CDAY', 'APPF', 'TENB',
    # Healthcare
    'TECH', 'HOLX', 'NVO', 'NBIX', 'EXAS', 'RARE', 'ACAD', 'JAZZ', 'MEDP', 'HZNP',
    'ENSG', 'AMED', 'LHCG', 'ACHC', 'SGRY', 'SEM', 'PINC', 'OMI', 'PRGO', 'PCRX',
    # Financials
    'EWBC', 'COLB', 'FHN', 'PACW', 'OZK', 'CBSH', 'PNFP', 'UMBF', 'IBOC', 'BOKF',
    'SNV', 'FNB', 'FCNCA', 'SFBS', 'WSFS', 'RNST', 'SFNC', 'HOMB', 'UBSI', 'FFIN',
    # Consumer Discretionary
    'WSM', 'DKS', 'BOOT', 'PLNT', 'SIX', 'LKQ', 'GNTX', 'SCI', 'SKX', 'CROX',
    'FL', 'SHAK', 'PLAY', 'RH', 'WOOF', 'FIVE', 'OLLI', 'BJ', 'WING', 'BROS',
    # Industrials
    'RBC', 'GGG', 'RRX', 'TTC', 'SITE', 'AGCO', 'PRMW', 'ALSN', 'MASI', 'TREX',
    'AZEK', 'AAON', 'ESE', 'AIT', 'HRI', 'GHC', 'GATX', 'ALG', 'MATX', 'KNX',
    # Real Estate
    'INVH', 'SUI', 'RHP', 'COLD', 'FR', 'STAG', 'CUZ', 'OHI', 'NNN', 'GTY',
    'STOR', 'PK', 'NSA', 'ELME', 'DEI', 'JBGS', 'PGRE', 'CLI', 'HIW', 'PECO',
    # Energy
    'SM', 'MTDR', 'PDCE', 'CIVI', 'NOG', 'GPOR', 'RRC', 'AR', 'SWN', 'CNX',
    'HESM', 'NS', 'NGL', 'CLMT', 'PARR', 'CVI', 'PBF', 'DINO', 'CEIX', 'ARCH',
    # Materials
    'CLF', 'X', 'RS', 'AA', 'ATI', 'CMC', 'STLD', 'TMST', 'CRS', 'HAYN',
    'SON', 'SLVM', 'OI', 'GEF', 'BERY', 'GPK', 'ATR', 'BCPC', 'KWR', 'CBT',
    # Consumer Staples
    'BG', 'POST', 'HRL', 'FLO', 'CASY', 'INGR', 'JJSF', 'THS', 'CHEF', 'LANC',
    'FIZZ', 'CELH', 'FRPT', 'CALM', 'JBSS', 'SMPL', 'DAR', 'VITL', 'USFD', 'PFGC',
    # Utilities
    'AVA', 'OGE', 'POR', 'BKH', 'NWE', 'MGEE', 'SR', 'UTL', 'SJW', 'OTTR',
]

# ==================== Sector ETFs ====================
# 行业ETF，用于行业轮动分析
SECTOR_ETFS = [
    # SPDR Sector ETFs (11 sectors)
    'XLK',   # Technology
    'XLV',   # Health Care
    'XLF',   # Financials
    'XLY',   # Consumer Discretionary
    'XLP',   # Consumer Staples
    'XLE',   # Energy
    'XLI',   # Industrials
    'XLB',   # Materials
    'XLU',   # Utilities
    'XLRE',  # Real Estate
    'XLC',   # Communication Services

    # Thematic ETFs
    'SMH',   # Semiconductors (VanEck)
    'SOXX',  # Semiconductors (iShares)
    'IGV',   # Software (iShares)
    'ARKK',  # Innovation (ARK)
    'ARKG',  # Genomics (ARK)
    'ARKF',  # Fintech (ARK)
    'ARKW',  # Internet (ARK)
    'BOTZ',  # Robotics & AI
    'ROBO',  # Robotics & Automation
    'HACK',  # Cybersecurity
    'CIBR',  # Cybersecurity
    'CLOU',  # Cloud Computing
    'WCLD',  # Cloud Computing
    'FINX',  # Fintech
    'OGIG',  # Internet Giants

    # Factor ETFs
    'VTV',   # Value
    'VUG',   # Growth
    'MTUM',  # Momentum
    'QUAL',  # Quality
    'USMV',  # Min Volatility
    'SIZE',  # Small Cap

    # Bond & Fixed Income
    'TLT',   # 20+ Year Treasury
    'IEF',   # 7-10 Year Treasury
    'SHY',   # 1-3 Year Treasury
    'SGOV',  # 0-3 Month Treasury (iShares) 短期国债
    'BIL',   # 1-3 Month Treasury (SPDR) 超短期国债
    'SCHO',  # 1-3 Year Treasury Short-Term (Schwab)
    'LQD',   # Investment Grade Corporate
    'HYG',   # High Yield Corporate
    'TIP',   # TIPS

    # International
    'EFA',   # EAFE (Developed ex-US)
    'EEM',   # Emerging Markets
    'FXI',   # China Large Cap
    'EWJ',   # Japan
    'EWG',   # Germany
    'EWU',   # UK

    # Commodities
    'GLD',   # Gold
    'SLV',   # Silver
    'USO',   # Oil
    'UNG',   # Natural Gas
    'DBA',   # Agriculture
    'DBC',   # Commodities Broad
]

# ==================== Dividend Aristocrats ====================
# 连续25年以上增加股息的公司 (~65 stocks)
DIVIDEND_ARISTOCRATS = [
    # Consumer Staples
    'PG', 'KO', 'PEP', 'CL', 'CLX', 'KMB', 'SYY', 'ADM', 'HRL', 'MKC',
    'BF-B', 'GPC', 'TROW', 'SWK', 'GWW', 'PPG', 'SHW', 'ECL', 'ITW', 'EMR',
    # Healthcare
    'JNJ', 'ABBV', 'ABT', 'MDT', 'BDX', 'CAH',
    # Financials
    'AFL', 'CINF', 'CB', 'BEN', 'FRT', 'SPGI', 'T', 'ATO', 'ED', 'SO',
    # Industrials
    'MMM', 'CAT', 'DOV', 'GD', 'PH', 'ROP', 'APD', 'LIN', 'NUE', 'AOS',
    'CTAS', 'EXPD',
    # Utilities
    'NEE', 'AWK', 'WM', 'ADP',
    # Materials
    'APD', 'LIN', 'NUE', 'SHW', 'PPG', 'ECL',
    # REITs
    'O', 'FRT', 'ESS', 'WPC',
    # Technology
    'IBM', 'KLAC', 'NDSN', 'BRO', 'RHI',
    # Energy
    'XOM', 'CVX', 'TRGP',
    # Additional Aristocrats
    'LOW', 'TGT', 'WMT', 'MCD', 'LEG', 'VFC', 'PBCT', 'KHC', 'ED', 'XEL',
    'PNR', 'CHD', 'AMCR', 'ALB', 'CHRW', 'FAST', 'WST', 'POOL', 'RSG', 'STE',
]

# ==================== Combined Universe (去重) ====================
def get_combined_universe(*universes) -> List[str]:
    """Combine multiple universes and remove duplicates"""
    combined = []
    seen = set()
    for universe in universes:
        for symbol in universe:
            if symbol not in seen:
                combined.append(symbol)
                seen.add(symbol)
    return combined


if __name__ == "__main__":
    print("Running Stock Scanner...")
    print()

    # Use smaller universe for testing
    scanner = StockScanner(universe=SP500_SAMPLE[:30])

    results = scanner.scan_all(top_n=10, min_score=40, max_workers=3)

    print()
    print(scanner.format_scan_report(results))
