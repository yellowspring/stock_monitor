#!/usr/bin/env python3
"""
Show crash probability predictions before and after COVID-19 crash
"""
import sys
sys.path.append('src')

from data.data_fetcher import MarketDataFetcher
from data.label_generator import CrashLabelGenerator
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor
import pandas as pd

print("=" * 80)
print("COVID-19 CRASH PREDICTIONS - BEFORE AND AFTER")
print("=" * 80)

# Load model
print("\nLoading model...")
predictor = CrashPredictor()
predictor.load_model('models/crash_predictor.pkl')

# Fetch data
print("Fetching market data...")
fetcher = MarketDataFetcher(start_date="2019-01-01", end_date="2020-12-31")
data = fetcher.fetch_data()

# Generate labels and features
print("Generating features...")
label_gen = CrashLabelGenerator()
data = label_gen.generate_labels(data)

feature_engine = CrashFeatureEngine()
data = feature_engine.create_features(data)

# Get predictions
feature_names = predictor.feature_names
cols_to_check = feature_names + ['crash_label']
data_clean = data.dropna(subset=cols_to_check)

X_all = data_clean[feature_names].values
data_clean['crash_probability'] = predictor.get_crash_probability_index(X_all)

# Define COVID crash period
covid_crash_start = '2020-02-15'
covid_crash_end = '2020-04-15'

# Before COVID (Jan 2020)
before_covid = data_clean.loc['2020-01-01':'2020-02-14']

# During COVID crash
during_covid = data_clean.loc[covid_crash_start:covid_crash_end]

# After COVID (May-Dec 2020)
after_covid = data_clean.loc['2020-05-01':'2020-12-31']

# Pre-COVID (2019 for comparison)
pre_2020 = data_clean.loc['2019-01-01':'2019-12-31']

print("\n" + "=" * 80)
print("BEFORE COVID-19 (January 2020)")
print("=" * 80)
print(f"\nPeriod: 2020-01-01 to 2020-02-14")
print(f"Number of days: {len(before_covid)}")
print(f"\nAverage crash probability: {before_covid['crash_probability'].mean():.1f}%")
print(f"Max crash probability: {before_covid['crash_probability'].max():.1f}%")
print(f"Min crash probability: {before_covid['crash_probability'].min():.1f}%")

print("\nLast 10 trading days before crash:")
print("-" * 80)
for idx, row in before_covid.tail(10).iterrows():
    date = idx.strftime('%Y-%m-%d')
    prob = row['crash_probability']
    spy = row['SPY']
    qqq = row['QQQ']
    vix = row['VIX']
    icon = "⚠️ " if prob > 30 else "   "
    print(f"{icon}{date}: Prob={prob:5.1f}%  SPY=${spy:6.2f}  QQQ=${qqq:6.2f}  VIX={vix:5.2f}")

print("\n" + "=" * 80)
print("DURING COVID-19 CRASH (Feb 15 - Apr 15, 2020)")
print("=" * 80)
print(f"\nPeriod: {covid_crash_start} to {covid_crash_end}")
print(f"Number of days: {len(during_covid)}")
print(f"\nAverage crash probability: {during_covid['crash_probability'].mean():.1f}%")
print(f"Max crash probability: {during_covid['crash_probability'].max():.1f}%")
print(f"Min crash probability: {during_covid['crash_probability'].min():.1f}%")

print("\nAll trading days during crash:")
print("-" * 80)
for idx, row in during_covid.iterrows():
    date = idx.strftime('%Y-%m-%d')
    prob = row['crash_probability']
    spy = row['SPY']
    qqq = row['QQQ']
    vix = row['VIX']
    actual = row['crash_label']
    icon = "🚨" if prob > 60 else ("⚠️ " if prob > 30 else "   ")
    label_icon = " [CRASH]" if actual == 1 else ""
    print(f"{icon}{date}: Prob={prob:5.1f}%  SPY=${spy:6.2f}  QQQ=${qqq:6.2f}  VIX={vix:5.2f}{label_icon}")

print("\n" + "=" * 80)
print("AFTER COVID-19 (May - Dec 2020)")
print("=" * 80)
print(f"\nPeriod: 2020-05-01 to 2020-12-31")
print(f"Number of days: {len(after_covid)}")
print(f"\nAverage crash probability: {after_covid['crash_probability'].mean():.1f}%")
print(f"Max crash probability: {after_covid['crash_probability'].max():.1f}%")
print(f"Min crash probability: {after_covid['crash_probability'].min():.1f}%")

