"""
ETF-4Q Model - ETF Quick Evaluation
Macro × Quality × Valuation × Structure

ETF ≠ Company. ETF = Factor Exposure + Asset Basket
We don't use DCF - we evaluate "what factor are you buying"

Total Score = Macro + Quality + Valuation + Structure (0-16 scale)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ETFScore:
    """ETF-4Q evaluation result"""
    symbol: str
    name: str
    category: str  # benchmark, sector, factor, fixed_income
    price: float
    expense_ratio: float

    # Macro Component (0-4)
    macro_score: int
    macro_notes: List[str]

    # Quality Component (0-4)
    quality_score: int
    quality_notes: List[str]

    # Valuation Component (0-3)
    valuation_score: int
    valuation_notes: List[str]

    # Structure Component (0-4)
    structure_score: int
    structure_notes: List[str]

    # Momentum Component (0-3)
    momentum_score: int
    momentum_notes: List[str]

    # Total
    total_score: int  # 0-18 (M4 + Q4 + V3 + S4 + Mom3)
    recommendation: str  # A+, A, B, C

    # Additional metrics
    ytd_return: Optional[float]
    dividend_yield: Optional[float]
    pe_ratio: Optional[float]
    aum: Optional[float]  # Assets under management

    # Role tag and description (with defaults)
    role_tag: str = ""  # CORE, HEDGE, INCOME, AI, DEFENSE, SATELLITE
    description: str = ""  # Chinese description from ETF_DATABASE

    def __str__(self):
        return f"{self.symbol}: {self.total_score}/15 ({self.recommendation}) [{self.role_tag}]"


# ETF Database with sector/category info and characteristics
ETF_DATABASE = {
    # =========================
    # CORE / BENCHMARK (Equity)
    # =========================
    "VTI": {
        "name": "Total US Stock",
        "category": "benchmark",
        "sector": "broad",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.03,
        "description": "全美股一篮子（大中小盘），一只覆盖美国股市的大底仓。"
    },
    "VOO": {
        "name": "S&P 500",
        "category": "benchmark",
        "sector": "broad",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.03,
        "description": "标普500大盘股核心仓位，流动性好、成本低。"
    },
    "IVV": {
        "name": "S&P 500 (iShares)",
        "category": "benchmark",
        "sector": "broad",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.03,
        "description": "标普500另一只超大规模ETF（iShares），与VOO/SPY同类对标。"
    },
    "SPY": {
        "name": "S&P 500 (SPDR)",
        "category": "benchmark",
        "sector": "broad",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.09,
        "description": "标普500最老牌、流动性最强之一（但费率通常高于VOO/IVV）。"
    },
    "VT": {
        "name": "Total World",
        "category": "benchmark",
        "sector": "global",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.07,
        "description": "全球股票一篮子（发达+新兴），适合“一只买全世界”。"
    },

    # =========================
    # INTERNATIONAL EQUITY
    # =========================
    "VXUS": {
        "name": "Total International ex-US",
        "category": "international",
        "sector": "intl_ex_us",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.07,
        "description": "美国以外的全球股票（发达+新兴），可作为VTI的国际补充。"
    },
    "VEA": {
        "name": "Developed Markets",
        "category": "international",
        "sector": "developed",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.05,
        "description": "发达市场（不含美国），更偏大盘成熟经济体。"
    },
    "VWO": {
        "name": "Emerging Markets",
        "category": "international",
        "sector": "emerging",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.08,
        "description": "新兴市场，波动更大、周期属性更强。"
    },
    "IEFA": {
        "name": "Intl Developed (Core)",
        "category": "international",
        "sector": "developed",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.07,
        "description": "发达市场核心ETF（iShares），与VEA相近但编制略不同。"
    },

    # =========================
    # LARGE STYLE / GROWTH
    # =========================
    "QQQ": {
        "name": "Nasdaq-100",
        "category": "benchmark",
        "sector": "nasdaq_100",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.20,
        "description": "纳指100，偏大盘成长/科技权重高，波动更大。"
    },
    "QQQM": {
        "name": "Nasdaq-100 (Lower Fee)",
        "category": "benchmark",
        "sector": "nasdaq_100",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.15,
        "description": "纳指100的低费率版本，长期持有通常比QQQ更划算。"
    },

    # =========================
    # SECTOR (SPDR Select Sector)
    # =========================
    "XLK": {"name": "Technology", "category": "sector", "sector": "technology", "quality": "high", "cyclical": True,
            "expense_ratio": 0.09, "description": "科技板块（偏成长），对利率/景气敏感。"},
    "XLV": {"name": "Healthcare", "category": "sector", "sector": "healthcare", "quality": "high", "cyclical": False,
            "expense_ratio": 0.09, "description": "医疗保健，偏防御、现金流相对稳。"},
    "XLC": {"name": "Communication", "category": "sector", "sector": "communication", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.09, "description": "通信服务（含互联网平台/媒体），波动中等偏高。"},
    "XLE": {"name": "Energy", "category": "sector", "sector": "energy", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.09, "description": "能源，上游油气权重高，强周期/通胀敏感。"},
    "XLF": {"name": "Financials", "category": "sector", "sector": "financials", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.09, "description": "金融（银行/保险/资本市场），对利差与周期敏感。"},
    "XLI": {"name": "Industrials", "category": "sector", "sector": "industrials", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.09, "description": "工业（制造/航空航天/运输等），典型顺周期。"},
    "XLB": {"name": "Materials", "category": "sector", "sector": "materials", "quality": "low", "cyclical": True,
            "expense_ratio": 0.09, "description": "材料（化工/金属/建材），周期+商品属性明显。"},
    # XLU moved to POWER & UTILITIES section below
    "XLY": {"name": "Consumer Discretionary", "category": "sector", "sector": "consumer_disc", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.09, "description": "可选消费，和就业/消费景气相关。"},
    "XLP": {"name": "Consumer Staples", "category": "sector", "sector": "consumer_staples", "quality": "high", "cyclical": False,
            "expense_ratio": 0.09, "description": "必选消费，防御属性更强。"},
    "XLRE": {"name": "Real Estate (Sector)", "category": "sector", "sector": "real_estate", "quality": "medium", "cyclical": True,
             "expense_ratio": 0.09, "description": "标普房地产板块（含REITs），利率敏感+周期属性。"},
    "XBI": {"name": "Biotech (SPDR)", "category": "thematic", "sector": "biotech", "quality": "low", "cyclical": True,
            "expense_ratio": 0.35, "description": "生物科技更偏中小盘与研发风险，波动通常高于IBB。"},
    "XME": {"name": "Metals & Mining", "category": "thematic", "sector": "metals_mining", "quality": "low", "cyclical": True,
            "expense_ratio": 0.35, "description": "金属矿业，强商品周期。"},

    # =========================
    # FACTOR / STYLE
    # =========================
    "VUG": {"name": "Growth", "category": "factor", "sector": "growth", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.04, "description": "美股成长风格（大盘为主），对利率更敏感。"},
    "VTV": {"name": "Value", "category": "factor", "sector": "value", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.04, "description": "美股价值风格，金融/工业权重通常更高。"},
    "QUAL": {"name": "Quality", "category": "factor", "sector": "quality", "quality": "high", "cyclical": False,
             "expense_ratio": 0.15, "description": "质量因子（盈利质量/资产负债表更好）。"},
    "MTUM": {"name": "Momentum", "category": "factor", "sector": "momentum", "quality": "medium", "cyclical": True,
             "expense_ratio": 0.15, "description": "动量因子（趋势跟随），回撤时可能更“急”。"},
    "USMV": {"name": "Low Volatility", "category": "factor", "sector": "low_vol", "quality": "high", "cyclical": False,
             "expense_ratio": 0.15, "description": "低波动因子，回撤通常更小，但牛市可能跑输。"},
    "SCHD": {"name": "Dividend (Quality Income)", "category": "factor", "sector": "dividend", "quality": "high", "cyclical": False,
             "expense_ratio": 0.06, "description": "高股息/质量偏好，适合做现金流与防御风格配置。"},

    # =========================
    # SIZE (Small / Mid)
    # =========================
    "IWM": {"name": "Russell 2000", "category": "factor", "sector": "small_cap", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.19, "description": "小盘股（更顺周期、更高波动），适合小仓位卫星。"},
    "VB": {"name": "Small Cap", "category": "factor", "sector": "small_cap", "quality": "medium", "cyclical": True,
           "expense_ratio": 0.05, "description": "Vanguard小盘股，成本更低，长期配置更友好。"},
    "IJR": {"name": "S&P SmallCap 600", "category": "factor", "sector": "small_cap", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.06, "description": "标普小盘600，相对Russell 2000质量过滤更强一点。"},
    "MDY": {"name": "S&P MidCap 400", "category": "factor", "sector": "mid_cap", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.23, "description": "中盘股（介于大盘与小盘之间），更平衡但仍偏周期。"},
    "DIA": {"name": "Dow 30", "category": "benchmark", "sector": "dow_30", "quality": "high", "cyclical": True,
            "expense_ratio": 0.16, "description": "道琼斯30，集中度高、偏传统蓝筹。"},

    # =========================
    # REAL ESTATE (Broad REIT)
    # =========================
    "VNQ": {"name": "US REIT", "category": "thematic", "sector": "reit", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.12, "description": "全美REIT一篮子（房产/数据中心/塔等），利率敏感。"},

    # =========================
    # FIXED INCOME
    # =========================
    "BND": {"name": "Total US Bond", "category": "fixed_income", "sector": "bond_agg", "quality": "high", "cyclical": False,
            "expense_ratio": 0.03, "description": "美国综合债（国债+投资级公司债+MBS），做稳定器。"},
    "AGG": {"name": "US Aggregate Bond (iShares)", "category": "fixed_income", "sector": "bond_agg", "quality": "high", "cyclical": False,
            "expense_ratio": 0.03, "description": "iShares版综合债，对标BND。"},
    "TLT": {"name": "20+ Year Treasuries", "category": "fixed_income", "sector": "treasury_long", "quality": "high", "cyclical": False,
            "expense_ratio": 0.15, "description": "超长久期国债，对利率极敏感（弹性大/波动也大）。"},
    "IEF": {"name": "7-10 Year Treasuries", "category": "fixed_income", "sector": "treasury_intermediate", "quality": "high", "cyclical": False,
            "expense_ratio": 0.15, "description": "中久期国债（7-10年），比TLT温和。"},
    "IEI": {"name": "3-7 Year Treasuries", "category": "fixed_income", "sector": "treasury_short_intermediate", "quality": "high", "cyclical": False,
            "expense_ratio": 0.15, "description": "中短久期国债（3-7年）。"},
    "SHY": {"name": "1-3 Year Treasuries", "category": "fixed_income", "sector": "treasury_short", "quality": "high", "cyclical": False,
            "expense_ratio": 0.15, "description": "短久期国债（1-3年），更像现金增强。"},
    "SHV": {"name": "Short Treasury (0-1yr)", "category": "fixed_income", "sector": "treasury_ultra_short", "quality": "high", "cyclical": False,
            "expense_ratio": 0.15, "description": "超短国债（更接近现金替代）。"},
    "VGSH": {"name": "Short-Term Treasury (Vanguard)", "category": "fixed_income", "sector": "treasury_short", "quality": "high", "cyclical": False,
             "expense_ratio": 0.04, "description": "Vanguard短期国债，费用通常更低，偏现金替代。"},
    "SGOV": {"name": "0-3 Month T-Bills", "category": "fixed_income", "sector": "t_bill", "quality": "high", "cyclical": False,
             "expense_ratio": 0.09, "description": "超短T-Bill（接近货币基金体验），常用于闲钱停泊。"},
    "BIL": {"name": "1-3 Month T-Bills", "category": "fixed_income", "sector": "t_bill", "quality": "high", "cyclical": False,
            "expense_ratio": 0.14, "description": "短票据T-Bill，现金管理/利率工具。"},
    "TIP": {"name": "TIPS (Inflation-Protected)", "category": "fixed_income", "sector": "tips", "quality": "high", "cyclical": False,
            "expense_ratio": 0.18, "description": "通胀保值债（TIPS），对通胀预期更敏感。"},
    "LQD": {"name": "IG Corporate Bonds", "category": "fixed_income", "sector": "corporate_ig", "quality": "high", "cyclical": False,
            "expense_ratio": 0.14, "description": "投资级公司债，信用利差工具（比国债风险高）。"},
    "HYG": {"name": "High Yield Corp Bonds", "category": "fixed_income", "sector": "high_yield", "quality": "low", "cyclical": True,
            "expense_ratio": 0.49, "description": "高收益/垃圾债，风险更像股票，周期属性强。"},
    "JNK": {"name": "High Yield Corp Bonds (SPDR)", "category": "fixed_income", "sector": "high_yield", "quality": "low", "cyclical": True,
            "expense_ratio": 0.40, "description": "高收益债另一只常见ETF（与HYG同类）。"},
    "EMB": {"name": "EM USD Sovereign Bonds", "category": "fixed_income", "sector": "em_bonds", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.39, "description": "新兴市场美元主权债，受美元与风险偏好影响大。"},
    "PFF": {"name": "Preferred Stock", "category": "fixed_income", "sector": "preferred", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.46, "description": "优先股（介于股债之间），对利率与金融板块较敏感。"},
    "GOVT": {"name": "US Treasury (All Maturities)", "category": "fixed_income", "sector": "treasury_all", "quality": "high", "cyclical": False,
             "expense_ratio": 0.05, "description": "一篮子国债（全期限），做利率中性配置。"},
    "BNDX": {"name": "Intl Bond (Hedged)", "category": "fixed_income", "sector": "intl_bond_hedged", "quality": "high", "cyclical": False,
             "expense_ratio": 0.07, "description": "国际债券（通常做美元对冲），分散利率来源。"},
    "LQDH": {"name": "IG Corporate (Hedged)", "category": "fixed_income", "sector": "corporate_ig_hedged", "quality": "high", "cyclical": False,
             "expense_ratio": 0.27, "description": "对冲美元汇率的投资级公司债（更小众）。"},

    # =========================
    # COMMODITIES / GOLD
    # =========================
    "GLD": {"name": "Gold", "category": "thematic", "sector": "gold", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.40, "description": "黄金，偏避险/对冲极端风险与货币信用。"},
    "IAU": {"name": "Gold (Lower Fee)", "category": "thematic", "sector": "gold", "quality": "medium", "cyclical": True,
            "expense_ratio": 0.25, "description": "黄金低费率替代之一。"},
    "DBC": {"name": "Broad Commodities", "category": "thematic", "sector": "commodities", "quality": "low", "cyclical": True,
            "expense_ratio": 0.85, "description": "大宗商品综合（期货结构影响较大），偏通胀对冲。"},
    "PDBC": {"name": "Broad Commodities (No K-1)", "category": "thematic", "sector": "commodities", "quality": "low", "cyclical": True,
             "expense_ratio": 0.59, "description": "广义商品（常见卖点：税表/结构更友好），通胀敏感。"},

    # =========================
    # POWER & UTILITIES (AI BACKBONE)
    # =========================
    "XLU": {
        "name": "Utilities",
        "category": "sector",
        "sector": "utilities",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.09,
        "description": "传统公用事业，防御+利率敏感，但AI推高长期电力需求"
    },
    "VPU": {
        "name": "Utilities (Vanguard)",
        "category": "sector",
        "sector": "utilities",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.10,
        "description": "低费率公用事业ETF，适合长期配置"
    },
    "GRID": {
        "name": "Smart Grid",
        "category": "thematic",
        "sector": "power_grid",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.58,
        "description": "智能电网、输配电设备，AI电力升级核心受益者"
    },
    "UTES": {
        "name": "Energy Transition Utilities",
        "category": "thematic",
        "sector": "utilities_clean",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.50,
        "description": "新能源+电力基础设施（波动较高）"
    },

    # =========================
    # AI INFRASTRUCTURE
    # =========================

    "SMH": {
        "name": "Semiconductors",
        "category": "thematic",
        "sector": "semiconductors",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.35,
        "description": "半导体全产业链（设备+设计+制造），AI算力最直接受益者"
    },
    "SOXX": {
        "name": "Semiconductors (iShares)",
        "category": "thematic",
        "sector": "semiconductors",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.35,
        "description": "半导体ETF（偏龙头集中），周期性与弹性都很高"
    },
    "XSD": {
        "name": "Semiconductor Equal Weight",
        "category": "thematic",
        "sector": "semiconductors",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.35,
        "description": "等权半导体，减少NVDA/AVGO一极独大风险"
    },

    # 数据中心 / REIT
    "SRVR": {
        "name": "Data Center REITs",
        "category": "thematic",
        "sector": "data_centers",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.60,
        "description": "数据中心REIT（DLR/EQIX等），AI算力背后的“房地产+电力”"
    },
    "VPN": {
        "name": "US REIT",
        "category": "thematic",
        "sector": "reit",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.12,
        "description": "广义REIT（含数据中心、塔、工业地产）"
    },

    # =========================
    # INFRASTRUCTURE
    # =========================
    "PAVE": {
        "name": "US Infrastructure",
        "category": "thematic",
        "sector": "infrastructure",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.47,
        "description": "美国本土基础设施（工程/材料/设备），财政支出驱动"
    },
    "IFRA": {
        "name": "Infrastructure (iShares)",
        "category": "thematic",
        "sector": "infrastructure",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.40,
        "description": "偏工程/公共设施类基础设施，波动略低于PAVE"
    },
    "TOLZ": {
        "name": "Global Infrastructure",
        "category": "thematic",
        "sector": "infrastructure_global",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.41,
        "description": "全球基础设施（机场/港口/收费公路）"
    },

    # =========================
    # DEFENSE & AEROSPACE
    # =========================
    "ITA": {
        "name": "Aerospace & Defense",
        "category": "thematic",
        "sector": "defense",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.40,
        "description": "美国航天国防龙头（LMT/RTX/NOC），订单周期极长"
    },
    "XAR": {
        "name": "Aerospace & Defense (Equal Weight)",
        "category": "thematic",
        "sector": "defense",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.35,
        "description": "等权国防ETF，中小防务公司权重更高"
    },
    "PPA": {
        "name": "Aerospace & Defense",
        "category": "thematic",
        "sector": "defense",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.58,
        "description": "航天+军工，集中度略高"
    },

    # =========================
    # QUALITY / VALUE / DIVIDEND (CORE)
    # =========================
    "VYM": {
        "name": "High Dividend Yield",
        "category": "factor",
        "sector": "dividend",
        "quality": "medium",
        "cyclical": False,
        "expense_ratio": 0.06,
        "description": "高股息（偏金融/能源），现金流导向"
    },
    "DGRO": {
        "name": "Dividend Growth",
        "category": "factor",
        "sector": "dividend_growth",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.08,
        "description": "股息增长因子（质量+稳健），长期表现非常均衡"
    },
    "SPHQ": {
        "name": "Quality Factor (SPDR)",
        "category": "factor",
        "sector": "quality",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.15,
        "description": "质量因子（ROE/低负债/盈利稳定）"
    },
    "USQ": {
        "name": "US Quality Factor",
        "category": "factor",
        "sector": "quality",
        "quality": "high",
        "cyclical": False,
        "expense_ratio": 0.19,
        "description": "偏财务质量的系统化筛选ETF"
    },
    "AVUS": {
        "name": "US Equity (Value + Quality Tilt)",
        "category": "factor",
        "sector": "value_quality",
        "quality": "high",
        "cyclical": True,
        "expense_ratio": 0.15,
        "description": "Avantis体系：价值+盈利能力因子，长期因子投资代表"
    },

    # =========================
    # AI SEMICONDUCTORS (Wattage × Intelligence)
    # =========================
    "PSI": {
        "name": "Dynamic Semiconductors",
        "category": "thematic",
        "sector": "semiconductors",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.56,
        "description": "动态半导体策略（Invesco），相比SMH/SOXX更主动调仓"
    },

    # =========================
    # AI POWER / NUCLEAR / CLEAN ENERGY
    # =========================
    "URA": {
        "name": "Uranium & Nuclear",
        "category": "thematic",
        "sector": "nuclear",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.69,
        "description": "铀矿/核能ETF，AI数据中心核电需求暴增的核心受益者"
    },
    "ICLN": {
        "name": "Global Clean Energy",
        "category": "thematic",
        "sector": "clean_energy",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.40,
        "description": "全球清洁能源（风/光/氢能），政策驱动+长期趋势"
    },
    "TAN": {
        "name": "Solar Energy",
        "category": "thematic",
        "sector": "solar",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.67,
        "description": "太阳能产业链，周期性强、利率敏感，但AI电力需求长期利好"
    },

    # =========================
    # AI DATA CENTER / INFRASTRUCTURE
    # =========================
    "INFR": {
        "name": "Infrastructure (ClearBridge)",
        "category": "thematic",
        "sector": "infrastructure",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.43,
        "description": "基础设施主题（含通信塔/数据中心/电力设施），AI基建受益"
    },

    # =========================
    # AI ROBOTICS / AUTOMATION
    # =========================
    "BOTZ": {
        "name": "Robotics & AI",
        "category": "thematic",
        "sector": "ai_robotics",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.68,
        "description": "机器人与AI自动化龙头（NVDA/ABB/Keyence），Intelligence端核心"
    },
    "ROBO": {
        "name": "Robotics & Automation",
        "category": "thematic",
        "sector": "ai_robotics",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.95,
        "description": "机器人/自动化/3D打印全产业链，分散度更高但费率偏贵"
    },
    "IRBO": {
        "name": "Intl Robotics & AI",
        "category": "thematic",
        "sector": "ai_robotics",
        "quality": "medium",
        "cyclical": True,
        "expense_ratio": 0.47,
        "description": "全球机器人/AI（含日本/欧洲厂商），等权配置分散单一公司风险"
    },

    # =========================
    # AI MATERIALS (Tonnage)
    # =========================
    "COPX": {
        "name": "Copper Miners",
        "category": "thematic",
        "sector": "copper",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.65,
        "description": "铜矿ETF，AI/电动车/电网的红色金属，强周期+通胀敏感"
    },
    "LIT": {
        "name": "Lithium & Battery Tech",
        "category": "thematic",
        "sector": "lithium_battery",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.75,
        "description": "锂电池产业链（锂矿+电池制造），电动车/储能核心材料"
    },
    "PICK": {
        "name": "Metals & Mining (iShares)",
        "category": "thematic",
        "sector": "metals_mining",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.39,
        "description": "全球金属矿业巨头（必和必拓/力拓/淡水河谷），Tonnage的基础配置"
    },
    "REMX": {
        "name": "Rare Earth & Critical Metals",
        "category": "thematic",
        "sector": "rare_earth",
        "quality": "low",
        "cyclical": True,
        "expense_ratio": 0.56,
        "description": "稀土/战略金属，AI芯片/磁铁/电动车的关键上游，地缘政治敏感"
    }

}


class ETFEvaluator:
    """
    ETF-4Q Model Evaluator

    Scores ETFs on four dimensions:
    1. Macro Tailwind - Is the macro/cycle favorable?
    2. Quality - Earnings quality of underlying holdings
    3. Valuation - Relative to historical range
    4. Structure - Expense ratio, liquidity, concentration
    """

    # Expense ratio thresholds
    EXPENSE_THRESHOLDS = {
        'excellent': 0.10,  # ≤ 0.10%
        'good': 0.20,       # ≤ 0.20%
        'acceptable': 0.50, # ≤ 0.50%
        'high': 1.00,       # > 0.50%
    }

    # Decision thresholds (out of 18 = M4 + Q4 + V3 + S4 + Mom3)
    DECISION_THRESHOLDS = {
        'core': 14,      # ≥ 14: A+ Core/Satellite allocation
        'satellite': 10, # 10-13: A Good position
        'trade': 6,      # 6-9: B Fair / trading only
        'avoid': 0,      # < 6: C Avoid
    }

    def __init__(self, vix_level: float = None, cape_level: float = None):
        """
        Initialize evaluator with market context

        Args:
            vix_level: Current VIX (for macro assessment)
            cape_level: Current Shiller CAPE (for valuation context)
        """
        self.vix_level = vix_level
        self.cape_level = cape_level
        self._determine_macro_regime()

    def _determine_macro_regime(self):
        """Determine current macro regime based on available data"""
        # Simple regime detection based on VIX and CAPE
        self.regime = 'neutral'
        self.rate_environment = 'neutral'

        if self.vix_level:
            if self.vix_level > 25:
                self.regime = 'risk_off'
            elif self.vix_level < 15:
                self.regime = 'risk_on'

        if self.cape_level:
            if self.cape_level > 30:
                self.rate_environment = 'expensive'  # Favor value, defense
            elif self.cape_level < 20:
                self.rate_environment = 'cheap'  # Favor growth, cyclicals

    # Role tag Chinese explanations (Wattage × Tonnage × Intelligence framework)
    ROLE_TAG_DESCRIPTIONS = {
        'CORE': '核心仓位 - 长期持有的主力配置，如大盘指数ETF，占组合40-60%',
        'CORE-INTL': '国际核心 - 分散美国单一市场风险的海外发达市场配置',
        'HEDGE-CASH': '现金对冲 - 短期国债/货币替代，市场动荡时的安全港',
        'HEDGE-DURATION': '久期对冲 - 中长期国债，股票暴跌时通常上涨的避险资产',
        'HEDGE-INFL': '通胀对冲 - TIPS等通胀保值债券，应对物价上涨',
        'HEDGE': '综合对冲 - 固收类资产，降低组合整体波动',
        # Wattage × Tonnage × Intelligence (AI产业链)
        'AI-COMPUTE': 'AI算力 - 半导体/芯片(Intelligence)，AI产业链最核心受益者',
        'AI-SOFTWARE': 'AI软件 - 云计算/SaaS/网络安全，AI应用层',
        'AI-DATA': 'AI数据 - 数据中心REIT，算力背后的基础设施',
        'AI-POWER': 'AI电力 - 电网/核能/清洁能源(Wattage)，AI耗电量暴增的隐性受益者',
        'AI-ROBOTICS': 'AI机器人 - 机器人/自动化(Intelligence)，AI物理世界应用',
        'AI-MATERIALS': 'AI材料 - 铜/锂/稀土(Tonnage)，AI基础设施的原材料供应',
        'INCOME': '收益型 - 高股息/债券收益，适合追求现金流的配置',
        'DEFENSE': '国防军工 - 航天国防，地缘政治风险的对冲工具',
        'SATELLITE': '卫星仓位 - 小比例配置的进攻性资产，如行业主题ETF，高弹性但高风险',
    }

    def _get_role_tag(self, etf_info: dict) -> str:
        """
        Determine portfolio role tag based on priority rules:
        1. HEDGE - Fixed income treasuries
        2. INCOME - Dividend focused
        3. AI - AI/Tech infrastructure chain
        4. DEFENSE - Aerospace & defense
        5. CORE - Benchmark/broad market
        6. SATELLITE - Everything else
        """
        category = etf_info.get('category', '')
        sector = etf_info.get('sector', '')
        name = etf_info.get('name', '')

        # Priority 1: HEDGE (Fixed Income Treasuries)
        if category == 'fixed_income':
            if sector in {'treasury_short', 'treasury_ultra_short', 't_bill'}:
                return 'HEDGE-CASH'
            elif sector in {'treasury_long', 'treasury_intermediate', 'treasury_short_intermediate', 'treasury_all'}:
                return 'HEDGE-DURATION'
            elif sector == 'tips':
                return 'HEDGE-INFL'
            elif sector in {'bond_agg', 'intl_bond_hedged'}:
                return 'HEDGE'
            # High yield and EM bonds are not really hedge
            elif sector in {'high_yield', 'em_bonds', 'preferred'}:
                return 'INCOME'
            else:
                return 'HEDGE'

        # Priority 2: INCOME (Dividend focused)
        if sector in {'dividend', 'dividend_growth'}:
            return 'INCOME'
        if 'Dividend' in name or 'High Dividend' in name:
            return 'INCOME'

        # Priority 3: AI (AI/Tech infrastructure chain - Wattage × Tonnage × Intelligence)
        ai_sectors = {
            # Intelligence (算力)
            'semiconductors': 'AI-COMPUTE',
            'software': 'AI-SOFTWARE',
            'cloud': 'AI-SOFTWARE',
            'cybersecurity': 'AI-SOFTWARE',
            'ai_robotics': 'AI-ROBOTICS',
            # Data (数据)
            'data_centers': 'AI-DATA',
            # Wattage (电力)
            'power_grid': 'AI-POWER',
            'utilities': 'AI-POWER',
            'utilities_clean': 'AI-POWER',
            'nuclear': 'AI-POWER',
            'clean_energy': 'AI-POWER',
            'solar': 'AI-POWER',
            # Tonnage (材料)
            'copper': 'AI-MATERIALS',
            'lithium_battery': 'AI-MATERIALS',
            'rare_earth': 'AI-MATERIALS',
        }
        if sector in ai_sectors:
            return ai_sectors[sector]

        # Priority 4: DEFENSE (Aerospace & Defense)
        if sector in {'defense', 'aerospace'}:
            return 'DEFENSE'
        if 'Aerospace' in name or 'Defense' in name:
            return 'DEFENSE'

        # Priority 5: CORE (Benchmark/broad market)
        if category == 'benchmark':
            return 'CORE'
        if sector in {'broad', 'global', 'nasdaq_100', 'dow_30'}:
            return 'CORE'

        # Priority 6: International developed can be CORE-INTL
        if category == 'international' and sector in {'developed', 'intl_ex_us'}:
            return 'CORE-INTL'

        # Default: SATELLITE
        return 'SATELLITE'

    def _get_macro_score(self, etf_info: dict) -> Tuple[int, List[str]]:
        """
        Score macro tailwind (0-4)

        Considers:
        - Current economic cycle favorability
        - Rate environment
        - Policy/structural trends
        - Not in obvious headwind
        """
        score = 0
        notes = []
        sector = etf_info.get('sector', 'broad')
        is_cyclical = etf_info.get('cyclical', False)
        category = etf_info.get('category', 'benchmark')

        # Base score for non-cyclical, quality sectors
        if category == 'benchmark':
            score += 2
            notes.append("Benchmark: stable exposure")
        elif category == 'fixed_income':
            if self.regime == 'risk_off':
                score += 3
                notes.append("Risk-off: bonds favored")
            else:
                score += 1
                notes.append("Bonds: rate sensitive")
        elif category == 'factor':
            if sector == 'quality' or sector == 'low_vol':
                score += 2
                notes.append("Defensive factor")
            elif sector == 'dividend':
                score += 2
                notes.append("Income factor")
            else:
                score += 1
                notes.append("Factor exposure")

        # Cyclical adjustment
        if is_cyclical:
            if self.regime == 'risk_on':
                score += 1
                notes.append("Cyclical + risk-on")
            else:
                notes.append("Cyclical in uncertain regime")
        else:
            score += 1
            notes.append("Non-cyclical")

        # CAPE-based adjustment
        if self.cape_level and self.cape_level > 35:
            if sector in ['technology', 'growth', 'communication']:
                notes.append("Caution: high CAPE + growth sector")
            elif sector in ['value', 'dividend', 'utilities']:
                score += 1
                notes.append("Defensive tilt in high CAPE")

        return min(4, score), notes

    def _get_quality_score(self, etf_info: dict) -> Tuple[int, List[str]]:
        """
        Score earnings quality (0-4)

        Based on:
        - Sector ROIC characteristics
        - Earnings stability
        - Leverage profile
        """
        score = 0
        notes = []
        quality = etf_info.get('quality', 'medium')
        sector = etf_info.get('sector', 'broad')
        category = etf_info.get('category', 'benchmark')

        # Quality score by category
        if quality == 'high':
            score += 3
            notes.append("High quality holdings")
        elif quality == 'medium':
            score += 2
            notes.append("Medium quality")
        else:
            score += 1
            notes.append("Lower quality/cyclical")

        # Sector-specific adjustments
        if sector in ['technology', 'healthcare', 'consumer_staples']:
            score += 1
            notes.append(f"High ROIC sector: {sector}")
        elif sector in ['financials', 'real_estate']:
            notes.append("Leverage-dependent sector")
        elif sector in ['energy', 'materials']:
            notes.append("Commodity-dependent")

        # Fixed income quality
        if category == 'fixed_income':
            if 'treasury' in sector:
                score = 4
                notes = ["Treasury: highest credit quality"]
            else:
                score = 3
                notes = ["Investment grade fixed income"]

        return min(4, score), notes

    def _get_valuation_score(self, ticker_data: dict, etf_info: dict) -> Tuple[int, List[str]]:
        """
        Score valuation (0-3)

        Based on:
        - P/E vs historical
        - Yield vs historical
        - Relative to sector
        """
        score = 2  # Default to neutral
        notes = []

        pe_ratio = ticker_data.get('pe_ratio')
        dividend_yield = ticker_data.get('dividend_yield')
        ytd_return = ticker_data.get('ytd_return')

        # P/E based scoring
        if pe_ratio:
            if pe_ratio < 15:
                score = 3
                notes.append(f"P/E {pe_ratio:.1f}: attractive")
            elif pe_ratio < 22:
                score = 2
                notes.append(f"P/E {pe_ratio:.1f}: fair")
            elif pe_ratio < 30:
                score = 1
                notes.append(f"P/E {pe_ratio:.1f}: elevated")
            else:
                score = 0
                notes.append(f"P/E {pe_ratio:.1f}: expensive")

        # Dividend yield bonus
        if dividend_yield and dividend_yield > 2.5:
            notes.append(f"Yield {dividend_yield:.1f}%: income")

        # YTD momentum context
        if ytd_return:
            if ytd_return > 20:
                notes.append(f"YTD +{ytd_return:.1f}%: momentum")
            elif ytd_return < -10:
                notes.append(f"YTD {ytd_return:.1f}%: lagging")

        # Fixed income doesn't use P/E
        if etf_info.get('category') == 'fixed_income':
            score = 2
            notes = ["Fixed income: rate-dependent valuation"]
            if dividend_yield:
                if dividend_yield > 4:
                    score = 3
                    notes.append(f"Yield {dividend_yield:.1f}%: attractive")

        return min(3, score), notes

    def _get_structure_score(self, ticker_data: dict) -> Tuple[int, List[str]]:
        """
        Score ETF structure (0-4)

        Based on:
        - Expense ratio
        - Liquidity (AUM)
        - Concentration
        - No structural defects
        """
        score = 0
        notes = []

        expense_ratio = ticker_data.get('expense_ratio', 1.0)
        aum = ticker_data.get('aum', 0)

        # Expense ratio scoring
        if expense_ratio <= self.EXPENSE_THRESHOLDS['excellent']:
            score += 2
            notes.append(f"ER {expense_ratio:.2f}%: excellent")
        elif expense_ratio <= self.EXPENSE_THRESHOLDS['good']:
            score += 1
            notes.append(f"ER {expense_ratio:.2f}%: good")
        elif expense_ratio <= self.EXPENSE_THRESHOLDS['acceptable']:
            notes.append(f"ER {expense_ratio:.2f}%: acceptable")
        else:
            notes.append(f"ER {expense_ratio:.2f}%: high")

        # AUM/Liquidity scoring
        if aum:
            aum_b = aum / 1e9
            if aum_b > 10:
                score += 2
                notes.append(f"AUM ${aum_b:.0f}B: highly liquid")
            elif aum_b > 1:
                score += 1
                notes.append(f"AUM ${aum_b:.1f}B: liquid")
            else:
                notes.append(f"AUM ${aum_b*1000:.0f}M: smaller")

        return min(4, score), notes

    def _get_momentum_score(self, ticker_data: dict, etf_info: dict) -> Tuple[int, List[str]]:
        """
        Score momentum (0-3) - ENHANCED VERSION

        Scoring logic:
        1. Base score from YTD return (healthy range 15-50% gets max points)
        2. Overheating penalty: YTD > 80% is risky, cap at +2
        3. Short-term momentum: 3-month return must be positive
        4. Drawdown penalty: >15% from 52-week high is warning

        Final score = base_score - penalties (min 0)
        """
        score = 0
        notes = []
        ytd_return = ticker_data.get('ytd_return')
        return_3m = ticker_data.get('return_3m')
        drawdown_from_high = ticker_data.get('drawdown_from_high')  # negative number
        category = etf_info.get('category', 'benchmark')

        if ytd_return is None:
            notes.append("无YTD数据")
            return 0, notes

        # Fixed income - different thresholds
        if category == 'fixed_income':
            if ytd_return > 5:
                score = 3
                notes.append(f"YTD +{ytd_return:.1f}%: 固收超强")
            elif ytd_return > 2:
                score = 2
                notes.append(f"YTD +{ytd_return:.1f}%: 固收良好")
            elif ytd_return > 0:
                score = 1
                notes.append(f"YTD +{ytd_return:.1f}%: 固收正收益")
            else:
                notes.append(f"YTD {ytd_return:.1f}%: 固收承压")
            return min(3, score), notes

        # Equity / Thematic ETFs - Enhanced scoring
        # Step 1: Base score from YTD (healthy momentum = 20-50%)
        if 20 <= ytd_return <= 50:
            score = 3
            notes.append(f"YTD +{ytd_return:.1f}%: 健康动量✅")
        elif 50 < ytd_return <= 80:
            score = 2
            notes.append(f"YTD +{ytd_return:.1f}%: 强劲但偏热")
        elif ytd_return > 80:
            # Overheating penalty - cap at 2, might be topping
            score = 2
            notes.append(f"YTD +{ytd_return:.1f}%: 过热警告⚠️")
        elif 10 <= ytd_return < 20:
            score = 2
            notes.append(f"YTD +{ytd_return:.1f}%: 温和动量")
        elif 0 < ytd_return < 10:
            score = 1
            notes.append(f"YTD +{ytd_return:.1f}%: 弱正动量")
        elif ytd_return > -10:
            score = 0
            notes.append(f"YTD {ytd_return:.1f}%: 弱势")
        else:
            score = 0
            notes.append(f"YTD {ytd_return:.1f}%: 深度回调⚠️")

        # Step 2: Short-term momentum check (3-month)
        if return_3m is not None:
            if return_3m < -5:
                # Recent weakness - penalize
                score = max(0, score - 1)
                notes.append(f"近3月{return_3m:+.1f}%: 短期转弱⚠️")
            elif return_3m > 15:
                notes.append(f"近3月{return_3m:+.1f}%: 短期强劲")
            elif return_3m > 0:
                notes.append(f"近3月{return_3m:+.1f}%: 短期正向")

        # Step 3: Drawdown from 52-week high
        if drawdown_from_high is not None and drawdown_from_high < -15:
            # Significant drawdown - penalize
            score = max(0, score - 1)
            notes.append(f"离高点{drawdown_from_high:.1f}%: 回撤较大⚠️")
        elif drawdown_from_high is not None and drawdown_from_high > -5:
            notes.append(f"离高点{drawdown_from_high:.1f}%: 接近新高")

        return min(3, max(0, score)), notes

    def _get_recommendation(self, total_score: int) -> str:
        """Get recommendation based on total score (Grade: A+/A/B/C)"""
        if total_score >= self.DECISION_THRESHOLDS['core']:
            return "A+"  # Top tier - core holding
        elif total_score >= self.DECISION_THRESHOLDS['satellite']:
            return "A"   # Good - satellite position
        elif total_score >= self.DECISION_THRESHOLDS['trade']:
            return "B"   # Fair - trading only
        else:
            return "C"   # Poor - avoid

    def evaluate(self, symbol: str) -> Optional[ETFScore]:
        """
        Evaluate a single ETF using ETF-4Q model

        Args:
            symbol: ETF ticker

        Returns:
            ETFScore object or None if data unavailable
        """
        try:
            # Get ETF info from database
            etf_info = ETF_DATABASE.get(symbol, {
                'name': symbol,
                'category': 'unknown',
                'sector': 'unknown',
                'quality': 'medium',
                'cyclical': False
            })

            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                print(f"Warning: No data for {symbol}")
                return None

            # Extract ticker data
            price = info.get('regularMarketPrice') or info.get('previousClose', 0)

            # Prefer expense_ratio from our database (already in % form, e.g., 0.03 = 0.03%)
            expense_ratio = etf_info.get('expense_ratio', 0)
            if expense_ratio == 0:
                # Fallback to yfinance data (may be in decimal form, e.g., 0.0003 = 0.03%)
                expense_ratio = info.get('annualReportExpenseRatio', 0) or 0
                if expense_ratio == 0:
                    expense_ratio = info.get('totalExpenseRatio', 0)
                # yfinance returns decimal (0.0003), convert to percentage (0.03)
                if expense_ratio > 0 and expense_ratio < 0.01:
                    expense_ratio = expense_ratio * 100

            pe_ratio = info.get('trailingPE')
            dividend_yield = info.get('yield', 0) or info.get('dividendYield', 0)
            if dividend_yield and dividend_yield < 1:
                dividend_yield = dividend_yield * 100  # Convert to %
            aum = info.get('totalAssets', 0)

            # Calculate momentum metrics
            ytd_return = None
            return_3m = None
            drawdown_from_high = None
            try:
                hist = ticker.history(period='1y')
                if len(hist) > 0:
                    end_price = hist['Close'].iloc[-1]
                    start_price = hist['Close'].iloc[0]
                    ytd_return = (end_price / start_price - 1) * 100

                    # 3-month return (approx 63 trading days)
                    if len(hist) > 63:
                        price_3m_ago = hist['Close'].iloc[-63]
                        return_3m = (end_price / price_3m_ago - 1) * 100

                    # Drawdown from 52-week high
                    high_52w = hist['Close'].max()
                    drawdown_from_high = (end_price / high_52w - 1) * 100
            except:
                pass

            ticker_data = {
                'price': price,
                'expense_ratio': expense_ratio,
                'pe_ratio': pe_ratio,
                'dividend_yield': dividend_yield,
                'aum': aum,
                'ytd_return': ytd_return,
                'return_3m': return_3m,
                'drawdown_from_high': drawdown_from_high,
            }

            # Calculate scores
            macro_score, macro_notes = self._get_macro_score(etf_info)
            quality_score, quality_notes = self._get_quality_score(etf_info)
            valuation_score, valuation_notes = self._get_valuation_score(ticker_data, etf_info)
            structure_score, structure_notes = self._get_structure_score(ticker_data)
            momentum_score, momentum_notes = self._get_momentum_score(ticker_data, etf_info)

            # Total score (max 18 = M4 + Q4 + V3 + S4 + Mom3)
            total_score = macro_score + quality_score + valuation_score + structure_score + momentum_score
            recommendation = self._get_recommendation(total_score)

            # Get role tag and description
            role_tag = self._get_role_tag(etf_info)
            description = etf_info.get('description', '')

            return ETFScore(
                symbol=symbol,
                name=etf_info.get('name', symbol),
                category=etf_info.get('category', 'unknown'),
                price=price,
                expense_ratio=expense_ratio,
                macro_score=macro_score,
                macro_notes=macro_notes,
                quality_score=quality_score,
                quality_notes=quality_notes,
                valuation_score=valuation_score,
                valuation_notes=valuation_notes,
                structure_score=structure_score,
                structure_notes=structure_notes,
                momentum_score=momentum_score,
                momentum_notes=momentum_notes,
                total_score=total_score,
                recommendation=recommendation,
                ytd_return=ytd_return,
                dividend_yield=dividend_yield,
                pe_ratio=pe_ratio,
                aum=aum,
                role_tag=role_tag,
                description=description
            )

        except Exception as e:
            print(f"Error evaluating {symbol}: {e}")
            return None

    def evaluate_multiple(self, symbols: List[str]) -> List[ETFScore]:
        """
        Evaluate multiple ETFs

        Args:
            symbols: List of ETF tickers

        Returns:
            List of ETFScore objects, sorted by total score
        """
        results = []
        for symbol in symbols:
            score = self.evaluate(symbol)
            if score:
                results.append(score)

        # Sort by total score (highest first)
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def format_scores_text(self, scores: List[ETFScore]) -> str:
        """Format ETF scores as text for report"""
        if not scores:
            return "No ETF scores available.\n"

        lines = []
        lines.append("ETF-5Q EVALUATION (Macro × Quality × Valuation × Structure × Momentum)")
        lines.append("-" * 80)
        lines.append(f"{'ETF':<8} {'Name':<18} {'M':>2} {'Q':>2} {'V':>2} {'S':>2} {'Mom':>3} {'Total':>6} {'Grade':>6}")
        lines.append("-" * 80)

        # Group by category
        categories = {}
        for s in scores:
            cat = s.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(s)

        category_order = ['benchmark', 'sector', 'factor', 'fixed_income', 'international', 'thematic', 'unknown']

        for cat in category_order:
            if cat not in categories:
                continue

            cat_name = {
                'benchmark': '📊 BENCHMARK',
                'sector': '🏭 SECTOR',
                'factor': '📈 FACTOR',
                'fixed_income': '💵 FIXED INCOME',
                'international': '🌍 INTERNATIONAL',
                'thematic': '🚀 THEMATIC',
                'unknown': '❓ OTHER'
            }.get(cat, cat.upper())

            lines.append(f"\n{cat_name}")

            for s in categories[cat]:
                lines.append(
                    f"{s.symbol:<8} {s.name:<18} {s.macro_score:>2} {s.quality_score:>2} "
                    f"{s.valuation_score:>2} {s.structure_score:>2} {s.momentum_score:>3} "
                    f"{s.total_score:>5}/18 {s.recommendation:>6}"
                )

        # Add legend
        lines.append("")
        lines.append("Score Guide: M=Macro Q=Quality V=Valuation S=Structure Mom=Momentum")
        lines.append("  ≥14: A+ - Top tier, core holding")
        lines.append("  10-13: A - Good, satellite position")
        lines.append("  6-9: B - Fair, trading only")
        lines.append("  <6: C - Poor, avoid")

        # Top picks (A+)
        top_etfs = [s for s in scores if s.recommendation == 'A+']
        if top_etfs:
            lines.append("")
            lines.append("💡 TOP PICKS (A+):")
            for s in top_etfs:
                role_desc = self.ROLE_TAG_DESCRIPTIONS.get(s.role_tag, s.role_tag)
                lines.append(f"   • {s.symbol} ({s.name}): {s.total_score}/15")
                lines.append(f"     [{s.role_tag}] {role_desc.split(' - ')[1] if ' - ' in role_desc else ''}")
                if s.dividend_yield and s.dividend_yield > 1:
                    lines.append(f"     Yield: {s.dividend_yield:.1f}%")

        # Role tag legend
        lines.append("")
        lines.append("=" * 70)
        lines.append("ROLE TAG GUIDE (角色标签说明)")
        lines.append("=" * 70)
        for tag, desc in self.ROLE_TAG_DESCRIPTIONS.items():
            lines.append(f"  {tag:<15} {desc}")

        return "\n".join(lines)

    def format_scores_html(self, scores: List[ETFScore]) -> str:
        """Format ETF scores as HTML table"""
        if not scores:
            return "<p>No ETF scores available.</p>"

        html = ['<table style="border-collapse: collapse; width: 100%;">']
        html.append('<tr style="background-color: #2c5282; color: white;">')
        html.append('<th style="padding: 6px;">ETF</th>')
        html.append('<th style="padding: 6px;">Category</th>')
        html.append('<th style="padding: 6px;">M</th>')
        html.append('<th style="padding: 6px;">Q</th>')
        html.append('<th style="padding: 6px;">V</th>')
        html.append('<th style="padding: 6px;">S</th>')
        html.append('<th style="padding: 6px;">Mom</th>')
        html.append('<th style="padding: 6px;">Total</th>')
        html.append('<th style="padding: 6px;">Grade</th>')
        html.append('</tr>')

        for i, s in enumerate(scores):
            bg_color = "#f7fafc" if i % 2 == 0 else "#ffffff"

            action_color = {
                'CORE': '#276749',
                'SATELLITE': '#c05621',
                'TRADE': '#c53030',
                'AVOID': '#718096'
            }.get(s.recommendation, '#718096')

            cat_display = {
                'benchmark': 'Benchmark',
                'sector': 'Sector',
                'factor': 'Factor',
                'fixed_income': 'Fixed Inc',
                'international': 'Intl',
                'thematic': 'Thematic'
            }.get(s.category, s.category)

            # Momentum color (green for high, red for negative)
            mom_color = '#276749' if s.momentum_score >= 2 else ('#c05621' if s.momentum_score >= 1 else '#718096')

            html.append(f'<tr style="background-color: {bg_color};">')
            html.append(f'<td style="padding: 6px;"><b>{s.symbol}</b><br><small>{s.name}</small></td>')
            html.append(f'<td style="padding: 6px; text-align: center;"><small>{cat_display}</small></td>')
            html.append(f'<td style="padding: 6px; text-align: center;">{s.macro_score}</td>')
            html.append(f'<td style="padding: 6px; text-align: center;">{s.quality_score}</td>')
            html.append(f'<td style="padding: 6px; text-align: center;">{s.valuation_score}</td>')
            html.append(f'<td style="padding: 6px; text-align: center;">{s.structure_score}</td>')
            html.append(f'<td style="padding: 6px; text-align: center; color: {mom_color}; font-weight: bold;">{s.momentum_score}</td>')
            html.append(f'<td style="padding: 6px; text-align: center; font-weight: bold;">{s.total_score}/18</td>')
            html.append(f'<td style="padding: 6px; text-align: center; color: {action_color}; font-weight: bold;">{s.recommendation}</td>')
            html.append('</tr>')

        html.append('</table>')

        return '\n'.join(html)


# Default ETF list for evaluation
DEFAULT_ETFS = [
    # Benchmark
    'VTI', 'VOO', 'VT',
    # Sector - Growth
    'XLK', 'XLV', 'XLC',
    # Sector - Cyclical
    'XLE', 'XLF', 'XLI', 'XLB', 'XLU',
    # Factor
    'VUG', 'VTV', 'QUAL', 'MTUM', 'USMV', 'SCHD',
    # Fixed Income
    'TLT', 'VGSH', 'BND',
    # AI Chain (Wattage × Tonnage × Intelligence)
    'SMH', 'SOXX',  # AI-COMPUTE (半导体)
    'URA', 'GRID',  # AI-POWER (核能/电网)
    'BOTZ',         # AI-ROBOTICS (机器人)
    'COPX', 'LIT',  # AI-MATERIALS (铜/锂)
]


if __name__ == "__main__":
    # Test ETF evaluator
    print("=" * 70)
    print("ETF-4Q MODEL EVALUATION")
    print("=" * 70)

    # Initialize with market context
    evaluator = ETFEvaluator(vix_level=18.0, cape_level=35.0)

    print(f"\nMarket Context:")
    print(f"  VIX: {evaluator.vix_level}")
    print(f"  CAPE: {evaluator.cape_level}")
    print(f"  Regime: {evaluator.regime}")
    print()

    # Evaluate ETFs
    scores = evaluator.evaluate_multiple(DEFAULT_ETFS)

    print(evaluator.format_scores_text(scores))

    # Show detailed breakdown for top ETF
    if scores:
        top = scores[0]
        print("\n" + "=" * 70)
        print(f"DETAILED: {top.symbol} - {top.name}")
        print("=" * 70)
        print(f"Price: ${top.price:.2f}")
        print(f"Category: {top.category}")
        print(f"\nMacro Score: {top.macro_score}/4")
        for note in top.macro_notes:
            print(f"  • {note}")
        print(f"\nQuality Score: {top.quality_score}/4")
        for note in top.quality_notes:
            print(f"  • {note}")
        print(f"\nValuation Score: {top.valuation_score}/3")
        for note in top.valuation_notes:
            print(f"  • {note}")
        print(f"\nStructure Score: {top.structure_score}/4")
        for note in top.structure_notes:
            print(f"  • {note}")
        print(f"\n{'='*30}")
        print(f"TOTAL SCORE: {top.total_score}/15")
        print(f"RECOMMENDATION: {top.recommendation}")
