# Crash Probability Index

A systematic market crash prediction system that predicts the probability (0-100) of a ≥15% drawdown in SPY or QQQ within the next 20 trading days.

## Overview

This system uses machine learning to detect systemic/semi-systemic crash events by analyzing:
- **SPY** (S&P 500 ETF)
- **QQQ** (Nasdaq-100 ETF)
- **VIX** (Volatility Index)

### Crash Definition

A "crash event" is defined as:
```
min(SPY_drawdown, QQQ_drawdown) ≤ -15% within next 20 trading days
```

This identifies significant systemic risk events like:
- 2008 Financial Crisis
- 2020 COVID-19 Crash
- 2022 Bear Market

## Features

The model uses **6 core feature categories** (80+ features total):

### 1. Volatility Features
- VIX level and changes
- VIX jumps (>10% increase)
- VIX percentiles

### 2. Trend Features
- Price vs MA200 distance
- Death cross indicators
- Moving average relationships

### 3. Tail Risk Features
- Negative return frequency
- Large drawdown frequency
- Return skewness

### 4. Momentum Features
- RSI indicators
- Rate of change
- MACD signals

### 5. Correlation Features
- SPY-QQQ rolling correlation
- High correlation indicators

### 6. Risk Appetite Features
- QQQ/SPY ratio (tech vs market)
- Relative strength trends

## Installation

```bash
# Clone repository
git clone <repository-url>
cd proj_stock_monitor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### 1. Train Model

Train a new crash prediction model on historical data:

```bash
python main.py --mode train
```

### 2. Get Current Crash Probability

Get the current crash probability index:

```bash
python main.py --mode predict
```

Output example:
```
Date: 2024-01-15
SPY: $478.23
QQQ: $412.45
VIX: 13.21

========================================
CRASH PROBABILITY INDEX: 18.5/100
========================================

Risk Level: LOW
Interpretation: Market conditions appear stable
```

### 3. Run Backtest

Validate model performance on historical crash events:

```bash
python main.py --mode backtest --threshold 30
```

### 4. Create Visualizations

Generate comprehensive visualizations:

```bash
python main.py --mode visualize
```

Creates:
- Timeline of crash probabilities
- Feature importance chart
- Crash event analysis

### 5. Complete Pipeline

Run everything at once:

```bash
python main.py --mode all
```

## Command Line Options

```bash
python main.py --mode <MODE> [OPTIONS]

Modes:
  train       Train new model
  predict     Get current crash probability
  backtest    Run historical backtest
  visualize   Create visualizations
  all         Run complete pipeline

Options:
  --start-date DATE       Start date for data (default: 2005-01-01)
  --model-type TYPE       Model type: xgboost, lightgbm, random_forest (default: xgboost)
  --threshold PROB        Warning threshold 0-100 (default: 30)
```

## Project Structure

```
proj_stock_monitor/
├── main.py                    # Main entry point
├── requirements.txt           # Dependencies
├── README.md                  # This file
├── src/
│   ├── data/
│   │   ├── data_fetcher.py   # Fetch SPY, QQQ, VIX data
│   │   └── label_generator.py # Generate crash labels
│   ├── features/
│   │   └── feature_engineering.py # 6 feature categories
│   ├── models/
│   │   └── crash_predictor.py # ML prediction model
│   └── utils/
│       ├── backtester.py     # Backtest framework
│       └── visualizer.py     # Visualization tools
├── models/                    # Saved models
├── reports/                   # Backtest reports
└── visualizations/           # Generated plots
```

## Model Details

### Binary Classification

- **Target**: Crash (1) vs Normal (0)
- **Output**: Probability 0-1 (scaled to 0-100)
- **Models**: XGBoost (default), LightGBM, Random Forest, Gradient Boosting, Logistic Regression

### Training Approach

- Time series split (preserves temporal order)
- Class imbalance handling (weighted loss)
- Feature scaling with StandardScaler
- 80/20 train/test split

### Evaluation Metrics

- Precision/Recall/F1
- ROC-AUC
- Crash event detection rate
- Warning lead time

## Risk Interpretation

| Crash Probability | Risk Level | Interpretation |
|-------------------|------------|----------------|
| 0-20              | LOW        | Market conditions appear stable |
| 20-40             | MODERATE   | Elevated risk - monitor closely |
| 40-60             | HIGH       | High crash risk - consider defensive positioning |
| 60-100            | EXTREME    | EXTREME crash risk - urgent action recommended |

## Known Crash Events Detected

The model is validated on these historical events:

- **2008 Financial Crisis** (Sep-Nov 2008)
- **2011 US Debt Crisis** (Jul-Oct 2011)
- **2015 China Market Crash** (Aug-Sep 2015)
- **2018 Q4 Selloff** (Oct-Dec 2018)
- **2020 COVID-19 Crash** (Feb-Apr 2020)
- **2022 Bear Market** (Jan-Oct 2022)

## Example Python Usage

```python
from src.data.data_fetcher import MarketDataFetcher
from src.data.label_generator import CrashLabelGenerator
from src.features.feature_engineering import CrashFeatureEngine
from src.models.crash_predictor import CrashPredictor

# Fetch data
fetcher = MarketDataFetcher(start_date="2010-01-01")
data = fetcher.fetch_data()

# Generate labels
label_gen = CrashLabelGenerator()
data = label_gen.generate_labels(data)

# Create features
feature_engine = CrashFeatureEngine()
data = feature_engine.create_features(data)
feature_names = feature_engine.get_feature_names(data)

# Train model
predictor = CrashPredictor(model_type='xgboost')
X_train, X_test, y_train, y_test, _, _ = predictor.prepare_data(
    data, feature_names, test_size=0.2
)
predictor.train(X_train, y_train)

# Get crash probability
latest_features = data[feature_names].dropna().tail(1).values
crash_prob = predictor.get_crash_probability_index(latest_features)[0]
print(f"Crash Probability: {crash_prob:.1f}/100")
```

## Important Notes

### Mathematical Definition

The crash label for day `t` is:

```
label(t) = 1  if  min(
    min(SPY[t+1:t+20] / SPY[t]) - 1,
    min(QQQ[t+1:t+20] / QQQ[t]) - 1
) ≤ -0.15
else 0
```

### Limitations

- **Not investment advice** - Use at your own risk
- **Past performance** does not guarantee future results
- **False positives** are possible - model shows elevated risk that doesn't materialize
- **Data quality** depends on market data availability
- **Model drift** - Retrain periodically with new data

### Best Practices

1. **Monitor regularly** - Check probability daily/weekly
2. **Use thresholds** - Define your own risk thresholds
3. **Combine signals** - Don't rely solely on this model
4. **Retrain periodically** - Update with recent data
5. **Backtest changes** - Validate before production use

## License

MIT License

## Disclaimer

This software is for educational and research purposes only. It is not financial advice. Trading and investing carry risk of loss. Always do your own research and consult with financial professionals before making investment decisions.