print("\nFirst 10 trading days after crash:")
print("-" * 80)
for idx, row in after_covid.head(10).iterrows():
    date = idx.strftime('%Y-%m-%d')
    prob = row['crash_probability']
    spy = row['SPY']
    qqq = row['QQQ']
    vix = row['VIX']
    icon = "⚠️ " if prob > 30 else "   "
    print(f"{icon}{date}: Prob={prob:5.1f}%  SPY=${spy:6.2f}  QQQ=${qqq:6.2f}  VIX={vix:5.2f}")

print("\n" + "=" * 80)
print("COMPARISON: 2019 (PRE-COVID YEAR)")
print("=" * 80)
print(f"\nPeriod: 2019-01-01 to 2019-12-31")
print(f"Number of days: {len(pre_2020)}")
print(f"\nAverage crash probability: {pre_2020['crash_probability'].mean():.1f}%")
print(f"Max crash probability: {pre_2020['crash_probability'].max():.1f}%")
print(f"Min crash probability: {pre_2020['crash_probability'].min():.1f}%")

print("\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)

summary = pd.DataFrame({
    'Period': ['2019 (Normal)', 'Jan 2020 (Before)', 'Feb-Apr 2020 (During)', 'May-Dec 2020 (After)'],
    'Avg Probability': [
        pre_2020['crash_probability'].mean(),
        before_covid['crash_probability'].mean(),
        during_covid['crash_probability'].mean(),
        after_covid['crash_probability'].mean()
    ],
    'Max Probability': [
        pre_2020['crash_probability'].max(),
        before_covid['crash_probability'].max(),
        during_covid['crash_probability'].max(),
        after_covid['crash_probability'].max()
    ],
    'Days > 30%': [
        (pre_2020['crash_probability'] > 30).sum(),
        (before_covid['crash_probability'] > 30).sum(),
        (during_covid['crash_probability'] > 30).sum(),
        (after_covid['crash_probability'] > 30).sum()
    ],
    'Days > 60%': [
        (pre_2020['crash_probability'] > 60).sum(),
        (before_covid['crash_probability'] > 60).sum(),
        (during_covid['crash_probability'] > 60).sum(),
        (after_covid['crash_probability'] > 60).sum()
    ]
})

print("\n")
print(summary.to_string(index=False))

print("\n" + "=" * 80)
print("KEY INSIGHTS")
print("=" * 80)

avg_normal = pre_2020['crash_probability'].mean()
avg_during = during_covid['crash_probability'].mean()
increase = ((avg_during - avg_normal) / avg_normal * 100)

print(f"\n1. Probability Increase During Crisis:")
print(f"   - Normal 2019: {avg_normal:.1f}%")
print(f"   - COVID Crash: {avg_during:.1f}%")
print(f"   - Increase: {increase:.0f}x higher")

first_warning = before_covid[before_covid['crash_probability'] > 30]
if len(first_warning) > 0:
    warning_date = first_warning.index[0].strftime('%Y-%m-%d')
    warning_prob = first_warning.iloc[0]['crash_probability']
    print(f"\n2. First Warning Signal:")
    print(f"   - Date: {warning_date}")
    print(f"   - Probability: {warning_prob:.1f}%")

    crash_actual_start = pd.to_datetime('2020-02-19').tz_localize('America/New_York')  # Market peak
    days_before = (crash_actual_start - first_warning.index[0]).days
    print(f"   - Days before market peaked: {days_before}")

peak_prob_day = during_covid['crash_probability'].idxmax()
peak_prob = during_covid['crash_probability'].max()
print(f"\n3. Peak Crash Probability:")
print(f"   - Date: {peak_prob_day.strftime('%Y-%m-%d')}")
print(f"   - Probability: {peak_prob:.1f}%")
print(f"   - SPY: ${during_covid.loc[peak_prob_day, 'SPY']:.2f}")
print(f"   - VIX: {during_covid.loc[peak_prob_day, 'VIX']:.2f}")

recovery_normal = after_covid[after_covid['crash_probability'] < 20]
if len(recovery_normal) > 0:
    recovery_date = recovery_normal.index[0].strftime('%Y-%m-%d')
    print(f"\n4. Recovery to Normal Levels (<20%):")
    print(f"   - Date: {recovery_date}")
    print(f"   - Days after peak: {(recovery_normal.index[0] - peak_prob_day).days}")

print("\n" + "=" * 80)
