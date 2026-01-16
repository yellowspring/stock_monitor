"""
Configuration settings for Crash Probability Index system
"""

# Data settings
DATA_START_DATE = "2005-01-01"  # Start date for historical data
SYMBOLS = ['SPY', 'QQQ', '^VIX']  # Market symbols to fetch

# Crash definition
CRASH_THRESHOLD = -0.15  # -15% drawdown threshold
LOOKFORWARD_DAYS = 20    # Number of trading days to look forward

# Model settings
DEFAULT_MODEL_TYPE = 'xgboost'  # Default ML model
TEST_SIZE = 0.2  # Train/test split ratio
RANDOM_STATE = 42

# Model hyperparameters
XGBOOST_PARAMS = {
    'n_estimators': 200,
    'max_depth': 5,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'scale_pos_weight': 5,
    'random_state': RANDOM_STATE,
    'eval_metric': 'logloss'
}

LIGHTGBM_PARAMS = {
    'n_estimators': 200,
    'max_depth': 5,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'class_weight': 'balanced',
    'random_state': RANDOM_STATE
}

RANDOM_FOREST_PARAMS = {
    'n_estimators': 200,
    'max_depth': 10,
    'min_samples_split': 20,
    'min_samples_leaf': 10,
    'class_weight': 'balanced',
    'random_state': RANDOM_STATE
}

# Warning thresholds
THRESHOLD_LOW = 20      # Below this = LOW risk
THRESHOLD_MODERATE = 40 # Below this = MODERATE risk
THRESHOLD_HIGH = 60     # Below this = HIGH risk
# Above THRESHOLD_HIGH = EXTREME risk

# Backtest settings
DEFAULT_WARNING_THRESHOLD = 30.0  # Default threshold for warnings

# Known crash events for validation
KNOWN_CRASHES = {
    '2008_financial_crisis': {
        'period': ('2008-09-01', '2008-11-30'),
        'description': '2008 Financial Crisis'
    },
    '2020_covid': {
        'period': ('2020-02-15', '2020-04-30'),
        'description': '2020 COVID-19 Crash'
    },
    '2022_bear_market': {
        'period': ('2022-01-01', '2022-10-31'),
        'description': '2022 Bear Market'
    },
    '2011_debt_crisis': {
        'period': ('2011-07-01', '2011-10-31'),
        'description': '2011 US Debt Crisis'
    },
    '2015_china_crash': {
        'period': ('2015-08-01', '2015-09-30'),
        'description': '2015 China Market Crash'
    },
    '2018_q4_selloff': {
        'period': ('2018-10-01', '2018-12-31'),
        'description': '2018 Q4 Selloff'
    }
}

# Paths
MODEL_DIR = "models"
REPORT_DIR = "reports"
VIZ_DIR = "visualizations"
DATA_DIR = "data"

# Visualization settings
FIGURE_DPI = 300
DEFAULT_FIGSIZE = (16, 8)
