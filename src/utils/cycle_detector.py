"""
Cycle Detector - Risk/Rate/AI Cycle Detection

Detects three key market cycles:
1. Risk Cycle: risk_on / neutral / risk_off
2. Rate Cycle: ease / neutral / tight
3. AI Cycle: off / early / broad

Uses these cycles to generate portfolio role tilts (CORE/AI/DEFENSE/INCOME/HEDGE)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta


@dataclass
class CycleState:
    """Current state of all three cycles"""
    # Risk Cycle
    risk_regime: str  # risk_on, neutral, risk_off
    risk_score: float  # -1 to +1
    risk_notes: List[str]

    # Rate Cycle
    rate_regime: str  # ease, neutral, tight
    rate_score: float  # -1 to +1
    rate_notes: List[str]

    # AI Cycle
    ai_regime: str  # off, early, broad
    ai_score: float  # -1 to +1
    ai_notes: List[str]

    # Role Tilts (calculated from cycles)
    role_tilts: Dict[str, int]  # role -> tilt score (-4 to +4)
    role_suggestions: Dict[str, str]  # role -> OW/N/UW

    def __str__(self):
        return (f"Risk: {self.risk_regime} | Rate: {self.rate_regime} | AI: {self.ai_regime}")


class CycleDetector:
    """
    Detects market cycles and generates portfolio tilts

    Risk Cycle: VIX-based with SPY momentum confirmation
    Rate Cycle: 10Y yield level + direction + curve shape
    AI Cycle: Semiconductor/Software relative strength + infrastructure diffusion
    """

    # VIX thresholds for risk regime
    VIX_RISK_OFF = 25
    VIX_RISK_ON = 15

    # Role tilt matrices
    # Format: {regime: {role: tilt}}
    # Tilt: +2 = strong OW, +1 = OW, 0 = neutral, -1 = UW, -2 = strong UW

    RISK_TILTS = {
        'risk_on': {'CORE': 1, 'AI': 2, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': -1},
        'neutral': {'CORE': 0, 'AI': 0, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 0},
        'risk_off': {'CORE': 0, 'AI': -2, 'DEFENSE': 1, 'INCOME': 1, 'HEDGE': 2},
    }

    RATE_TILTS = {
        'tight': {'CORE': 0, 'AI': -1, 'DEFENSE': 0, 'INCOME': 1, 'HEDGE': 1},
        'neutral': {'CORE': 0, 'AI': 0, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 0},
        'ease': {'CORE': 1, 'AI': 1, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 1},
    }

    AI_TILTS = {
        'off': {'CORE': 0, 'AI': -2, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 0},
        'early': {'CORE': 0, 'AI': 1, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 0},
        'broad': {'CORE': 0, 'AI': 2, 'DEFENSE': 0, 'INCOME': 0, 'HEDGE': 0},
    }

    def __init__(self):
        self.cache = {}

    def _get_price_data(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Get historical price data with caching"""
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

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price"""
        hist = self._get_price_data(symbol, "5d")
        if hist is not None and len(hist) > 0:
            return hist['Close'].iloc[-1]
        return None

    def _calc_return(self, hist: pd.DataFrame, days: int) -> Optional[float]:
        """Calculate return over N trading days"""
        if hist is None or len(hist) < days:
            return None
        try:
            end_price = hist['Close'].iloc[-1]
            start_price = hist['Close'].iloc[-days]
            return (end_price / start_price - 1) * 100
        except:
            return None

    def _calc_relative_strength(self, symbol: str, benchmark: str = "SPY", days: int = 63) -> Optional[float]:
        """
        Calculate relative strength vs benchmark
        Returns excess return in percentage points
        """
        sym_hist = self._get_price_data(symbol)
        bench_hist = self._get_price_data(benchmark)

        if sym_hist is None or bench_hist is None:
            return None

        sym_ret = self._calc_return(sym_hist, days)
        bench_ret = self._calc_return(bench_hist, days)

        if sym_ret is None or bench_ret is None:
            return None

        return sym_ret - bench_ret

    def detect_risk_cycle(self) -> Tuple[str, float, List[str]]:
        """
        Detect Risk Cycle using VIX + SPY momentum

        Returns: (regime, score, notes)
        """
        notes = []

        # Get VIX
        vix_hist = self._get_price_data("^VIX", "3mo")
        vix_current = None
        vix_avg_20d = None

        if vix_hist is not None and len(vix_hist) > 0:
            vix_current = vix_hist['Close'].iloc[-1]
            if len(vix_hist) >= 20:
                vix_avg_20d = vix_hist['Close'].tail(20).mean()

        # Get SPY momentum
        spy_hist = self._get_price_data("SPY")
        spy_3m_ret = self._calc_return(spy_hist, 63) if spy_hist is not None else None
        spy_6m_ret = self._calc_return(spy_hist, 126) if spy_hist is not None else None

        # Calculate max drawdown in last 3 months
        spy_drawdown = None
        if spy_hist is not None and len(spy_hist) >= 63:
            recent = spy_hist['Close'].tail(63)
            peak = recent.expanding().max()
            drawdown = (recent - peak) / peak * 100
            spy_drawdown = drawdown.min()

        # Determine regime
        regime = 'neutral'
        score = 0.0

        if vix_current is not None:
            notes.append(f"VIX: {vix_current:.1f}")

            # Primary VIX classification
            if vix_current >= self.VIX_RISK_OFF:
                regime = 'risk_off'
                score = -0.7
                notes.append("VIX >= 25: Risk-Off signal")
            elif vix_current < self.VIX_RISK_ON:
                regime = 'risk_on'
                score = 0.7
                notes.append("VIX < 15: Risk-On signal")
            else:
                regime = 'neutral'
                score = 0.0
                notes.append("VIX 15-25: Neutral")

        # SPY momentum confirmation/override
        if spy_3m_ret is not None:
            notes.append(f"SPY 3M: {spy_3m_ret:+.1f}%")

            # Force risk_off if significant drawdown + elevated VIX
            if spy_drawdown is not None and spy_drawdown < -10 and vix_current and vix_current > 20:
                regime = 'risk_off'
                score = -0.9
                notes.append(f"Drawdown {spy_drawdown:.1f}% + VIX>20: Force Risk-Off")

            # Force risk_on if strong momentum + low VIX
            elif spy_6m_ret is not None and spy_6m_ret > 10 and vix_current and vix_current < 15:
                regime = 'risk_on'
                score = 0.9
                notes.append(f"SPY 6M +{spy_6m_ret:.1f}% + VIX<15: Confirm Risk-On")

        return regime, score, notes

    def detect_rate_cycle(self) -> Tuple[str, float, List[str]]:
        """
        Detect Rate Cycle using 10Y yield + curve shape

        Returns: (regime, score, notes)
        """
        notes = []

        # Get 10Y yield (^TNX)
        tnx_hist = self._get_price_data("^TNX", "2y")
        tnx_current = None
        tnx_3m_change = None
        tnx_percentile = None

        if tnx_hist is not None and len(tnx_hist) > 0:
            tnx_current = tnx_hist['Close'].iloc[-1]

            if len(tnx_hist) >= 63:
                tnx_3m_ago = tnx_hist['Close'].iloc[-63]
                tnx_3m_change = tnx_current - tnx_3m_ago

            # Calculate percentile over 2 years
            if len(tnx_hist) >= 252:
                tnx_percentile = (tnx_hist['Close'] <= tnx_current).sum() / len(tnx_hist) * 100

        # Get 2Y yield (^IRX is 13-week, use ^TWO for 2Y)
        # Note: ^TNX is 10Y, we'll approximate curve with available data
        irx_hist = self._get_price_data("^IRX", "1y")  # 13-week T-bill
        curve_spread = None

        if tnx_current is not None and irx_hist is not None and len(irx_hist) > 0:
            irx_current = irx_hist['Close'].iloc[-1] / 100  # IRX is in basis points
            # Approximate 10Y-2Y spread (using 13-week as proxy, adjust)
            curve_spread = tnx_current - (irx_current * 10)  # Rough proxy

        # Determine regime
        regime = 'neutral'
        score = 0.0

        if tnx_current is not None:
            notes.append(f"10Y: {tnx_current:.2f}%")

            if tnx_3m_change is not None:
                notes.append(f"3M Change: {tnx_3m_change:+.2f}%")

                # Rate direction + level classification
                if tnx_3m_change > 0.3 and tnx_percentile and tnx_percentile > 70:
                    regime = 'tight'
                    score = -0.7
                    notes.append("Rising rates + high level: Tight")
                elif tnx_3m_change < -0.3 and tnx_percentile and tnx_percentile < 50:
                    regime = 'ease'
                    score = 0.7
                    notes.append("Falling rates + lower level: Ease")
                else:
                    regime = 'neutral'
                    notes.append("Rates stable: Neutral")

            # Curve shape adjustment
            if curve_spread is not None:
                if curve_spread < -0.5:
                    notes.append(f"Curve inverted: Still tight bias")
                    if regime == 'neutral':
                        regime = 'tight'
                        score = -0.3
                elif curve_spread > 0.5:
                    notes.append(f"Curve positive: Easing bias")

        return regime, score, notes

    def detect_ai_cycle(self, risk_regime: str) -> Tuple[str, float, List[str]]:
        """
        Detect AI Cycle using semiconductor/software relative strength + infrastructure diffusion

        Key insight: Not just "is AI up" but "is AI getting sustained capital/orders"

        Returns: (regime, score, notes)
        """
        notes = []

        # AI Chain: Semiconductors (compute)
        smh_rs_3m = self._calc_relative_strength("SMH", "SPY", 63)
        soxx_rs_3m = self._calc_relative_strength("SOXX", "SPY", 63)

        # AI Software
        igv_rs_3m = self._calc_relative_strength("IGV", "SPY", 63)

        # AI Infrastructure (power/data centers)
        xlu_rs_3m = self._calc_relative_strength("XLU", "SPY", 63)
        grid_data = self._get_price_data("GRID")
        grid_rs_3m = self._calc_relative_strength("GRID", "SPY", 63) if grid_data is not None and len(grid_data) > 0 else None

        # Calculate 6M relative strength for trend
        smh_rs_6m = self._calc_relative_strength("SMH", "SPY", 126)

        # Aggregate compute strength
        compute_scores = [s for s in [smh_rs_3m, soxx_rs_3m] if s is not None]
        compute_avg = np.mean(compute_scores) if compute_scores else None

        # Aggregate software strength
        software_avg = igv_rs_3m

        # Aggregate infrastructure strength
        infra_scores = [s for s in [xlu_rs_3m, grid_rs_3m] if s is not None]
        infra_avg = np.mean(infra_scores) if infra_scores else None

        # Log data
        if compute_avg is not None:
            notes.append(f"Compute RS: {compute_avg:+.1f}%")
        if software_avg is not None:
            notes.append(f"Software RS: {software_avg:+.1f}%")
        if infra_avg is not None:
            notes.append(f"Infra RS: {infra_avg:+.1f}%")

        # Determine regime
        regime = 'off'
        score = 0.0

        # Check if compute is strong (core AI signal)
        compute_strong = compute_avg is not None and compute_avg > 2
        compute_weak = compute_avg is not None and compute_avg < -5

        # Check if infrastructure is strong (diffusion signal)
        infra_strong = infra_avg is not None and infra_avg > 0

        # Check momentum trend (is it accelerating?)
        compute_accelerating = (smh_rs_3m is not None and smh_rs_6m is not None and
                                smh_rs_3m > smh_rs_6m / 2)  # 3M stronger than half of 6M

        if compute_weak:
            regime = 'off'
            score = -0.8
            notes.append("Compute weak: AI Off")
        elif compute_strong and infra_strong:
            regime = 'broad'
            score = 0.9
            notes.append("Compute + Infra strong: AI Broad")
        elif compute_strong:
            regime = 'early'
            score = 0.5
            notes.append("Compute strong, Infra lagging: AI Early")
        elif compute_accelerating:
            regime = 'early'
            score = 0.3
            notes.append("Compute accelerating: AI Early")
        else:
            regime = 'off'
            score = -0.3
            notes.append("No clear AI leadership: AI Off")

        # Risk regime gate: downgrade AI in risk_off
        if risk_regime == 'risk_off' and regime == 'broad':
            regime = 'early'
            score = score * 0.5
            notes.append("Risk-Off gate: AI Broad -> Early")

        return regime, score, notes

    def calculate_role_tilts(self, risk_regime: str, rate_regime: str, ai_regime: str) -> Tuple[Dict[str, int], Dict[str, str]]:
        """
        Calculate role tilts from the three cycle regimes

        Returns: (tilts dict, suggestions dict)
        """
        roles = ['CORE', 'AI', 'DEFENSE', 'INCOME', 'HEDGE']
        tilts = {role: 0 for role in roles}

        # Sum tilts from all three matrices
        for role in roles:
            tilts[role] += self.RISK_TILTS.get(risk_regime, {}).get(role, 0)
            tilts[role] += self.RATE_TILTS.get(rate_regime, {}).get(role, 0)
            tilts[role] += self.AI_TILTS.get(ai_regime, {}).get(role, 0)

        # Map to suggestions
        suggestions = {}
        for role, tilt in tilts.items():
            if tilt >= 2:
                suggestions[role] = 'OW++'  # Strong overweight
            elif tilt == 1:
                suggestions[role] = 'OW'    # Overweight
            elif tilt == 0:
                suggestions[role] = 'N'     # Neutral
            elif tilt == -1:
                suggestions[role] = 'UW'    # Underweight
            else:  # tilt <= -2
                suggestions[role] = 'UW--'  # Strong underweight

        return tilts, suggestions

    def detect_cycles(self) -> CycleState:
        """
        Run full cycle detection and return CycleState

        This is the main entry point.
        """
        # Detect each cycle
        risk_regime, risk_score, risk_notes = self.detect_risk_cycle()
        rate_regime, rate_score, rate_notes = self.detect_rate_cycle()
        ai_regime, ai_score, ai_notes = self.detect_ai_cycle(risk_regime)

        # Calculate role tilts
        role_tilts, role_suggestions = self.calculate_role_tilts(
            risk_regime, rate_regime, ai_regime
        )

        return CycleState(
            risk_regime=risk_regime,
            risk_score=risk_score,
            risk_notes=risk_notes,
            rate_regime=rate_regime,
            rate_score=rate_score,
            rate_notes=rate_notes,
            ai_regime=ai_regime,
            ai_score=ai_score,
            ai_notes=ai_notes,
            role_tilts=role_tilts,
            role_suggestions=role_suggestions
        )

    def format_cycle_report(self, state: CycleState) -> str:
        """Format cycle state as text report"""
        lines = []
        lines.append("=" * 60)
        lines.append("MARKET CYCLE ANALYSIS")
        lines.append("=" * 60)

        # Risk Cycle
        lines.append(f"\n{'='*20} RISK CYCLE {'='*20}")
        lines.append(f"Regime: {state.risk_regime.upper()} (score: {state.risk_score:+.2f})")
        for note in state.risk_notes:
            lines.append(f"  • {note}")

        # Rate Cycle
        lines.append(f"\n{'='*20} RATE CYCLE {'='*20}")
        lines.append(f"Regime: {state.rate_regime.upper()} (score: {state.rate_score:+.2f})")
        for note in state.rate_notes:
            lines.append(f"  • {note}")

        # AI Cycle
        lines.append(f"\n{'='*20} AI CYCLE {'='*20}")
        lines.append(f"Regime: {state.ai_regime.upper()} (score: {state.ai_score:+.2f})")
        for note in state.ai_notes:
            lines.append(f"  • {note}")

        # Role Tilts
        lines.append(f"\n{'='*20} ROLE TILTS {'='*20}")
        lines.append(f"{'Role':<12} {'Tilt':>6} {'Suggestion':>12}")
        lines.append("-" * 32)

        tilt_emoji = {
            'OW++': '🟢🟢',
            'OW': '🟢',
            'N': '⚪',
            'UW': '🔴',
            'UW--': '🔴🔴'
        }

        for role in ['CORE', 'AI', 'DEFENSE', 'INCOME', 'HEDGE']:
            tilt = state.role_tilts.get(role, 0)
            suggestion = state.role_suggestions.get(role, 'N')
            emoji = tilt_emoji.get(suggestion, '')
            lines.append(f"{role:<12} {tilt:>+6} {suggestion:>8} {emoji}")

        return "\n".join(lines)


# Convenience function for quick cycle check
def get_current_cycles() -> CycleState:
    """Quick function to get current cycle state"""
    detector = CycleDetector()
    return detector.detect_cycles()


if __name__ == "__main__":
    print("Running Cycle Detection...")
    print()

    detector = CycleDetector()
    state = detector.detect_cycles()

    print(detector.format_cycle_report(state))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Risk: {state.risk_regime} | Rate: {state.rate_regime} | AI: {state.ai_regime}")
    print()
    print("Role Allocation Suggestions:")
    for role, suggestion in state.role_suggestions.items():
        print(f"  {role}: {suggestion}")
