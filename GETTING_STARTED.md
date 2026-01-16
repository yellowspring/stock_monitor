# Getting Started with Crash Probability Index

This guide will get you up and running in 5 minutes.

## Prerequisites

- **Python 3.8+** installed
- **Internet connection** (for downloading market data)
- **~500MB disk space** (for dependencies and data)

---

## Installation

### Option 1: Automated Setup (Recommended)

```bash
# Clone or download the project
cd proj_stock_monitor

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate virtual environment
source venv/bin/activate
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p models reports visualizations data
```

---

## Quick Start (5 minutes)

### 1. Run the Example Script

This demonstrates the complete workflow:

```bash
python example.py
```

**What it does:**
- Fetches 13+ years of market data (SPY, QQQ, VIX)
- Generates crash labels for training
- Creates 80+ features
- Trains XGBoost model
- Shows recent crash probabilities
- Validates on known crash events

**Expected output:**
```
[1/5] Fetching market data...
      Loaded 3500 trading days

[2/5] Generating crash labels...
      Found 285 crash days (8.14%)

[3/5] Engineering features...
      Created 82 features

[4/5] Training XGBoost model...
      Training accuracy: 0.8756
      Test accuracy: 0.8234

[5/5] Generating crash probabilities...

LATEST CRASH PROBABILITY INDEX: 23.5/100
Risk Level: MODERATE
```

### 2. Train Your Own Model

```bash
python main.py --mode train
```

This trains a model on all available historical data and saves it to `models/crash_predictor.pkl`.

**Typical output:**
```
========================================
TRAINING CRASH PREDICTION MODEL
========================================

Training set: 2800 samples, 228 crashes (8.14%)
Test set: 700 samples, 57 crashes (8.14%)

Training XGBoost model...
Training accuracy: 0.8756
Training AUC: 0.9123

Evaluating model...
Test accuracy: 0.8234
Test AUC: 0.7891

Top 15 Most Important Features:
1. vix_level                  0.1842
2. vix_change_5d              0.1213
3. SPY_vs_ma200               0.0987
...

Model saved to models/crash_predictor.pkl
```

### 3. Get Current Crash Probability

```bash
python main.py --mode predict
```

**Output:**
```
========================================
CURRENT CRASH PROBABILITY INDEX
========================================

Date: 2024-01-15
SPY: $478.23
QQQ: $412.45
VIX: 13.21

========================================
CRASH PROBABILITY INDEX: 18.5/100
========================================

Risk Level: LOW
Interpretation: Market conditions appear stable

Recent 10-day probability history:
  2024-01-05: 15.2
  2024-01-08: 16.8
  2024-01-09: 17.3
  2024-01-10: 18.1
  2024-01-11: 18.5
  ...
```

### 4. Run Backtest on Historical Data

```bash
python main.py --mode backtest --threshold 30
```

This validates the model on known crash events.

**Sample output:**
```
========================================
CRASH PREDICTION BACKTEST REPORT
========================================

OVERALL PERFORMANCE
Threshold: 30
Precision: 0.5234
Recall: 0.7123
F1 Score: 0.6021
Accuracy: 0.8567

========================================
KNOWN CRASH EVENTS DETECTION
========================================

2008 Financial Crisis
  Period: 2008-09-01 to 2008-11-30
  Average Probability: 65.3
  Max Probability: 87.2
  Days Above Threshold: 48/60 (80.0%)
  Warning Lead Time: 7 days before

2020 COVID-19 Crash
  Period: 2020-02-15 to 2020-04-30
  Average Probability: 72.1
  Max Probability: 91.5
  Days Above Threshold: 52/55 (94.5%)
  Warning Lead Time: 5 days before
...
```

### 5. Create Visualizations

```bash
python main.py --mode visualize
```

This generates three plots in the `visualizations/` directory:

1. **crash_probability_timeline.png** - Full history with crash probabilities
2. **feature_importance.png** - Top 20 most important features
3. **crash_events.png** - Detailed view of major crash periods

### 6. Run Complete Pipeline

```bash
python main.py --mode all
```

This runs everything: train → predict → backtest → visualize

---

## Understanding the Output

### Crash Probability Index

The output is a number from **0 to 100**:

| Range | Risk Level | Meaning |
|-------|------------|---------|
| 0-20 | **LOW** | Normal market conditions, standard risk |
| 20-40 | **MODERATE** | Elevated risk, monitor closely |
| 40-60 | **HIGH** | Significant risk, consider reducing exposure |
| 60-100 | **EXTREME** | Severe risk, defensive positioning recommended |

### Interpretation Examples

**Probability: 15** (LOW)
```
Market appears stable. VIX is low, trends are intact,
no significant risk signals. Normal risk tolerance.
```

**Probability: 35** (MODERATE)
```
Some warning signs present. VIX elevated or trend weakening.
Monitor positions, review stop losses, reduce leverage.
```

**Probability: 55** (HIGH)
```
Multiple risk signals firing. Combination of high VIX,
broken trends, negative momentum. Consider hedging,
reduce equity exposure.
```

**Probability: 75** (EXTREME)
```
Severe systemic risk detected. Similar to conditions before
2008/2020 crashes. Capital preservation mode - reduce risk
significantly.
```

---

## Command Reference

### Main Script Options

```bash
python main.py --mode <MODE> [OPTIONS]

Modes:
  train       Train new model from scratch
  predict     Get current crash probability
  backtest    Validate on historical crash events
  visualize   Create all visualizations
  all         Run complete pipeline

Options:
  --start-date DATE       Start date for data (default: 2005-01-01)
  --model-type TYPE       xgboost, lightgbm, random_forest, etc.
  --threshold PROB        Warning threshold 0-100 (default: 30)

Examples:
  python main.py --mode train --start-date 2010-01-01
  python main.py --mode predict
  python main.py --mode backtest --threshold 25
  python main.py --mode all --model-type lightgbm
```

