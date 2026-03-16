#!/usr/bin/env python3
"""
Standalone Stock Scanner Script

Run this nightly (e.g., 1 AM) to scan stocks and cache results.
Results are saved to cache/stock_scan_results.json and can be
loaded by the daily report without re-scanning.

Usage:
    python run_stock_scan.py [--top N] [--min-score N] [--workers N]

Example cron (1 AM daily):
    0 1 * * * cd /path/to/proj_stock_monitor && python run_stock_scan.py >> logs/scan.log 2>&1
"""

import sys
import os
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.stock_scanner import StockScanner


def main():
    parser = argparse.ArgumentParser(description='Run stock scanner')
    parser.add_argument('--top', type=int, default=20, help='Top N stocks to return')
    parser.add_argument('--min-score', type=int, default=50, help='Minimum score threshold')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers')
    parser.add_argument('--universe', type=str, default='default',
                        choices=['default', 'sp500', 'sp500-full', 'nasdaq100', 'midcap',
                                 'etfs', 'dividend', 'all', 'small'],
                        help='''Stock universe to scan:
                            small(12), default(60), sp500(80), sp500-full(~485),
                            nasdaq100(~100), midcap(~200), etfs(~60), dividend(~65),
                            all(combined ~800)''')

    args = parser.parse_args()

    print("=" * 60)
    print(f"STOCK SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Select universe
    if args.universe == 'small':
        # Small test universe (12 stocks)
        universe = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
                    'AMD', 'INTC', 'PYPL', 'SQ', 'COIN']
    elif args.universe == 'sp500':
        # S&P 500 sample (80 stocks)
        from utils.stock_scanner import SP500_SAMPLE
        universe = SP500_SAMPLE
    elif args.universe == 'sp500-full':
        # Full S&P 500 (~485 stocks)
        from utils.stock_scanner import SP500_FULL
        universe = SP500_FULL
    elif args.universe == 'nasdaq100':
        # NASDAQ 100 (~100 stocks, tech-heavy)
        from utils.stock_scanner import NASDAQ_100
        universe = NASDAQ_100
    elif args.universe == 'midcap':
        # S&P 400 Mid-cap (~200 stocks)
        from utils.stock_scanner import MIDCAP_400
        universe = MIDCAP_400
    elif args.universe == 'etfs':
        # Sector ETFs (~60 ETFs)
        from utils.stock_scanner import SECTOR_ETFS
        universe = SECTOR_ETFS
    elif args.universe == 'dividend':
        # Dividend Aristocrats (~65 stocks)
        from utils.stock_scanner import DIVIDEND_ARISTOCRATS
        universe = DIVIDEND_ARISTOCRATS
    elif args.universe == 'all':
        # Combined universe (SP500 + NASDAQ100 + MIDCAP + DIVIDEND, ~680 stocks)
        # NOTE: ETFs are scanned separately with ETFEvaluator
        from utils.stock_scanner import (SP500_FULL, NASDAQ_100, MIDCAP_400,
                                         DIVIDEND_ARISTOCRATS, get_combined_universe)
        universe = get_combined_universe(SP500_FULL, NASDAQ_100, MIDCAP_400, DIVIDEND_ARISTOCRATS)
    else:
        # Default universe (60 stocks)
        universe = None

    scanner = StockScanner(universe=universe, cache_hours=20)

    print(f"Universe: {args.universe} ({len(scanner.universe)} stocks)")
    print(f"Parameters: top={args.top}, min_score={args.min_score}, workers={args.workers}")
    print()

    # Run scan
    results = scanner.scan_all(
        top_n=args.top,
        min_score=args.min_score,
        max_workers=args.workers
    )

    # Save results
    scanner.save_results(results)

    # Print report
    print()
    print(scanner.format_scan_report(results))

    # ==================== ETF SCAN (SEPARATE) ====================
    print()
    print("=" * 60)
    print("ETF EVALUATOR - Technical Analysis")
    print("=" * 60)

    try:
        from utils.etf_evaluator import ETFEvaluator, ETF_DATABASE

        evaluator = ETFEvaluator()
        etf_symbols = list(ETF_DATABASE.keys())

        print(f"Scanning {len(etf_symbols)} ETFs...")
        etf_scores = evaluator.evaluate_multiple(etf_symbols)

        # Save ETF results
        import json
        from pathlib import Path
        etf_results_file = Path(__file__).parent / "cache" / "etf_scan_results.json"

        etf_data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(etf_scores),
            'results': [
                {
                    'symbol': s.symbol,
                    'name': s.name,
                    'category': s.category,
                    'role_tag': s.role_tag,
                    'total_score': s.total_score,
                    'recommendation': s.recommendation,
                    'price': s.price,
                    'ytd_return': s.ytd_return,
                    'dividend_yield': s.dividend_yield,
                    'expense_ratio': s.expense_ratio,
                    'description': s.description,
                }
                for s in etf_scores
            ]
        }

        with open(etf_results_file, 'w') as f:
            json.dump(etf_data, f, indent=2)
        print(f"ETF results saved to {etf_results_file}")

        # Print ETF report
        print()
        print(evaluator.format_scores_text(etf_scores))

    except Exception as e:
        print(f"Warning: ETF scan failed: {e}")

    print()
    print("=" * 60)
    print(f"SCAN COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
