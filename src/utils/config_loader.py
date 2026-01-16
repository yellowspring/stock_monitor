"""
Configuration loader for stock monitoring
Loads stocks from YAML config file
"""
import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StockConfig:
    """Configuration for a single stock"""
    symbol: str
    name: str
    enabled: bool = True
    type: str = "stock"


@dataclass
class ThresholdConfig:
    """Risk threshold configuration"""
    high_risk: float = 60.0
    moderate_risk: float = 40.0
    low_risk: float = 25.0


class ConfigLoader:
    """Load and manage stock monitoring configuration"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader

        Args:
            config_path: Path to config file (default: config/stocks.yaml)
        """
        if config_path is None:
            # Find config relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "stocks.yaml"

        self.config_path = Path(config_path)
        self.config: Dict = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            print(f"Warning: Config file not found at {self.config_path}")
            self._create_default_config()

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def _create_default_config(self):
        """Create default configuration file"""
        default_config = {
            'market_indices': [
                {'symbol': 'SPY', 'name': 'S&P 500 ETF', 'type': 'index'},
                {'symbol': 'QQQ', 'name': 'Nasdaq 100 ETF', 'type': 'index'},
            ],
            'risk_indicators': [
                {'symbol': '^VIX', 'name': 'VIX Volatility Index'},
                {'symbol': '^SKEW', 'name': 'SKEW Index'},
                {'symbol': 'GLD', 'name': 'Gold ETF'},
                {'symbol': 'HYG', 'name': 'High Yield Bond ETF'},
                {'symbol': 'LQD', 'name': 'Investment Grade Bond ETF'},
                {'symbol': 'RSP', 'name': 'Equal Weight S&P 500'},
            ],
            'monitored_stocks': [
                {'symbol': 'TSLA', 'name': 'Tesla', 'enabled': True},
                {'symbol': 'NVDA', 'name': 'NVIDIA', 'enabled': True},
            ],
            'thresholds': {
                'high_risk': 60,
                'moderate_risk': 40,
                'low_risk': 25,
            },
            'report': {
                'show_all_stocks': True,
                'highlight_high_risk': True,
                'include_market_context': True,
            }
        }

        # Create config directory if needed
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

        self.config = default_config
        print(f"Created default config at {self.config_path}")

    def get_market_indices(self) -> List[StockConfig]:
        """Get market index configurations"""
        indices = self.config.get('market_indices', [])
        return [
            StockConfig(
                symbol=idx['symbol'],
                name=idx['name'],
                type=idx.get('type', 'index')
            )
            for idx in indices
        ]

    def get_risk_indicators(self) -> List[Dict]:
        """Get risk indicator configurations"""
        return self.config.get('risk_indicators', [])

    def get_monitored_stocks(self, enabled_only: bool = True) -> List[StockConfig]:
        """
        Get monitored stock configurations

        Args:
            enabled_only: Only return enabled stocks

        Returns:
            List of StockConfig objects
        """
        stocks = self.config.get('monitored_stocks', [])
        result = []

        for stock in stocks:
            enabled = stock.get('enabled', True)
            if enabled_only and not enabled:
                continue

            result.append(StockConfig(
                symbol=stock['symbol'],
                name=stock['name'],
                enabled=enabled,
                type=stock.get('type', 'stock')
            ))

        return result

    def get_all_symbols(self) -> List[str]:
        """Get all symbols to fetch (indices + indicators + stocks)"""
        symbols = []

        # Market indices
        for idx in self.get_market_indices():
            symbols.append(idx.symbol)

        # Risk indicators
        for ind in self.get_risk_indicators():
            symbols.append(ind['symbol'])

        # Monitored stocks
        for stock in self.get_monitored_stocks():
            if stock.symbol not in symbols:
                symbols.append(stock.symbol)

        return symbols

    def get_thresholds(self) -> ThresholdConfig:
        """Get risk threshold configuration"""
        thresholds = self.config.get('thresholds', {})
        return ThresholdConfig(
            high_risk=thresholds.get('high_risk', 60),
            moderate_risk=thresholds.get('moderate_risk', 40),
            low_risk=thresholds.get('low_risk', 25)
        )

    def get_report_settings(self) -> Dict:
        """Get report configuration"""
        return self.config.get('report', {
            'show_all_stocks': True,
            'highlight_high_risk': True,
            'include_market_context': True
        })

    def get_stock_name(self, symbol: str) -> str:
        """Get display name for a symbol"""
        # Check monitored stocks
        for stock in self.config.get('monitored_stocks', []):
            if stock['symbol'] == symbol:
                return stock['name']

        # Check market indices
        for idx in self.config.get('market_indices', []):
            if idx['symbol'] == symbol:
                return idx['name']

        # Check risk indicators
        for ind in self.config.get('risk_indicators', []):
            if ind['symbol'] == symbol:
                return ind['name']

        return symbol

    def add_stock(self, symbol: str, name: str, enabled: bool = True):
        """
        Add a new stock to monitor

        Args:
            symbol: Stock ticker symbol
            name: Display name
            enabled: Whether to enable monitoring
        """
        if 'monitored_stocks' not in self.config:
            self.config['monitored_stocks'] = []

        # Check if already exists
        for stock in self.config['monitored_stocks']:
            if stock['symbol'] == symbol:
                stock['name'] = name
                stock['enabled'] = enabled
                self._save_config()
                return

        # Add new stock
        self.config['monitored_stocks'].append({
            'symbol': symbol,
            'name': name,
            'enabled': enabled
        })
        self._save_config()
        print(f"Added {name} ({symbol}) to monitoring list")

    def remove_stock(self, symbol: str):
        """Remove a stock from monitoring"""
        if 'monitored_stocks' not in self.config:
            return

        self.config['monitored_stocks'] = [
            s for s in self.config['monitored_stocks']
            if s['symbol'] != symbol
        ]
        self._save_config()
        print(f"Removed {symbol} from monitoring list")

    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)


if __name__ == "__main__":
    # Test config loader
    loader = ConfigLoader()

    print("Market Indices:")
    for idx in loader.get_market_indices():
        print(f"  {idx.symbol}: {idx.name}")

    print("\nMonitored Stocks:")
    for stock in loader.get_monitored_stocks():
        print(f"  {stock.symbol}: {stock.name}")

    print("\nThresholds:")
    thresholds = loader.get_thresholds()
    print(f"  High Risk: >= {thresholds.high_risk}%")
    print(f"  Moderate Risk: >= {thresholds.moderate_risk}%")
    print(f"  Low Risk: <= {thresholds.low_risk}%")

    print("\nAll Symbols to Fetch:")
    print(f"  {loader.get_all_symbols()}")
