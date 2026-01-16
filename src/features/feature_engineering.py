"""
Feature engineering for crash prediction
7 feature categories (100+ features):

1. Volatility (VIX level, VIX jumps, volatility of volatility)
2. Trend (MA crossovers, distance from MAs, death cross)
3. Tail risk (drawdowns, skewness, kurtosis, VaR)
4. Momentum (RSI, MACD, ROC, acceleration)
5. Correlation (SPY-QQQ, SPY-VIX correlations)
6. Risk appetite (QQQ/SPY ratio, volume trends)
7. Credit & Liquidity (HYG/LQD spread, SKEW, Gold+VIX, SPY/RSP, stress index) - NEW!
"""
import pandas as pd
import numpy as np
from typing import Dict, List


class CrashFeatureEngine:
    """Feature engineering for crash prediction"""

    def __init__(self):
        """Initialize feature engineering"""
        self.feature_names: List[str] = []

    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create all features for crash prediction

        Args:
            data: DataFrame with SPY, QQQ, VIX columns

        Returns:
            DataFrame with all features
        """
        df = data.copy()

        # Category 1: Volatility features
        df = self._add_volatility_features(df)

        # Category 2: Trend features
        df = self._add_trend_features(df)

        # Category 3: Tail risk features
        df = self._add_tail_risk_features(df)

        # Category 4: Momentum features
        df = self._add_momentum_features(df)

        # Category 5: Correlation features
        df = self._add_correlation_features(df)

        # Category 6: Risk appetite features
        df = self._add_risk_appetite_features(df)

        # Category 7: Credit & Liquidity features (NEW)
        df = self._add_credit_liquidity_features(df)

        return df

    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 1: Volatility features

        Features:
        - VIX level
        - VIX change (1-day, 5-day, 20-day)
        - VIX jump indicator (>10% increase)
        - VIX percentile (rolling 252 days)
        """
        # VIX level
        df['vix_level'] = df['VIX']

        # VIX changes
        df['vix_change_1d'] = df['VIX'].pct_change(1)
        df['vix_change_5d'] = df['VIX'].pct_change(5)
        df['vix_change_20d'] = df['VIX'].pct_change(20)

        # VIX jump indicator
        df['vix_jump'] = (df['vix_change_1d'] > 0.10).astype(int)

        # VIX percentile (where is VIX relative to past year)
        df['vix_percentile'] = df['VIX'].rolling(252).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) == 252 else np.nan
        )

        # VIX above 20 (fear threshold)
        df['vix_above_20'] = (df['VIX'] > 20).astype(int)

        # VIX above 30 (panic threshold)
        df['vix_above_30'] = (df['VIX'] > 30).astype(int)

        return df

    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 2: Trend features

        Features:
        - SPY vs MA200 (distance and cross)
        - QQQ vs MA200 (distance and cross)
        - MA50 vs MA200 (golden cross / death cross)
        """
        # Calculate moving averages
        for col in ['SPY', 'QQQ']:
            df[f'{col}_ma20'] = df[col].rolling(20).mean()
            df[f'{col}_ma50'] = df[col].rolling(50).mean()
            df[f'{col}_ma200'] = df[col].rolling(200).mean()

            # Distance from MA200 (%)
            df[f'{col}_vs_ma200'] = (df[col] / df[f'{col}_ma200'] - 1) * 100

            # Below MA200 indicator
            df[f'{col}_below_ma200'] = (df[col] < df[f'{col}_ma200']).astype(int)

            # MA50 vs MA200 (golden cross = 1, death cross = -1)
            df[f'{col}_ma50_vs_ma200'] = (df[f'{col}_ma50'] / df[f'{col}_ma200'] - 1) * 100

            # Death cross indicator
            df[f'{col}_death_cross'] = (df[f'{col}_ma50'] < df[f'{col}_ma200']).astype(int)

        return df

    def _add_tail_risk_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 3: Tail risk features

        Features:
        - Frequency of negative returns (rolling windows)
        - Frequency of large negative returns (<-2%)
        - Maximum drawdown in rolling window
        - Skewness of returns
        """
        # Calculate returns
        df['spy_return'] = df['SPY'].pct_change()
        df['qqq_return'] = df['QQQ'].pct_change()

        # Rolling negative return frequency
        for window in [20, 60]:
            df[f'spy_neg_freq_{window}d'] = (
                df['spy_return'].rolling(window).apply(lambda x: (x < 0).sum() / len(x))
            )
            df[f'qqq_neg_freq_{window}d'] = (
                df['qqq_return'].rolling(window).apply(lambda x: (x < 0).sum() / len(x))
            )

        # Large negative return frequency (<-2%)
        for window in [20, 60]:
            df[f'spy_large_neg_freq_{window}d'] = (
                df['spy_return'].rolling(window).apply(lambda x: (x < -0.02).sum() / len(x))
            )
            df[f'qqq_large_neg_freq_{window}d'] = (
                df['qqq_return'].rolling(window).apply(lambda x: (x < -0.02).sum() / len(x))
            )

        # Rolling maximum drawdown
        def max_drawdown(prices):
            cummax = pd.Series(prices).cummax()
            drawdown = (pd.Series(prices) - cummax) / cummax
            return drawdown.min()

        for window in [20, 60]:
            df[f'spy_max_dd_{window}d'] = (
                df['SPY'].rolling(window).apply(max_drawdown)
            )
            df[f'qqq_max_dd_{window}d'] = (
                df['QQQ'].rolling(window).apply(max_drawdown)
            )

        # Return skewness (negative skew = left tail)
        for window in [60]:
            df[f'spy_skew_{window}d'] = df['spy_return'].rolling(window).skew()
            df[f'qqq_skew_{window}d'] = df['qqq_return'].rolling(window).skew()

        return df

    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 4: Momentum features

        Features:
        - RSI (14-day)
        - Rate of change (ROC)
        - MACD
        """
        # RSI calculation
        for col in ['SPY', 'QQQ']:
            delta = df[col].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

            rs = gain / loss
            df[f'{col}_rsi'] = 100 - (100 / (1 + rs))

            # RSI overbought (>70)
            df[f'{col}_rsi_overbought'] = (df[f'{col}_rsi'] > 70).astype(int)

            # RSI oversold (<30)
            df[f'{col}_rsi_oversold'] = (df[f'{col}_rsi'] < 30).astype(int)

        # Rate of Change (ROC)
        for col in ['SPY', 'QQQ']:
            for period in [10, 20]:
                df[f'{col}_roc_{period}d'] = (
                    (df[col] / df[col].shift(period) - 1) * 100
                )

        # MACD
        for col in ['SPY', 'QQQ']:
            ema12 = df[col].ewm(span=12, adjust=False).mean()
            ema26 = df[col].ewm(span=26, adjust=False).mean()
            df[f'{col}_macd'] = ema12 - ema26
            df[f'{col}_macd_signal'] = df[f'{col}_macd'].ewm(span=9, adjust=False).mean()
            df[f'{col}_macd_diff'] = df[f'{col}_macd'] - df[f'{col}_macd_signal']

        return df

    def _add_correlation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 5: Correlation features

        Features:
        - SPY-QQQ rolling correlation
        - High correlation indicator (crashes = high correlation)
        """
        # Rolling correlation
        for window in [20, 60]:
            df[f'spy_qqq_corr_{window}d'] = (
                df['spy_return'].rolling(window).corr(df['qqq_return'])
            )

            # High correlation indicator (>0.9)
            df[f'high_corr_{window}d'] = (
                df[f'spy_qqq_corr_{window}d'] > 0.9
            ).astype(int)

        return df

    def _add_risk_appetite_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 6: Risk appetite features

        Features:
        - QQQ/SPY ratio (tech vs broad market)
        - QQQ/SPY ratio trend
        - Tech underperformance indicator
        """
        # QQQ/SPY ratio
        df['qqq_spy_ratio'] = df['QQQ'] / df['SPY']

        # Ratio trend (is tech outperforming or underperforming?)
        df['qqq_spy_ratio_ma20'] = df['qqq_spy_ratio'].rolling(20).mean()
        df['qqq_spy_ratio_vs_ma'] = (
            (df['qqq_spy_ratio'] / df['qqq_spy_ratio_ma20'] - 1) * 100
        )

        # Tech underperformance indicator
        df['tech_underperform'] = (df['qqq_spy_ratio_vs_ma'] < -2).astype(int)

        # Relative strength
        df['qqq_spy_ratio_change_20d'] = df['qqq_spy_ratio'].pct_change(20) * 100

        return df

    def _add_credit_liquidity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Category 7: Credit & Liquidity features (INSTITUTIONAL-GRADE INDICATORS)

        Features:
        1. Credit Spread (HYG/LQD ratio) - Credit risk indicator
        2. Credit Spread Widening - Acceleration of credit stress
        3. SKEW Index - Tail risk / black swan probability
        4. Gold + VIX同涨 - Flight to safety + fear combo
        5. SPY/RSP Divergence - Market breadth deterioration
        6. Liquidity Proxy - Volume + volatility based
        7. Stress Composite Index - Multi-factor stress gauge
        8. Stress Acceleration - Rate of stress increase
        """

        # ========== 1. CREDIT SPREAD FEATURES ==========
        if 'HYG' in df.columns and 'LQD' in df.columns:
            # HYG/LQD ratio (high yield vs investment grade)
            # Lower ratio = credit stress (high yield underperforming)
            df['credit_spread_ratio'] = df['HYG'] / df['LQD']

            # Credit spread change
            df['credit_spread_change_5d'] = df['credit_spread_ratio'].pct_change(5) * 100
            df['credit_spread_change_20d'] = df['credit_spread_ratio'].pct_change(20) * 100

            # Credit spread widening indicator (ratio falling = widening spreads)
            df['credit_stress'] = (df['credit_spread_change_5d'] < -2).astype(int)

            # Credit spread percentile (where are we in historical range?)
            df['credit_spread_percentile'] = df['credit_spread_ratio'].rolling(252).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) == 252 else np.nan
            )

            # Credit spread vs MA (trend detection)
            df['credit_spread_ma20'] = df['credit_spread_ratio'].rolling(20).mean()
            df['credit_spread_vs_ma'] = (
                (df['credit_spread_ratio'] / df['credit_spread_ma20'] - 1) * 100
            )

        # ========== 2. SKEW INDEX FEATURES ==========
        if 'SKEW' in df.columns:
            # SKEW level (>135 = elevated tail risk)
            df['skew_level'] = df['SKEW']

            # SKEW changes
            df['skew_change_5d'] = df['SKEW'].pct_change(5) * 100
            df['skew_change_20d'] = df['SKEW'].pct_change(20) * 100

            # SKEW spike (sudden increase in tail risk)
            df['skew_spike'] = (df['skew_change_5d'] > 5).astype(int)

            # SKEW above 135 (elevated tail risk threshold)
            df['skew_elevated'] = (df['SKEW'] > 135).astype(int)

            # SKEW above 145 (extreme tail risk)
            df['skew_extreme'] = (df['SKEW'] > 145).astype(int)

        # ========== 3. GOLD + VIX 同涨 SIGNAL ==========
        if 'GLD' in df.columns:
            # Gold returns
            df['gld_return_5d'] = df['GLD'].pct_change(5) * 100
            df['gld_return_20d'] = df['GLD'].pct_change(20) * 100

            # VIX returns (already have VIX changes)
            # Reuse existing vix_change_5d and vix_change_20d

            # Gold + VIX both rising = flight to safety + fear
            # This is a RARE and POWERFUL crash signal
            df['gold_vix_combo_5d'] = (
                (df['gld_return_5d'] > 2) & (df['vix_change_5d'] > 0.10)
            ).astype(int)

            df['gold_vix_combo_20d'] = (
                (df['gld_return_20d'] > 5) & (df['vix_change_20d'] > 0.20)
            ).astype(int)

            # Gold/SPY ratio (safe haven preference)
            df['gold_spy_ratio'] = df['GLD'] / df['SPY']
            df['gold_spy_ratio_change_20d'] = df['gold_spy_ratio'].pct_change(20) * 100

        # ========== 4. SPY/RSP DIVERGENCE (BREADTH) ==========
        if 'RSP' in df.columns:
            # SPY/RSP ratio (cap-weighted vs equal-weight)
            # Rising = large caps outperforming = narrow market = fragile
            df['spy_rsp_ratio'] = df['SPY'] / df['RSP']

            # Ratio changes
            df['spy_rsp_divergence_5d'] = df['spy_rsp_ratio'].pct_change(5) * 100
            df['spy_rsp_divergence_20d'] = df['spy_rsp_ratio'].pct_change(20) * 100

            # Narrow market indicator (large caps leading = warning)
            df['narrow_market'] = (df['spy_rsp_divergence_20d'] > 3).astype(int)

            # Breadth deterioration (RSP underperforming badly)
            df['breadth_deterioration'] = (df['spy_rsp_divergence_5d'] > 1.5).astype(int)

        # ========== 5. LIQUIDITY PROXY ==========
        # Combine volume trends with volatility
        if 'SPY_Volume' in df.columns:
            # Volume moving averages
            df['spy_volume_ma20'] = df['SPY_Volume'].rolling(20).mean()

            # Volume surge (>1.5x average)
            df['volume_surge'] = (
                df['SPY_Volume'] / df['spy_volume_ma20'] > 1.5
            ).astype(int)

            # Volume trend
            df['volume_trend'] = df['SPY_Volume'].pct_change(20) * 100

            # Liquidity stress = low volume + high volatility
            df['liquidity_stress'] = (
                (df['volume_trend'] < -10) & (df['vix_level'] > 20)
            ).astype(int)

        # ========== 6. FALSE CALM DETECTOR (NEW!) ==========
        # Detects "false calm" - when surface looks calm but smart money is hedging
        # Triggers when: VIX low + SKEW high + credit spread widening
        # This catches the dangerous "calm before the storm" scenario

        false_calm_conditions = []

        # Condition 1: VIX appears calm (< 18)
        if 'VIX' in df.columns:
            vix_calm = df['VIX'] < 18
            false_calm_conditions.append(vix_calm)

        # Condition 2: SKEW elevated (> 135) - institutions buying tail protection
        if 'SKEW' in df.columns:
            skew_high = df['SKEW'] > 135
            false_calm_conditions.append(skew_high)

        # Condition 3: Credit spread widening (HYG underperforming LQD)
        if 'credit_spread_change_5d' in df.columns:
            credit_widening = df['credit_spread_change_5d'] < -1  # ratio falling = spread widening
            false_calm_conditions.append(credit_widening)

        # False Calm Detector: All three conditions met
        if len(false_calm_conditions) == 3:
            df['false_calm_detector'] = (
                false_calm_conditions[0] &
                false_calm_conditions[1] &
                false_calm_conditions[2]
            ).astype(int)

            # Also create a "soft" version with 2 out of 3 conditions
            df['false_calm_soft'] = (
                (false_calm_conditions[0].astype(int) +
                 false_calm_conditions[1].astype(int) +
                 false_calm_conditions[2].astype(int)) >= 2
            ).astype(int)
        else:
            df['false_calm_detector'] = 0
            df['false_calm_soft'] = 0

        # ========== 7. STRESS COMPOSITE INDEX (IMPROVED WITH Z-SCORE + PERCENTILE) ==========
        # Step 1: Standardize each component using z-score (removes scale differences)
        # Step 2: Weighted combination of z-scores
        # Step 3: Convert to percentile (0-100) for interpretability

        stress_z_components = []
        window = 252  # 1 year rolling window for statistics

        # VIX stress (weight: 30%)
        if 'vix_percentile' in df.columns:
            # Already a percentile, convert to z-score equivalent
            vix_mean = df['vix_percentile'].rolling(window).mean()
            vix_std = df['vix_percentile'].rolling(window).std()
            vix_zscore = (df['vix_percentile'] - vix_mean) / (vix_std + 1e-8)
            stress_z_components.append(('vix', vix_zscore, 0.30))

        # Credit stress (weight: 25%)
        # IMPROVED: Level + Momentum (captures acceleration)
        if 'credit_spread_ratio' in df.columns:
            # Component 1: Level pressure (lower ratio = higher stress)
            # Use negative z-score: declining ratio = positive pressure
            credit_mean = df['credit_spread_ratio'].rolling(window).mean()
            credit_std = df['credit_spread_ratio'].rolling(window).std()
            level_pressure = -(df['credit_spread_ratio'] - credit_mean) / (credit_std + 1e-8)

            # Component 2: Momentum pressure (rapid decline = crisis)
            # Capture acceleration of credit deterioration
            credit_change_5d = df['credit_spread_ratio'].diff(5)
            change_mean = credit_change_5d.rolling(window).mean()
            change_std = credit_change_5d.rolling(window).std()
            momentum_pressure = (credit_change_5d - change_mean) / (change_std + 1e-8)

            # Combined credit pressure = level + momentum
            # Both declining level AND accelerating decline = maximum warning
            credit_zscore = level_pressure + momentum_pressure
            stress_z_components.append(('credit', credit_zscore, 0.25))

        # Correlation stress (weight: 20%)
        # IMPROVED: Level + Acceleration (captures systemic risk buildup)
        # High correlation = loss of diversification = systemic crisis
        if 'spy_qqq_corr_20d' in df.columns:
            # Component 1: Level pressure (high correlation = systemic risk)
            # Direct z-score of correlation (no normalization needed)
            corr_mean = df['spy_qqq_corr_20d'].rolling(window).mean()
            corr_std = df['spy_qqq_corr_20d'].rolling(window).std()
            level_pressure = (df['spy_qqq_corr_20d'] - corr_mean) / (corr_std + 1e-8)

            # Component 2: Acceleration pressure (correlation rising = crisis approaching)
            # Rapid increase in correlation = "nowhere to hide" regime
            corr_change_5d = df['spy_qqq_corr_20d'].diff(5)
            change_mean = corr_change_5d.rolling(window).mean()
            change_std = corr_change_5d.rolling(window).std()
            acceleration_pressure = (corr_change_5d - change_mean) / (change_std + 1e-8)

            # Combined: high correlation + rising correlation = maximum systemic risk
            # Example: corr=0.95 (+3σ) + Δcorr=+0.2 (+2σ) = +5σ systemic crisis
            corr_zscore = level_pressure + acceleration_pressure
            stress_z_components.append(('corr', corr_zscore, 0.20))

        # Tail risk stress (weight: 15%)
        # IMPROVED: Level + Momentum (captures sudden tail risk spike)
        if 'skew_level' in df.columns:
            # Component 1: Level pressure (higher SKEW = higher tail risk)
            skew_mean = df['skew_level'].rolling(window).mean()
            skew_std = df['skew_level'].rolling(window).std()
            level_pressure = (df['skew_level'] - skew_mean) / (skew_std + 1e-8)

            # Component 2: Momentum pressure (rapid SKEW increase = crisis)
            skew_change_5d = df['skew_level'].diff(5)
            change_mean = skew_change_5d.rolling(window).mean()
            change_std = skew_change_5d.rolling(window).std()
            momentum_pressure = (skew_change_5d - change_mean) / (change_std + 1e-8)

            # Combined: high SKEW + rising fast = maximum tail risk warning
            skew_zscore = level_pressure + momentum_pressure
            stress_z_components.append(('skew', skew_zscore, 0.15))

        # Breadth stress (weight: 10%)
        # IMPROVED: Level + Momentum (captures market narrowing acceleration)
        if 'spy_rsp_ratio' in df.columns:
            # Component 1: Level pressure (higher ratio = narrower market)
            breadth_mean = df['spy_rsp_ratio'].rolling(window).mean()
            breadth_std = df['spy_rsp_ratio'].rolling(window).std()
            level_pressure = (df['spy_rsp_ratio'] - breadth_mean) / (breadth_std + 1e-8)

            # Component 2: Momentum pressure (rapid narrowing = fragility)
            breadth_change_5d = df['spy_rsp_ratio'].diff(5)
            change_mean = breadth_change_5d.rolling(window).mean()
            change_std = breadth_change_5d.rolling(window).std()
            momentum_pressure = (breadth_change_5d - change_mean) / (change_std + 1e-8)

            # Combined: narrow market + rapid narrowing = maximum fragility
            breadth_zscore = level_pressure + momentum_pressure
            stress_z_components.append(('breadth', breadth_zscore, 0.10))

        # Combine z-scores with weights
        if stress_z_components:
            # Weighted sum of z-scores
            stress_zscore_combined = sum(
                zscore * weight for _, zscore, weight in stress_z_components
            )

            # Convert combined z-score to percentile (0-100)
            # Use rolling rank to get percentile
            df['stress_composite'] = stress_zscore_combined.rolling(window).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) == window else np.nan
            )

            # Stress acceleration (rate of change in percentile)
            df['stress_acceleration_5d'] = df['stress_composite'].diff(5)
            df['stress_acceleration_20d'] = df['stress_composite'].diff(20)

            # Statistically meaningful thresholds (based on percentile)
            df['stress_elevated'] = (df['stress_composite'] > 75).astype(int)   # Top 25% = elevated
            df['stress_critical'] = (df['stress_composite'] > 90).astype(int)   # Top 10% = critical

            # Add raw z-score for advanced analysis (optional)
            df['stress_zscore_raw'] = stress_zscore_combined

        return df

    def get_feature_names(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of feature column names

        Args:
            df: DataFrame with features

        Returns:
            List of feature names (excluding original price columns and labels)
        """
        exclude_cols = ['SPY', 'QQQ', 'VIX', 'GLD', 'HYG', 'LQD', 'RSP', 'SKEW',
                       'SPY_Volume', 'QQQ_Volume', 'GLD_Volume', 'HYG_Volume', 'LQD_Volume', 'RSP_Volume',
                       'crash_label', 'spy_max_drawdown', 'qqq_max_drawdown', 'min_drawdown',
                       'days_to_crash', 'spy_return', 'qqq_return']

        feature_cols = [col for col in df.columns if col not in exclude_cols]

        self.feature_names = feature_cols
        return feature_cols


if __name__ == "__main__":
    # Test feature engineering
    import sys
    sys.path.append('..')

    from data.data_fetcher import MarketDataFetcher
    from data.label_generator import CrashLabelGenerator

    # Fetch data
    fetcher = MarketDataFetcher(start_date="2007-01-01", end_date="2023-12-31")
    data = fetcher.fetch_data()

    # Generate labels
    label_gen = CrashLabelGenerator()
    data = label_gen.generate_labels(data)

    # Create features
    feature_engine = CrashFeatureEngine()
    data_with_features = feature_engine.create_features(data)

    # Get feature names
    feature_names = feature_engine.get_feature_names(data_with_features)

    print(f"\nTotal features created: {len(feature_names)}")
    print("\nFeature categories:")
    print("  Volatility features:", [f for f in feature_names if 'vix' in f.lower()])
    print("  Trend features:", [f for f in feature_names if 'ma' in f.lower() or 'vs_ma200' in f])
    print("  Tail risk features:", [f for f in feature_names if 'neg_freq' in f or 'max_dd' in f or 'skew' in f])
    print("  Momentum features:", [f for f in feature_names if 'rsi' in f or 'roc' in f or 'macd' in f])
    print("  Correlation features:", [f for f in feature_names if 'corr' in f])
    print("  Risk appetite features:", [f for f in feature_names if 'qqq_spy_ratio' in f or 'tech' in f])

    print("\nData preview with features:")
    print(data_with_features[['SPY', 'QQQ', 'VIX', 'crash_label', 'vix_level',
                               'SPY_vs_ma200', 'SPY_rsi', 'spy_qqq_corr_20d',
                               'qqq_spy_ratio']].head(30))

    print("\nFeature statistics:")
    print(data_with_features[feature_names].describe())