---

## Common Use Cases

### Daily Monitoring

Run this every day to track crash probability:

```bash
#!/bin/bash
# daily_check.sh
source venv/bin/activate
python main.py --mode predict > logs/$(date +%Y%m%d).txt
```

### Weekly Retraining

Update the model with latest data weekly:

```bash
#!/bin/bash
# weekly_retrain.sh
source venv/bin/activate
python main.py --mode train
python main.py --mode backtest
```

### Alert on High Risk

Get notified when probability exceeds threshold:

```python
# alert_system.py
from src.models.crash_predictor import CrashPredictor
import smtplib

predictor = CrashPredictor()
predictor.load_model('models/crash_predictor.pkl')

crash_prob = get_latest_probability()  # Your implementation

if crash_prob > 50:
    send_email(f"ALERT: Crash probability at {crash_prob}!")
```

---

## Troubleshooting

### Issue: "No module named 'yfinance'"

**Solution:** Install dependencies
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Data fetch failed"

**Cause:** Network issues or Yahoo Finance API rate limit

**Solution:**
```bash
# Retry after 1 minute, or use cached data
python main.py --mode train --use-cache
```

### Issue: "Model file not found"

**Solution:** Train model first
```bash
python main.py --mode train
```

### Issue: "Insufficient data for features"

**Cause:** Not enough historical data (need 252+ days for MA200)

**Solution:** Use earlier start date
```bash
python main.py --mode train --start-date 2010-01-01
```

### Issue: Low model performance

**Solutions:**
1. **More data:** Use longer history
2. **Different model:** Try `--model-type lightgbm`
3. **Retrain:** Market regime may have changed
4. **Check features:** Some may have missing values

---

## Next Steps

### Learn More

1. **README.md** - User documentation and overview
2. **TECHNICAL_DOCS.md** - Deep dive into methodology
3. **PROJECT_SUMMARY.md** - Architecture and design decisions

### Customize

1. **Modify features** - Edit `src/features/feature_engineering.py`
2. **Change crash definition** - Edit `config.py` (CRASH_THRESHOLD, LOOKFORWARD_DAYS)
3. **Add new models** - Extend `src/models/crash_predictor.py`
4. **Custom visualization** - Use `src/utils/visualizer.py`

### Integrate

Use the system programmatically:

```python
# your_script.py
import sys
sys.path.append('src')

from data.data_fetcher import MarketDataFetcher
from features.feature_engineering import CrashFeatureEngine
from models.crash_predictor import CrashPredictor

# Fetch latest data
fetcher = MarketDataFetcher()
data = fetcher.fetch_data()

# Create features
engine = CrashFeatureEngine()
data = engine.create_features(data)

# Load model and predict
predictor = CrashPredictor()
predictor.load_model('models/crash_predictor.pkl')

latest_features = data[predictor.feature_names].dropna().tail(1).values
crash_prob = predictor.get_crash_probability_index(latest_features)[0]

print(f"Current crash probability: {crash_prob:.1f}")
```

---

## Best Practices

### 1. Regular Updates
- **Retrain monthly** with new data
- **Check daily** for significant changes
- **Validate quarterly** on recent performance

### 2. Risk Management
- **Never rely solely** on this indicator
- **Combine with fundamentals** and other signals
- **Use proper position sizing** always
- **Have stop losses** in place

### 3. Interpretation
- **Trend matters** - Rising probability more concerning than high static
- **Context matters** - 40 during calm vs crisis means different things
- **Multiple signals** - Look at feature breakdown, not just final number

### 4. Production Use
- **Monitor data quality** - Check for missing values
- **Log predictions** - Track historical accuracy
- **Set up alerts** - Don't miss critical signals
- **Have fallbacks** - What if model/data unavailable?

---

## Support

### Documentation
- 📖 [README.md](README.md) - Overview and usage
- 🔧 [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md) - Technical details
- 📊 [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Architecture

### Code
- 💻 [example.py](example.py) - Working example
- 🎯 [main.py](main.py) - Main entry point
- ⚙️ [config.py](config.py) - Configuration

### Issues
- Check existing documentation first
- Review error messages carefully
- Include steps to reproduce

---

## Quick Reference Card

```
┌──────────────────────────────────────────────────────┐
│              CRASH PROBABILITY INDEX                 │
│               Quick Reference Card                   │
├──────────────────────────────────────────────────────┤
│ Setup:                                               │
│   ./setup.sh                                         │
│   source venv/bin/activate                           │
│                                                      │
│ Train:                                               │
│   python main.py --mode train                        │
│                                                      │
│ Predict:                                             │
│   python main.py --mode predict                      │
│                                                      │
│ Backtest:                                            │
│   python main.py --mode backtest                     │
│                                                      │
│ Risk Levels:                                         │
│   0-20   LOW       - Normal conditions               │
│   20-40  MODERATE  - Monitor closely                 │
│   40-60  HIGH      - Reduce exposure                 │
│   60-100 EXTREME   - Defensive mode                  │
│                                                      │
│ Files:                                               │
│   models/crash_predictor.pkl  - Trained model        │
│   reports/*.txt               - Backtest reports     │
│   visualizations/*.png        - Charts               │
└──────────────────────────────────────────────────────┘
```

---

**You're all set! Run `python example.py` to get started.**
