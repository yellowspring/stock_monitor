"""
Alerting module for crash probability notifications
Supports Email (SMTP) and SMS (Twilio)
"""
import smtplib
import os
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Optional
from io import BytesIO

# PDF generation imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True

    # Try to register Chinese font
    CHINESE_FONT_AVAILABLE = False
    CHINESE_FONT_NAME = 'Helvetica'  # Default fallback

    # Common Chinese font paths
    _chinese_font_paths = [
        # Linux
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        # macOS
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        # Windows (via WSL)
        '/mnt/c/Windows/Fonts/msyh.ttc',
        '/mnt/c/Windows/Fonts/simsun.ttc',
        '/mnt/c/Windows/Fonts/simhei.ttf',
    ]

    for _font_path in _chinese_font_paths:
        if os.path.exists(_font_path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', _font_path))
                CHINESE_FONT_NAME = 'ChineseFont'
                CHINESE_FONT_AVAILABLE = True
                break
            except Exception:
                continue

except ImportError:
    PDF_AVAILABLE = False
    CHINESE_FONT_AVAILABLE = False
    CHINESE_FONT_NAME = 'Helvetica'


class CrashAlerter:
    """Send alerts when crash probability exceeds threshold"""

    def __init__(
        self,
        alert_threshold: float = 60.0,
        enable_email: bool = False,
        enable_sms: bool = False
    ):
        """
        Initialize alerter

        Args:
            alert_threshold: Probability threshold to trigger alerts (0-100)
            enable_email: Enable email alerts
            enable_sms: Enable SMS alerts via Twilio
        """
        self.alert_threshold = alert_threshold
        self.enable_email = enable_email
        self.enable_sms = enable_sms

        # Email configuration (from environment variables)
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.email_to = os.getenv('EMAIL_TO', '')

        # Twilio configuration (from environment variables)
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.twilio_from = os.getenv('TWILIO_FROM', '')
        self.twilio_to = os.getenv('TWILIO_TO', '')

    def check_and_alert(
        self,
        crash_probability: float,
        spy_price: float,
        qqq_price: float,
        vix_level: float,
        date: Optional[str] = None
    ) -> bool:
        """
        Check if alert should be sent and send if needed

        Args:
            crash_probability: Current crash probability (0-100)
            spy_price: Current SPY price
            qqq_price: Current QQQ price
            vix_level: Current VIX level
            date: Date of prediction (None for today)

        Returns:
            True if alert was sent, False otherwise
        """
        if crash_probability < self.alert_threshold:
            return False

        # Determine risk level
        if crash_probability >= 80:
            risk_level = "EXTREME"
            urgency = "URGENT"
        elif crash_probability >= 60:
            risk_level = "EXTREME"
            urgency = "HIGH"
        elif crash_probability >= 40:
            risk_level = "HIGH"
            urgency = "MODERATE"
        else:
            risk_level = "MODERATE"
            urgency = "LOW"

        date_str = date or datetime.now().strftime('%Y-%m-%d')

        # Create alert message
        subject = f"🚨 CRASH ALERT: {crash_probability:.1f}% Risk - {risk_level} ({urgency})"

        message = self._create_alert_message(
            crash_probability, spy_price, qqq_price, vix_level,
            risk_level, urgency, date_str
        )

        # Send alerts
        alert_sent = False

        if self.enable_email:
            email_sent = self.send_email_alert(subject, message)
            alert_sent = alert_sent or email_sent

        if self.enable_sms:
            sms_sent = self.send_sms_alert(
                f"CRASH ALERT: {crash_probability:.1f}% - {risk_level}"
            )
            alert_sent = alert_sent or sms_sent

        return alert_sent

    def _create_alert_message(
        self,
        crash_probability: float,
        spy_price: float,
        qqq_price: float,
        vix_level: float,
        risk_level: str,
        urgency: str,
        date_str: str
    ) -> str:
        """Create formatted alert message"""
        message = f"""
CRASH PROBABILITY ALERT
{'=' * 50}

Date: {date_str}
Crash Probability: {crash_probability:.1f}/100
Risk Level: {risk_level}
Urgency: {urgency}

{'=' * 50}
MARKET DATA
{'=' * 50}

SPY: ${spy_price:.2f}
QQQ: ${qqq_price:.2f}
VIX: {vix_level:.2f}

{'=' * 50}
INTERPRETATION
{'=' * 50}

The model estimates a {crash_probability:.1f}% probability that SPY or QQQ
will experience a ≥15% drawdown within the next 20 trading days.

"""
        if crash_probability >= 80:
            message += """
⚠️  EXTREME RISK DETECTED ⚠️

This is an EXTREME crash probability level, similar to conditions
seen before major market crashes (2008, 2020).

RECOMMENDED ACTIONS:
• Review all positions immediately
• Consider significant de-risking
• Implement hedging strategies
• Preserve capital
• Consult financial advisor
"""
        elif crash_probability >= 60:
            message += """
⚠️  HIGH CRASH RISK ⚠️

Elevated crash probability detected. Multiple risk indicators
are showing stress.

RECOMMENDED ACTIONS:
• Reduce equity exposure
• Tighten stop losses
• Consider hedging
• Review portfolio risk
• Monitor daily
"""
        else:
            message += """
⚠️  MODERATE RISK ELEVATION ⚠️

Crash probability has exceeded your alert threshold.

RECOMMENDED ACTIONS:
• Monitor positions closely
• Review stop loss levels
• Reduce leverage if applicable
• Stay informed
"""

        message += f"""

{'=' * 50}

This alert was generated by the Crash Probability Index system.
Threshold: {self.alert_threshold}%

⚠️  DISCLAIMER: This is not financial advice. Always do your own
research and consult with qualified financial professionals.
"""
        return message

    def send_email_alert(self, subject: str, message: str) -> bool:
        """
        Send email alert via SMTP

        Args:
            subject: Email subject
            message: Email body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.email_from or not self.email_to or not self.email_password:
            print("⚠️  Email not configured. Set EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject

            msg.attach(MIMEText(message, 'plain'))

            # Connect to SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_from, self.email_password)

            # Send email
            server.send_message(msg)
            server.quit()

            print(f"✓ Email alert sent to {self.email_to}")
            return True

        except Exception as e:
            print(f"✗ Failed to send email: {e}")
            return False

    def send_email_with_pdf(
        self,
        subject: str,
        message: str,
        pdf_bytes: Optional[bytes],
        date_str: str
    ) -> bool:
        """
        Send email with PDF attachment

        Args:
            subject: Email subject
            message: Email body (plain text)
            pdf_bytes: PDF file as bytes (optional)
            date_str: Date string for filename

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.email_from or not self.email_to or not self.email_password:
            print("⚠️  Email not configured. Set EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject

            # Add plain text body
            msg.attach(MIMEText(message, 'plain'))

            # Attach PDF if available
            if pdf_bytes:
                pdf_attachment = MIMEBase('application', 'pdf')
                pdf_attachment.set_payload(pdf_bytes)
                encoders.encode_base64(pdf_attachment)
                pdf_filename = f"Market_Report_{date_str}.pdf"
                pdf_attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{pdf_filename}"'
                )
                msg.attach(pdf_attachment)
                print(f"✓ PDF report generated: {pdf_filename}")

            # Connect to SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_from, self.email_password)

            # Send email
            server.send_message(msg)
            server.quit()

            print(f"✓ Email with PDF sent to {self.email_to}")
            return True

        except Exception as e:
            print(f"✗ Failed to send email with PDF: {e}")
            return False

    def send_daily_report(
        self,
        crash_probability: float,
        spy_price: float,
        qqq_price: float,
        vix_level: float,
        spy_change: float = None,
        qqq_change: float = None,
        stress_score: float = None,
        stress_acceleration: float = None,
        false_calm: bool = False,
        skew_level: float = None,
        credit_spread_change: float = None,
        recent_history: list = None,
        stock_risks: list = None,
        cfq_scores: list = None,
        etf_scores: list = None,
        cape_analysis = None,
        cycle_state = None,  # CycleState from cycle_detector
        crypto_scores: list = None,  # CryptoScore list from crypto_scorer
        crypto_trends: list = None,  # CryptoTrend list from crypto_trend
        stock_scan_results: list = None,  # StockScanResult list from stock_scanner
        futures_data = None,  # FuturesData from futures_fetcher
        date: Optional[str] = None
    ) -> bool:
        """
        Send daily market report email (regardless of alert threshold)

        Args:
            crash_probability: Current crash probability (0-100)
            spy_price: Current SPY price
            crypto_trends: CryptoTrend list with trend analysis
            qqq_price: Current QQQ price
            futures_data: FuturesData object with futures premium/discount
            vix_level: Current VIX level
            stress_score: Current stress composite score (0-100)
            stress_acceleration: 5-day stress acceleration
            false_calm: Whether false calm detector is triggered
            skew_level: Current SKEW index level
            credit_spread_change: 5-day credit spread change %
            recent_history: List of recent probabilities [(date, prob), ...]
            stock_risks: List of StockRisk objects for individual stocks
            cape_analysis: CAPEAnalysis object with CAPE valuation data
            date: Date of report (None for today)

        Returns:
            True if sent successfully, False otherwise
        """
        date_str = date or datetime.now().strftime('%Y-%m-%d')

        # Determine risk level
        if crash_probability >= 80:
            risk_level = "🔴 EXTREME"
            risk_emoji = "🚨"
        elif crash_probability >= 60:
            risk_level = "🟠 HIGH"
            risk_emoji = "⚠️"
        elif crash_probability >= 40:
            risk_level = "🟡 ELEVATED"
            risk_emoji = "⚡"
        elif crash_probability >= 20:
            risk_level = "🟢 MODERATE"
            risk_emoji = "📊"
        else:
            risk_level = "🟢 LOW"
            risk_emoji = "✅"

        # Determine stress level
        if stress_score is not None:
            if stress_score >= 90:
                stress_level = "🔴 CRITICAL (Top 10%)"
            elif stress_score >= 75:
                stress_level = "🟠 ELEVATED (Top 25%)"
            elif stress_score >= 50:
                stress_level = "🟡 MODERATE"
            else:
                stress_level = "🟢 LOW"
        else:
            stress_level = "N/A"

        subject = f"{risk_emoji} Daily Market Report - {date_str} | Risk: {crash_probability:.1f}%"

        message = self._create_daily_report(
            crash_probability=crash_probability,
            spy_price=spy_price,
            qqq_price=qqq_price,
            vix_level=vix_level,
            spy_change=spy_change,
            qqq_change=qqq_change,
            risk_level=risk_level,
            stress_score=stress_score,
            stress_level=stress_level,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
            cfq_scores=cfq_scores,
            etf_scores=etf_scores,
            cape_analysis=cape_analysis,
            cycle_state=cycle_state,
            crypto_scores=crypto_scores,
            crypto_trends=crypto_trends,
            stock_scan_results=stock_scan_results,
            futures_data=futures_data,
            date_str=date_str
        )

        # Generate PDF report
        pdf_bytes = self._create_pdf_report(
            crash_probability=crash_probability,
            spy_price=spy_price,
            qqq_price=qqq_price,
            vix_level=vix_level,
            spy_change=spy_change,
            qqq_change=qqq_change,
            risk_level=risk_level,
            stress_score=stress_score,
            stress_level=stress_level,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
            cfq_scores=cfq_scores,
            etf_scores=etf_scores,
            cape_analysis=cape_analysis,
            cycle_state=cycle_state,
            crypto_scores=crypto_scores,
            crypto_trends=crypto_trends,
            stock_scan_results=stock_scan_results,
            futures_data=futures_data,
            date_str=date_str
        )

        # Send email with PDF attachment
        return self.send_email_with_pdf(subject, message, pdf_bytes, date_str)

    def _create_daily_report(
        self,
        crash_probability: float,
        spy_price: float,
        qqq_price: float,
        vix_level: float,
        spy_change: float,
        qqq_change: float,
        risk_level: str,
        stress_score: float,
        stress_level: str,
        stress_acceleration: float,
        false_calm: bool,
        skew_level: float,
        credit_spread_change: float,
        recent_history: list,
        stock_risks: list,
        cfq_scores: list,
        etf_scores: list,
        cape_analysis,
        cycle_state,  # CycleState from cycle_detector
        crypto_scores: list,  # CryptoScore list from crypto_scorer
        crypto_trends: list,  # CryptoTrend list from crypto_trend
        stock_scan_results: list,  # StockScanResult list from stock_scanner
        futures_data,  # FuturesData from futures_fetcher
        date_str: str
    ) -> str:
        """Create formatted daily report message"""

        # Build crypto trend section
        crypto_trend_section = ""
        if crypto_trends and len(crypto_trends) > 0:
            crypto_trend_section = f"""
📈 CRYPTO TREND ANALYSIS (加密货币趋势分析)
{'-' * 60}
"""
            for t in crypto_trends:
                arrow = {
                    'STRONG_BULL': '⬆️⬆️', 'BULL': '⬆️', 'NEUTRAL': '➡️',
                    'BEAR': '⬇️', 'STRONG_BEAR': '⬇️⬇️'
                }.get(t.overall_trend, '➡️')
                crypto_trend_section += f"\n{t.name} ({t.symbol})\n"
                crypto_trend_section += f"  Price: ${t.price:,.2f}  |  24h: {t.change_24h:+.1f}%  |  7d: {t.change_7d:+.1f}%  |  30d: {t.change_30d:+.1f}%\n"
                crypto_trend_section += f"  Trend: {arrow} {t.overall_trend} (Score: {t.trend_score:+d}, Confidence: {t.confidence})\n"
                crypto_trend_section += f"  预测: {t.prediction}\n"

                # Timeframe trends
                for tf, trend in [('Daily', t.daily_trend), ('Weekly', t.weekly_trend), ('Monthly', t.monthly_trend)]:
                    tf_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(trend.trend, '⚪')
                    crypto_trend_section += f"    {tf}: {tf_emoji} {trend.trend} | Price vs MA: {trend.price_vs_ma:+.1f}%\n"

                # Momentum
                rsi_emoji = {'OVERSOLD': '🟢', 'NEUTRAL': '🟡', 'OVERBOUGHT': '🔴'}.get(t.momentum.rsi_signal, '⚪')
                crypto_trend_section += f"  RSI(14): {t.momentum.rsi_14:.1f} {rsi_emoji} {t.momentum.rsi_signal}\n"

        # Build futures premium/discount section
        futures_section = ""
        if futures_data is not None:
            futures_section = f"""
📈 FUTURES PREMIUM/DISCOUNT (期货溢价/折价)
{'-' * 50}
{'Index':<15} {'Futures':>10} {'Spot Equiv':>12} {'Premium':>10} {'Signal':>10}
{'-' * 50}
"""
            if futures_data.sp500:
                fp = futures_data.sp500
                spot_equiv = fp.spot_price * 10.0  # SPY * 10 ≈ S&P 500
                sign = "+" if fp.premium_pct > 0 else ""
                signal_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(fp.signal, '⚪')
                futures_section += f"{'S&P 500 (ES)':<15} {fp.futures_price:>10.2f} {spot_equiv:>12.2f} {sign}{fp.premium_pct:>9.2f}% {signal_emoji} {fp.signal}\n"

            if futures_data.nasdaq:
                fp = futures_data.nasdaq
                spot_equiv = fp.spot_price * 40.0  # QQQ * 40 ≈ Nasdaq-100
                sign = "+" if fp.premium_pct > 0 else ""
                signal_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴'}.get(fp.signal, '⚪')
                futures_section += f"{'Nasdaq-100 (NQ)':<15} {fp.futures_price:>10.2f} {spot_equiv:>12.2f} {sign}{fp.premium_pct:>9.2f}% {signal_emoji} {fp.signal}\n"

            overall_emoji = {'BULLISH': '🟢', 'NEUTRAL': '🟡', 'BEARISH': '🔴', 'UNKNOWN': '⚪'}.get(futures_data.overall_signal, '⚪')
            futures_section += f"\n   Overall: {overall_emoji} {futures_data.overall_signal}\n"
            futures_section += f"   {futures_data.overall_interpretation}\n"

        # Build history section
        history_section = ""
        if recent_history:
            history_section = "\n📈 RECENT HISTORY (Last 5 Days)\n" + "-" * 40 + "\n"
            for hist_date, hist_prob in recent_history[-5:]:
                trend = "↑" if hist_prob > 50 else "↓" if hist_prob < 30 else "→"
                history_section += f"   {hist_date}: {hist_prob:.1f}% {trend}\n"

        # Build individual stock risks section
        stock_section = ""
        if stock_risks and len(stock_risks) > 0:
            stock_section = f"""
📊 INDIVIDUAL STOCK RISK ASSESSMENT
{'-' * 50}
{'Stock':<15} {'Price':>10} {'Risk':>8} {'Level':>10} {'Beta':>6}
{'-' * 50}
"""
            for risk in stock_risks:
                level_emoji = {
                    'HIGH': '🔴',
                    'MODERATE': '🟡',
                    'NORMAL': '🟢',
                    'LOW': '🟢'
                }.get(risk.risk_level, '⚪')
                stock_section += f"{risk.name:<15} ${risk.price:>8.2f} {risk.crash_probability:>6.1f}% {level_emoji} {risk.risk_level:<8} {risk.beta:>5.2f}\n"

            # High risk warnings
            high_risk_stocks = [r for r in stock_risks if r.risk_level == 'HIGH']
            if high_risk_stocks:
                stock_section += f"\n⚠️  HIGH RISK STOCKS:\n"
                for risk in high_risk_stocks:
                    stock_section += f"   • {risk.name} ({risk.symbol}): {risk.crash_probability:.1f}%\n"
                    stock_section += f"     Beta: {risk.beta:.2f}, Vol: {risk.volatility_30d:.1f}%, From High: {risk.distance_from_high:.1f}%\n"

        # Build CFQ valuation section
        cfq_section = ""
        if cfq_scores and len(cfq_scores) > 0:
            cfq_section = f"""
💰 CFQ VALUATION (Cashflow × Quality × Price)
{'-' * 60}
{'Stock':<12} {'Price':>10} {'FCF':>4} {'Qual':>4} {'Price':>5} {'Total':>6} {'Action':>8}
{'-' * 60}
"""
            for s in cfq_scores:
                action_emoji = {
                    'BUY': '✅',
                    'WATCH': '👀',
                    'AVOID': '⚠️',
                    'SKIP': '❌'
                }.get(s.recommendation, '')
                cfq_section += f"{s.name:<12} ${s.price:>8.2f} {s.fcf_score:>4} {s.quality_score:>4} {s.price_score:>5} {s.total_score:>5}/15 {action_emoji} {s.recommendation}\n"

            # Highlight buy recommendations
            buy_stocks = [s for s in cfq_scores if s.recommendation == 'BUY']
            if buy_stocks:
                cfq_section += f"\n💡 TOP PICKS (Score ≥ 12):\n"
                for s in buy_stocks:
                    cfq_section += f"   • {s.name}: {s.total_score}/15\n"
                    if s.ev_to_fcf:
                        cfq_section += f"     FCF Yield: {s.fcf_yield*100:.1f}%, EV/FCF: {s.ev_to_fcf:.1f}x\n"
                    else:
                        cfq_section += f"     FCF Yield: {s.fcf_yield*100:.1f}%\n"

        # Build ETF-4Q evaluation section
        etf_section = ""
        if etf_scores and len(etf_scores) > 0:
            etf_section = f"""
📊 ETF-4Q EVALUATION (Macro × Quality × Valuation × Structure)
{'-' * 70}
{'ETF':<8} {'Name':<18} {'M':>2} {'Q':>2} {'V':>2} {'S':>2} {'Total':>6} {'Action':>10}
{'-' * 70}
"""
            # Group by category
            categories = {}
            for s in etf_scores:
                cat = s.category
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(s)

            cat_names = {
                'benchmark': '📊 Benchmark (基准)',
                'sector': '🏭 Sector (行业)',
                'factor': '📈 Factor (因子)',
                'fixed_income': '💵 Fixed Income (固收)',
                'international': '🌍 International (国际)',
                'thematic': '🚀 Thematic (主题)',
                'unknown': '📦 Other (其他)'
            }

            # Use predefined order, then add any remaining categories
            cat_order = ['benchmark', 'sector', 'factor', 'fixed_income', 'international', 'thematic']
            for cat in list(categories.keys()):
                if cat not in cat_order:
                    cat_order.append(cat)

            for cat in cat_order:
                if cat not in categories:
                    continue
                etf_section += f"\n{cat_names.get(cat, f'📦 {cat.title()}')}\n"
                for s in categories[cat]:
                    grade_emoji = {'A+': '✅', 'A': '👍', 'B': '⚠️', 'C': '❌'}.get(s.recommendation, '')
                    role_tag = getattr(s, 'role_tag', '') or ''
                    etf_section += f"{s.symbol:<8} {s.name:<18} {s.macro_score:>2} {s.quality_score:>2} {s.valuation_score:>2} {s.structure_score:>2} {s.total_score:>5}/15 {grade_emoji} {s.recommendation} [{role_tag}]\n"

            # Top picks (A+)
            top_etfs = [s for s in etf_scores if s.recommendation == 'A+']
            if top_etfs:
                etf_section += f"\n💡 TOP PICKS (A+):\n"
                for s in top_etfs:
                    role_tag = getattr(s, 'role_tag', '') or ''
                    etf_section += f"   • {s.symbol} ({s.name}): {s.total_score}/15 [{role_tag}]\n"

        # Pre-compute formatted strings for use in report
        accel_str = f"{stress_acceleration:+.1f}" if stress_acceleration is not None else "N/A"
        skew_str = f"{skew_level:.1f}" if skew_level is not None else "N/A"
        skew_warning = "⚠️ ELEVATED" if skew_level and skew_level > 135 else ""
        credit_str = f"{credit_spread_change:+.2f}%" if credit_spread_change is not None else "N/A"
        credit_warning = "⚠️ WIDENING" if credit_spread_change and credit_spread_change < -1 else ""
        stress_score_str = f"{stress_score:.1f}" if stress_score is not None else "N/A"

        # Build stress section
        stress_section = ""
        if stress_score is not None:
            stress_section = f"""
📊 STRESS INDICATORS
{'-' * 40}
   Stress Score:      {stress_score:.1f}/100 ({stress_level})
   5-Day Acceleration: {accel_str}
   SKEW Index:        {skew_str} {skew_warning}
   Credit Spread Δ:   {credit_str} {credit_warning}
"""

        # False calm warning
        false_calm_warning = ""
        if false_calm:
            false_calm_warning = """
🔔 FALSE CALM DETECTED!
{'-' * 40}
   VIX appears calm but:
   • SKEW elevated (institutions hedging)
   • Credit spreads widening
   This pattern often precedes volatility spikes.
"""

        # VIX interpretation
        if vix_level < 12:
            vix_status = "🟢 VERY LOW (Complacency)"
        elif vix_level < 15:
            vix_status = "🟢 LOW"
        elif vix_level < 20:
            vix_status = "🟢 NORMAL"
        elif vix_level < 25:
            vix_status = "🟠 ELEVATED"
        elif vix_level < 30:
            vix_status = "🟠 HIGH"
        elif vix_level < 40:
            vix_status = "🔴 VERY HIGH"
        else:
            vix_status = "🔴 EXTREME (Panic)"

        # CAPE section
        cape_section = ""
        if cape_analysis is not None:
            cape_emoji = {
                'EXTREME': '🔴',
                'HIGH': '🟠',
                'ELEVATED': '🟡',
                'NORMAL': '🟢',
                'LOW': '🟢'
            }.get(cape_analysis.cape_level, '⚪')

            premium_to_median = ((cape_analysis.current_cape / cape_analysis.historical_median) - 1) * 100
            cape_section = f"""
📊 SHILLER CAPE VALUATION
{'-' * 40}
   Current CAPE:       {cape_analysis.current_cape:.1f} {cape_emoji} {cape_analysis.cape_level}
   Historical Pctl:    {cape_analysis.cape_percentile:.0f}%
   Historical Avg:     {cape_analysis.historical_avg:.1f}
   Historical Median:  {cape_analysis.historical_median:.1f}
   Premium to Median:  {premium_to_median:+.0f}%
   Implied 10Y Return: ~{cape_analysis.implied_return_10y:.1f}% p.a.
"""

        # SKEW interpretation
        if skew_level is not None:
            if skew_level < 115:
                skew_status = "🟢 LOW (Balanced)"
            elif skew_level < 125:
                skew_status = "🟢 NORMAL"
            elif skew_level < 135:
                skew_status = "🟠 ELEVATED"
            elif skew_level < 145:
                skew_status = "🟠 HIGH (Hedging)"
            elif skew_level < 155:
                skew_status = "🔴 VERY HIGH"
            else:
                skew_status = "🔴 EXTREME (Heavy Tail Protection)"
        else:
            skew_status = "N/A"

        message = f"""
{'=' * 50}
       DAILY MARKET MONITOR REPORT
{'=' * 50}

📅 Date: {date_str}

{'=' * 50}
🎯 CRASH PROBABILITY INDEX
{'=' * 50}

   Current Level:  {crash_probability:.1f}/100
   Risk Level:     {risk_level}

   Interpretation:
   {crash_probability:.1f}% probability of ≥15% drawdown in next 20 days

{'=' * 50}
📈 MARKET SNAPSHOT
{'=' * 50}

   SPY:  ${spy_price:.2f}
   QQQ:  ${qqq_price:.2f}
   VIX:  {vix_level:.2f} {vix_status}
{futures_section}
{stress_section}
{cape_section}
{false_calm_warning}
{stock_section}
{cfq_section}
{etf_section}
{crypto_trend_section}
{history_section}
{'=' * 50}
📋 CRASH PROBABILITY GUIDE
{'=' * 50}

   0-20%:   LOW - Normal market conditions
   20-40%:  MODERATE - Monitor positions
   40-60%:  ELEVATED - Consider reducing exposure
   60-80%:  HIGH - Significant de-risking recommended
   80-100%: EXTREME - Maximum caution, similar to 2008/2020

{'=' * 50}
📖 INDICATOR REFERENCE GUIDE
{'=' * 50}

📊 VIX (Volatility Index) - "Fear Gauge"
   Measures expected 30-day S&P 500 volatility.
   Current: {vix_level:.2f}
   ----------------------------------------
   <12:     Very Low (Market complacent, potential reversal)
   12-15:   Low (Calm markets)
   15-20:   Normal (Typical conditions)
   20-25:   Elevated (Increased uncertainty)
   25-30:   High (Significant fear)
   30-40:   Very High (Market stress)
   >40:     Extreme (Panic, e.g., 2008: 80+, 2020: 82)

📊 SKEW Index - "Tail Risk Indicator"
   Measures demand for out-of-money put options.
   High SKEW = institutions buying crash protection.
   Current: {skew_str} {skew_status}
   ----------------------------------------
   <115:    Low (Balanced sentiment)
   115-125: Normal (Typical hedging)
   125-135: Elevated (Above-average hedging)
   135-145: High (Smart money buying protection)
   145-155: Very High (Heavy tail hedging)
   >155:    Extreme (Rare, major crash fears)

   ⚠️ WARNING: Low VIX + High SKEW = "False Calm"
   (Surface calm but institutions hedging heavily)

📊 Credit Spread - "Credit Risk Indicator"
   Measured as HYG/LQD ratio (High Yield vs Investment Grade bonds).
   When ratio FALLS, spreads are WIDENING = risk aversion.
   Current 5-day change: {credit_str} {credit_warning}
   ----------------------------------------
   >+1%:    Spreads tightening (Risk appetite)
   -1% to +1%: Normal fluctuation
   <-1%:    Spreads widening (Risk aversion) ⚠️
   <-3%:    Significant widening (Credit stress)
   <-5%:    Severe (Potential credit crisis)

   What it means:
   • HYG = High Yield ("junk") corporate bonds
   • LQD = Investment Grade corporate bonds
   • When investors fear defaults, they sell HYG, buy LQD
   • Falling ratio = flight to quality = risk-off signal

📊 Stress Score - "Composite Stress Index"
   Combines VIX, credit spreads, correlations, momentum.
   Expressed as percentile (0-100) vs historical data.
   Current: {stress_score:.1f}/100 ({stress_level})
   ----------------------------------------
   0-25:    Low (Bottom 25% historically)
   25-50:   Normal (Below average stress)
   50-75:   Elevated (Above average stress)
   75-90:   High (Top 25% - significant stress)
   90-95:   Very High (Top 10% - major stress)
   >95:     Extreme (Top 5% - crisis levels)

   5-Day Acceleration: {accel_str}
   • Positive = stress increasing rapidly ⚠️
   • Negative = stress decreasing (relief)
   • >+10 in 5 days = rapid deterioration

📊 Shiller CAPE - "Long-term Valuation"
   Cyclically Adjusted P/E using 10-year avg earnings.
   Measures market valuation vs historical norms.
   ----------------------------------------
   <15:     LOW (Historically cheap, good entry)
   15-22:   NORMAL (Fair value range)
   22-28:   ELEVATED (Above average)
   28-35:   HIGH (Top 15% historically)
   >35:     EXTREME (Top 5%, 1929/2000 levels)

   Key insight: High CAPE → Lower expected 10Y returns
   Current implied return based on CAPE: 1/CAPE ≈ earnings yield

{'=' * 50}
⚙️  SYSTEM STATUS
{'=' * 50}

   Alert Threshold: {self.alert_threshold}%
   Alert Status:    {'🚨 TRIGGERED' if crash_probability >= self.alert_threshold else '✅ Normal'}

{'=' * 50}

⚠️  DISCLAIMER: This report is for informational purposes only.
It is not financial advice. Always consult qualified professionals.

Generated by Crash Probability Index Monitor
"""
        return message

    def _create_pdf_report(
        self,
        crash_probability: float,
        spy_price: float,
        qqq_price: float,
        vix_level: float,
        spy_change: float,
        qqq_change: float,
        risk_level: str,
        stress_score: float,
        stress_level: str,
        stress_acceleration: float,
        false_calm: bool,
        skew_level: float,
        credit_spread_change: float,
        recent_history: list,
        stock_risks: list,
        cfq_scores: list,
        etf_scores: list,
        cape_analysis,
        cycle_state,  # CycleState from cycle_detector
        crypto_scores: list,  # CryptoScore list from crypto_scorer
        crypto_trends: list,  # CryptoTrend list from crypto_trend
        stock_scan_results: list,  # StockScanResult list from stock_scanner
        futures_data,  # FuturesData from futures_fetcher
        date_str: str
    ) -> Optional[bytes]:
        """Create a professional PDF report"""
        if not PDF_AVAILABLE:
            print("⚠️  reportlab not installed. Run: pip install reportlab")
            return None

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        # Define colors
        DARK_BLUE = colors.HexColor('#1a365d')
        MEDIUM_BLUE = colors.HexColor('#2c5282')
        LIGHT_BLUE = colors.HexColor('#ebf8ff')
        GREEN = colors.HexColor('#276749')
        YELLOW = colors.HexColor('#c05621')
        RED = colors.HexColor('#c53030')
        GRAY = colors.HexColor('#718096')
        LIGHT_GRAY = colors.HexColor('#f7fafc')

        # Determine risk color
        if crash_probability >= 80:
            risk_color = RED
            risk_text = "EXTREME"
        elif crash_probability >= 60:
            risk_color = colors.HexColor('#dd6b20')
            risk_text = "HIGH"
        elif crash_probability >= 40:
            risk_color = YELLOW
            risk_text = "ELEVATED"
        elif crash_probability >= 20:
            risk_color = colors.HexColor('#38a169')
            risk_text = "MODERATE"
        else:
            risk_color = GREEN
            risk_text = "LOW"

        # Custom styles
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=DARK_BLUE,
            alignment=TA_CENTER,
            spaceAfter=6
        )

        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=GRAY,
            alignment=TA_CENTER,
            spaceAfter=20
        )

        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=DARK_BLUE,
            spaceBefore=15,
            spaceAfter=10,
            borderPadding=5
        )

        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            leading=14
        )

        small_style = ParagraphStyle(
            'Small',
            parent=styles['Normal'],
            fontSize=8,
            textColor=GRAY,
            leading=10
        )

        # Build document elements
        elements = []

        # Header
        elements.append(Paragraph("DAILY MARKET MONITOR REPORT", title_style))
        elements.append(Paragraph(f"Report Date: {date_str}", subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE, spaceAfter=15))

        # ========== CRASH PROBABILITY SECTION ==========
        elements.append(Paragraph("CRASH PROBABILITY INDEX", section_title_style))

        # Main probability display
        prob_data = [
            [Paragraph(f'<font size="36" color="#{risk_color.hexval()[2:]}">{crash_probability:.1f}%</font>',
                      ParagraphStyle('Big', alignment=TA_CENTER)),
             Paragraph(f'''<font size="12"><b>Risk Level:</b> {risk_text}</font><br/><br/>
                          <font size="10">Probability of ≥15% drawdown<br/>in next 20 trading days</font>''',
                      ParagraphStyle('Desc', alignment=TA_LEFT, leading=14))]
        ]

        prob_table = Table(prob_data, colWidths=[2.5*inch, 4.5*inch])
        prob_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
            ('BOX', (0, 0), (-1, -1), 1, MEDIUM_BLUE),
            ('PADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(prob_table)
        elements.append(Spacer(1, 15))

        # ========== MARKET SNAPSHOT ==========
        elements.append(Paragraph("MARKET SNAPSHOT", section_title_style))

        # VIX interpretation
        if vix_level < 12:
            vix_status = "Very Low"
            vix_color = YELLOW
        elif vix_level < 15:
            vix_status = "Low"
            vix_color = GREEN
        elif vix_level < 20:
            vix_status = "Normal"
            vix_color = GREEN
        elif vix_level < 25:
            vix_status = "Elevated"
            vix_color = YELLOW
        elif vix_level < 30:
            vix_status = "High"
            vix_color = YELLOW
        else:
            vix_status = "Very High"
            vix_color = RED

        # Format SPY/QQQ daily change
        spy_status = f'{spy_change:+.2f}%' if spy_change is not None else '—'
        qqq_status = f'{qqq_change:+.2f}%' if qqq_change is not None else '—'

        market_data = [
            ['Indicator', 'Value', 'Daily Change'],
            ['SPY', f'${spy_price:.2f}', spy_status],
            ['QQQ', f'${qqq_price:.2f}', qqq_status],
            ['VIX', f'{vix_level:.2f}', vix_status],
        ]

        market_table = Table(market_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
        market_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(market_table)
        elements.append(Spacer(1, 15))

        # ========== FUTURES PREMIUM/DISCOUNT ==========
        if futures_data is not None:
            elements.append(Paragraph("FUTURES PREMIUM/DISCOUNT", section_title_style))

            futures_rows = [['Index', 'Futures', 'Spot Equiv', 'Premium', 'Signal']]

            if futures_data.sp500:
                fp = futures_data.sp500
                spot_equiv = fp.spot_price * 10.0
                sign = "+" if fp.premium_pct > 0 else ""
                futures_rows.append([
                    'S&P 500 (ES)',
                    f'{fp.futures_price:,.2f}',
                    f'{spot_equiv:,.2f}',
                    f'{sign}{fp.premium_pct:.2f}%',
                    fp.signal
                ])

            if futures_data.nasdaq:
                fp = futures_data.nasdaq
                spot_equiv = fp.spot_price * 40.0
                sign = "+" if fp.premium_pct > 0 else ""
                futures_rows.append([
                    'Nasdaq-100 (NQ)',
                    f'{fp.futures_price:,.2f}',
                    f'{spot_equiv:,.2f}',
                    f'{sign}{fp.premium_pct:.2f}%',
                    fp.signal
                ])

            if len(futures_rows) > 1:
                futures_table = Table(futures_rows, colWidths=[1.4*inch, 1.3*inch, 1.3*inch, 1.2*inch, 1.2*inch])
                futures_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                    ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('PADDING', (0, 1), (-1, -1), 6),
                ]))
                elements.append(futures_table)

                # Add overall signal
                overall_color = {'BULLISH': GREEN, 'NEUTRAL': YELLOW, 'BEARISH': RED, 'UNKNOWN': GRAY}.get(futures_data.overall_signal, GRAY)
                overall_text = f"<b>Overall:</b> <font color='{overall_color}'>{futures_data.overall_signal}</font> - {futures_data.overall_interpretation}"
                elements.append(Spacer(1, 5))
                elements.append(Paragraph(overall_text, small_style))

            elements.append(Spacer(1, 15))

        # ========== CAPE VALUATION ==========
        if cape_analysis is not None:
            elements.append(Paragraph("SHILLER CAPE VALUATION", section_title_style))

            # CAPE level color
            cape_level_color = {
                'EXTREME': RED,
                'HIGH': colors.HexColor('#dd6b20'),
                'ELEVATED': YELLOW,
                'NORMAL': GREEN,
                'LOW': GREEN
            }.get(cape_analysis.cape_level, GRAY)

            # Premium to median
            premium_to_median = ((cape_analysis.current_cape / cape_analysis.historical_median) - 1) * 100

            cape_data = [
                ['Metric', 'Value', 'Reference'],
                ['Current CAPE', f'{cape_analysis.current_cape:.1f}', cape_analysis.cape_level],
                ['Historical Percentile', f'{cape_analysis.cape_percentile:.0f}%', 'vs 140+ years'],
                ['Premium to Median', f'{premium_to_median:+.0f}%', f'Median: {cape_analysis.historical_median:.1f}'],
                ['Implied 10Y Return', f'~{cape_analysis.implied_return_10y:.1f}% p.a.', 'Estimate only'],
            ]

            cape_table = Table(cape_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
            cape_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('PADDING', (0, 1), (-1, -1), 8),
                # Color the CAPE level cell
                ('TEXTCOLOR', (2, 1), (2, 1), cape_level_color),
                ('FONTNAME', (2, 1), (2, 1), 'Helvetica-Bold'),
            ]))
            elements.append(cape_table)
            elements.append(Spacer(1, 15))

        # ========== STRESS INDICATORS ==========
        if stress_score is not None:
            elements.append(Paragraph("STRESS INDICATORS", section_title_style))

            accel_str = f"{stress_acceleration:+.1f}" if stress_acceleration is not None else "N/A"
            skew_str = f"{skew_level:.1f}" if skew_level is not None else "N/A"
            credit_str = f"{credit_spread_change:+.2f}%" if credit_spread_change is not None else "N/A"

            # Stress score status
            if stress_score >= 90:
                stress_status = "Critical"
            elif stress_score >= 75:
                stress_status = "Elevated"
            elif stress_score >= 50:
                stress_status = "Moderate"
            else:
                stress_status = "Low"

            # SKEW status
            if skew_level is not None:
                if skew_level >= 145:
                    skew_status = "Very High"
                elif skew_level >= 135:
                    skew_status = "High"
                elif skew_level >= 125:
                    skew_status = "Elevated"
                else:
                    skew_status = "Normal"
            else:
                skew_status = "N/A"

            # Credit spread status
            if credit_spread_change is not None:
                if credit_spread_change < -3:
                    credit_status = "Severe"
                elif credit_spread_change < -1:
                    credit_status = "Widening"
                elif credit_spread_change > 1:
                    credit_status = "Tightening"
                else:
                    credit_status = "Normal"
            else:
                credit_status = "N/A"

            stress_data = [
                ['Indicator', 'Value', 'Status'],
                ['Stress Score', f'{stress_score:.1f}/100', stress_status],
                ['5-Day Acceleration', accel_str, 'Rising' if stress_acceleration and stress_acceleration > 0 else 'Falling' if stress_acceleration and stress_acceleration < 0 else '—'],
                ['SKEW Index', skew_str, skew_status],
                ['Credit Spread Δ (5d)', credit_str, credit_status],
            ]

            stress_table = Table(stress_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
            stress_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('PADDING', (0, 1), (-1, -1), 8),
            ]))
            elements.append(stress_table)
            elements.append(Spacer(1, 10))

            # False calm warning
            if false_calm:
                warning_style = ParagraphStyle(
                    'Warning',
                    parent=styles['Normal'],
                    fontSize=11,
                    textColor=RED,
                    backColor=colors.HexColor('#fff5f5'),
                    borderPadding=10,
                    leading=14
                )
                elements.append(Paragraph(
                    '<b>⚠ FALSE CALM DETECTED!</b><br/>'
                    'VIX appears calm but SKEW is elevated and credit spreads are widening. '
                    'This pattern often precedes volatility spikes.',
                    warning_style
                ))
            elements.append(Spacer(1, 15))

        # ========== MARKET CYCLE ANALYSIS ==========
        if cycle_state is not None:
            elements.append(Paragraph("MARKET CYCLE ANALYSIS", section_title_style))

            # Cycle regime colors
            regime_colors = {
                'risk_on': GREEN,
                'risk_off': RED,
                'neutral': YELLOW,
                'ease': GREEN,
                'tight': RED,
                'off': GRAY,
                'early': YELLOW,
                'broad': GREEN,
            }

            # Create cycle summary table
            cycle_data = [
                ['Cycle', 'Regime', 'Key Signal'],
                ['Risk', cycle_state.risk_regime.upper(),
                 cycle_state.risk_notes[0] if cycle_state.risk_notes else '-'],
                ['Rate', cycle_state.rate_regime.upper(),
                 cycle_state.rate_notes[0] if cycle_state.rate_notes else '-'],
                ['AI', cycle_state.ai_regime.upper(),
                 cycle_state.ai_notes[0] if cycle_state.ai_notes else '-'],
            ]

            cycle_table = Table(cycle_data, colWidths=[1.2*inch, 1.2*inch, 4.6*inch])
            cycle_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('PADDING', (0, 1), (-1, -1), 6),
            ]))

            # Color the regime cells
            for i, regime in enumerate([cycle_state.risk_regime, cycle_state.rate_regime, cycle_state.ai_regime], start=1):
                color = regime_colors.get(regime, GRAY)
                cycle_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, i), (1, i), color),
                    ('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'),
                ]))

            elements.append(cycle_table)
            elements.append(Spacer(1, 8))

            # Role Tilt Allocation Table
            elements.append(Paragraph("Portfolio Role Allocation Tilts", ParagraphStyle(
                'SubTitle', fontSize=10, textColor=DARK_BLUE, spaceAfter=5
            )))

            tilt_symbols = {
                'OW++': '++ (Strong OW)',
                'OW': '+ (Overweight)',
                'N': '= (Neutral)',
                'UW': '- (Underweight)',
                'UW--': '-- (Strong UW)'
            }

            tilt_data = [['Role', 'Tilt', 'Suggestion']]
            for role in ['CORE', 'AI', 'DEFENSE', 'INCOME', 'HEDGE']:
                tilt = cycle_state.role_tilts.get(role, 0)
                suggestion = cycle_state.role_suggestions.get(role, 'N')
                tilt_display = tilt_symbols.get(suggestion, suggestion)
                tilt_data.append([role, f'{tilt:+d}', tilt_display])

            tilt_table = Table(tilt_data, colWidths=[1.5*inch, 1*inch, 2.5*inch])
            tilt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('PADDING', (0, 1), (-1, -1), 4),
            ]))

            # Color tilt cells based on value
            for i, role in enumerate(['CORE', 'AI', 'DEFENSE', 'INCOME', 'HEDGE'], start=1):
                tilt = cycle_state.role_tilts.get(role, 0)
                if tilt >= 2:
                    color = GREEN
                elif tilt == 1:
                    color = colors.HexColor('#38a169')
                elif tilt == 0:
                    color = GRAY
                elif tilt == -1:
                    color = colors.HexColor('#dd6b20')
                else:
                    color = RED
                tilt_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, i), (2, i), color),
                    ('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'),
                ]))

            elements.append(tilt_table)
            elements.append(Spacer(1, 15))

        # ========== CRYPTO ENTRY SCORING ==========
        if crypto_scores and len(crypto_scores) > 0:
            elements.append(Paragraph("CRYPTO ENTRY SCORING (BTC/ETH)", section_title_style))

            # Explanation paragraph
            crypto_explanation = """
            <b>Scoring System (0-100):</b> Higher scores indicate better long-term entry timing, not price prediction.
            The system penalizes buying at highs and rewards buying during fear/undervaluation.
            <br/><br/>
            <b>Modules:</b> Valuation (40pts: MVRV + P/RP ratio) | Trend (20pts: 200wMA + Weekly RSI) |
            Sentiment (20pts: Fear&Greed + Narrative) | Macro (20pts: Rate Cycle + Risk Appetite)
            <br/><br/>
            <b>Action Guide:</b> >=80: Strong Buy (rare opportunity) | 65-79: Accumulate | 50-64: Normal DCA | <50: Wait
            """
            elements.append(Paragraph(crypto_explanation, ParagraphStyle(
                'CryptoExplain', fontSize=8, textColor=GRAY, spaceAfter=8, leading=11
            )))

            # Score colors
            score_colors = {
                'STRONG_BUY': GREEN,
                'ACCUMULATE': colors.HexColor('#38a169'),
                'DCA': YELLOW,
                'WAIT': GRAY
            }

            rec_text = {
                'STRONG_BUY': 'STRONG BUY',
                'ACCUMULATE': 'ACCUMULATE',
                'DCA': 'DCA',
                'WAIT': 'WAIT'
            }

            # Create crypto score table
            crypto_data = [['Asset', 'Price', 'Score', 'Action', 'MVRV', 'P/RP', 'RSI_w', 'F&G', 'Data Source']]

            for cs in crypto_scores:
                crypto_data.append([
                    cs.asset,
                    f'${cs.price:,.0f}' if cs.price else '-',
                    f'{cs.score:.0f}',
                    rec_text.get(cs.recommendation, cs.recommendation),
                    f'{cs.mvrv:.2f}' if cs.mvrv else '-',
                    f'{cs.ratio_rp:.2f}' if cs.ratio_rp else '-',
                    f'{cs.rsi_weekly:.0f}' if cs.rsi_weekly else '-',
                    str(cs.fear_greed) if cs.fear_greed is not None else '-',
                    {'api': 'API', 'estimated': 'Est.', 'manual': 'Manual', 'unavailable': 'N/A'}.get(cs.chain_data_source, '-')
                ])

            crypto_table = Table(crypto_data, colWidths=[0.6*inch, 0.9*inch, 0.6*inch, 1*inch, 0.6*inch, 0.6*inch, 0.5*inch, 0.5*inch, 0.8*inch])
            crypto_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f6ad55')),  # Orange header for crypto
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('PADDING', (0, 1), (-1, -1), 4),
            ]))

            # Color the score and action cells
            for i, cs in enumerate(crypto_scores, start=1):
                color = score_colors.get(cs.recommendation, GRAY)
                crypto_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (3, i), color),
                    ('FONTNAME', (2, i), (3, i), 'Helvetica-Bold'),
                ]))

            elements.append(crypto_table)

            # Add subscores detail for each crypto
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Subscore Breakdown", ParagraphStyle(
                'SubTitle', fontSize=9, textColor=DARK_BLUE, spaceAfter=4
            )))

            subscore_data = [['Asset', 'Valuation (40)', 'Trend (20)', 'Sentiment (20)', 'Macro (20)', 'Total', 'Signals']]
            for cs in crypto_scores:
                s = cs.subscores
                signals = ', '.join(cs.reason_tags[:3]) if cs.reason_tags else '-'  # Show top 3 signals
                subscore_data.append([
                    cs.asset,
                    f'{s.valuation_total:.0f}',
                    f'{s.trend_total:.0f}',
                    f'{s.sentiment_total:.0f}',
                    f'{s.macro_total:.0f}',
                    f'{cs.score_raw:.0f}',
                    signals
                ])

            subscore_table = Table(subscore_data, colWidths=[0.6*inch, 0.9*inch, 0.8*inch, 0.9*inch, 0.8*inch, 0.6*inch, 2.4*inch])
            subscore_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (6, 1), (6, -1), 'LEFT'),  # Signals left-aligned
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('TOPPADDING', (0, 0), (-1, 0), 5),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('PADDING', (0, 1), (-1, -1), 3),
            ]))

            elements.append(subscore_table)
            elements.append(Spacer(1, 15))

        # ========== CRYPTO TREND ANALYSIS ==========
        if crypto_trends and len(crypto_trends) > 0:
            elements.append(Paragraph("CRYPTO TREND ANALYSIS", section_title_style))

            # Explanation
            trend_explanation = """
            <b>趋势分析系统:</b> 多时间周期趋势识别 + 技术指标信号。
            Trend Score = Daily(20%) + Weekly(40%) + Monthly(40%) + Momentum
            <br/>
            <b>Score > +60:</b> STRONG_BULL | <b>+20~+60:</b> BULL | <b>-20~+20:</b> NEUTRAL |
            <b>-60~-20:</b> BEAR | <b>< -60:</b> STRONG_BEAR
            """
            elements.append(Paragraph(trend_explanation, ParagraphStyle(
                'TrendExplain', fontSize=8, textColor=GRAY, spaceAfter=8, leading=11
            )))

            # Create trend table
            trend_data = [['Asset', 'Price', '24h', '7d', '30d', 'Trend', 'Score', 'RSI', 'Confidence']]

            trend_colors = {
                'STRONG_BULL': GREEN,
                'BULL': colors.HexColor('#38a169'),
                'NEUTRAL': YELLOW,
                'BEAR': colors.HexColor('#e53e3e'),
                'STRONG_BEAR': RED
            }

            for t in crypto_trends:
                trend_data.append([
                    t.name,
                    f'${t.price:,.0f}',
                    f'{t.change_24h:+.1f}%',
                    f'{t.change_7d:+.1f}%',
                    f'{t.change_30d:+.1f}%',
                    t.overall_trend,
                    f'{t.trend_score:+d}',
                    f'{t.momentum.rsi_14:.0f}',
                    t.confidence
                ])

            trend_table = Table(trend_data, colWidths=[0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.6*inch, 1*inch, 0.6*inch, 0.5*inch, 0.8*inch])
            trend_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#805ad5')),  # Purple header for trends
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('PADDING', (0, 1), (-1, -1), 4),
            ]))

            # Color the trend cells
            for i, t in enumerate(crypto_trends, start=1):
                color = trend_colors.get(t.overall_trend, GRAY)
                trend_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (5, i), (6, i), color),
                    ('FONTNAME', (5, i), (6, i), 'Helvetica-Bold'),
                ]))

            elements.append(trend_table)

            # Add prediction for each crypto
            elements.append(Spacer(1, 8))
            for t in crypto_trends:
                arrow = {'STRONG_BULL': '⬆️⬆️', 'BULL': '⬆️', 'NEUTRAL': '➡️',
                         'BEAR': '⬇️', 'STRONG_BEAR': '⬇️⬇️'}.get(t.overall_trend, '➡️')
                pred_text = f"<b>{t.name}:</b> {arrow} {t.prediction}"
                elements.append(Paragraph(pred_text, small_style))

            elements.append(Spacer(1, 15))

        # ========== STOCK SCANNER RESULTS ==========
        if stock_scan_results and len(stock_scan_results) > 0:
            elements.append(Paragraph("STOCK SCANNER - TOP CANDIDATES", section_title_style))

            # Explanation - bilingual for clarity
            scanner_explanation = """
            <b>评分系统 Scoring (0-100):</b> 寻找具有生存优势的低估股票。生存过滤器先排除高风险股票，高分=更好的风险收益比。
            <br/><br/>
            <b>评分模块 Modules:</b><br/>
            • <b>生存 Survival (30分)</b>: 现金跑道、杠杆率、利息覆盖 - 确保公司不会"死掉"<br/>
            • <b>估值 Valuation (30分)</b>: PE百分位、自由现金流收益率 - 寻找便宜的好公司<br/>
            • <b>恐惧 Fear (20分)</b>: 52周跌幅、市场情绪 - 逆向投资，别人恐惧时贪婪<br/>
            • <b>结构 Structure (20分)</b>: 均线位置、RSI - 技术面支撑
            <br/><br/>
            <b>推荐等级 Action:</b><br/>
            • <font color="green"><b>STRONG_BUY (≥80)</b></font>: 强烈关注 - 风险收益比极佳，值得立即深入研究<br/>
            • <font color="#38a169"><b>RESEARCH (65-79)</b></font>: 值得研究 - 有潜力，需进一步分析基本面后再决定<br/>
            • <font color="#d69e2e"><b>WATCH (50-64)</b></font>: 观察名单 - 条件一般，等待更好的入场时机<br/>
            • <font color="gray"><b>AVOID (&lt;50)</b></font>: 暂时回避 - 风险收益比不佳或存在隐患
            """
            elements.append(Paragraph(scanner_explanation, ParagraphStyle(
                'ScannerExplain', fontSize=8, textColor=GRAY, spaceAfter=8, leading=11
            )))

            # Score colors
            scan_colors = {
                'STRONG_BUY': GREEN,
                'RESEARCH': colors.HexColor('#38a169'),
                'WATCH': YELLOW,
                'AVOID': GRAY
            }

            # Helper to get value from both object attributes and dict keys
            def get_val(item, key, default=None):
                if isinstance(item, dict):
                    return item.get(key, default)
                return getattr(item, key, default)

            # Recommendation display mapping (more descriptive)
            rec_display = {
                'STRONG_BUY': '强买',
                'RESEARCH': '研究',
                'WATCH': '观察',
                'AVOID': '回避'
            }

            # Create scanner results table with bilingual headers
            scan_data = [['代码', '名称', '得分', '建议', 'PE', 'FCF%', '杠杆', '跌幅', '行业']]

            for sr in stock_scan_results[:10]:  # Top 10
                name = get_val(sr, 'name', 'N/A')
                name = name[:15] if len(name) > 15 else name
                sector = get_val(sr, 'sector', 'N/A')
                sector = sector[:12] if len(sector) > 12 else sector
                pe = get_val(sr, 'pe_ratio')
                fcf = get_val(sr, 'fcf_yield')
                d2e = get_val(sr, 'debt_to_ebitda')
                dd = get_val(sr, 'drawdown_52w', 0)
                rec = get_val(sr, 'recommendation', 'N/A')
                scan_data.append([
                    get_val(sr, 'symbol'),
                    name,
                    f'{get_val(sr, "score", 0):.0f}',
                    rec_display.get(rec, rec[:6]),
                    f'{pe:.1f}' if pe else '-',
                    f'{fcf:.1f}%' if fcf else '-',
                    f'{d2e:.1f}x' if d2e else '-',
                    f'-{dd * 100:.0f}%' if dd else '-',
                    sector
                ])

            scan_table = Table(scan_data, colWidths=[0.6*inch, 1.1*inch, 0.5*inch, 0.7*inch, 0.5*inch, 0.5*inch, 0.6*inch, 0.5*inch, 0.9*inch])
            scan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),  # Dark header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('TOPPADDING', (0, 0), (-1, 0), 5),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('PADDING', (0, 1), (-1, -1), 3),
            ]))

            # Color the score and recommendation cells
            for i, sr in enumerate(stock_scan_results[:10], start=1):
                rec = get_val(sr, 'recommendation', 'WATCH')
                color = scan_colors.get(rec, GRAY)
                scan_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (3, i), color),
                    ('FONTNAME', (2, i), (3, i), 'Helvetica-Bold'),
                ]))
                # Highlight value trap warnings
                if get_val(sr, 'value_trap_warning', False):
                    scan_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fed7d7')),
                    ]))

            elements.append(scan_table)

            # Add column legend
            column_legend = """
            <b>列说明 Column Legend:</b> PE=市盈率(低好) | FCF%=自由现金流收益率(高好) | 杠杆=Debt/EBITDA(低好) | 跌幅=52周高点回撤(大=恐惧)
            <br/><font color="#c53030">粉色背景行 = 价值陷阱警告 (收入下降+利润恶化)</font>
            """
            elements.append(Paragraph(column_legend, ParagraphStyle(
                'Legend', fontSize=7, textColor=GRAY, spaceBefore=4, leading=10
            )))

            # Add top 3 signal breakdown
            if len(stock_scan_results) >= 1:
                elements.append(Spacer(1, 8))
                elements.append(Paragraph("前三名信号解读 Top 3 Signal Breakdown", ParagraphStyle(
                    'SubTitle', fontSize=9, textColor=DARK_BLUE, spaceAfter=4
                )))

                signals_text = ""
                for sr in stock_scan_results[:3]:
                    reason_tags = get_val(sr, 'reason_tags', [])
                    tags = ', '.join(reason_tags[:4]) if reason_tags else '无特殊信号'
                    trap_warn = " <font color='red'>[价值陷阱警告]</font>" if get_val(sr, 'value_trap_warning', False) else ""
                    score = get_val(sr, 'score', 0)
                    rec = get_val(sr, 'recommendation', 'N/A')
                    signals_text += f"<b>{get_val(sr, 'symbol', 'N/A')}</b> ({score:.0f}分): {tags}{trap_warn}<br/>"

                elements.append(Paragraph(signals_text, ParagraphStyle(
                    'Signals', fontSize=7, textColor=GRAY, leading=10
                )))

            elements.append(Spacer(1, 15))

        # ========== INDIVIDUAL STOCK RISKS ==========
        if stock_risks and len(stock_risks) > 0:
            elements.append(Paragraph("INDIVIDUAL STOCK RISK ASSESSMENT", section_title_style))

            stock_data = [['Stock', 'Price', 'Risk', 'Level', 'Beta', '5D Change']]
            for risk in stock_risks:
                level_color = {
                    'HIGH': RED,
                    'MODERATE': YELLOW,
                    'NORMAL': GREEN,
                    'LOW': GREEN
                }.get(risk.risk_level, GRAY)

                stock_data.append([
                    f'{risk.name}\n({risk.symbol})',
                    f'${risk.price:.2f}',
                    f'{risk.crash_probability:.1f}%',
                    risk.risk_level,
                    f'{risk.beta:.2f}',
                    f'{risk.change_5d:+.1f}%'
                ])

            stock_table = Table(stock_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 1*inch])
            stock_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('PADDING', (0, 1), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            # Color code risk levels
            for i, risk in enumerate(stock_risks, start=1):
                level_color = {
                    'HIGH': RED,
                    'MODERATE': YELLOW,
                    'NORMAL': GREEN,
                    'LOW': GREEN
                }.get(risk.risk_level, GRAY)
                stock_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, i), (3, i), level_color),
                    ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'),
                ]))

            elements.append(stock_table)
            elements.append(Spacer(1, 15))

            # High risk warnings
            high_risk_stocks = [r for r in stock_risks if r.risk_level == 'HIGH']
            if high_risk_stocks:
                warning_text = '<b>HIGH RISK STOCKS:</b><br/>'
                for r in high_risk_stocks:
                    warning_text += f'• {r.name} ({r.symbol}): {r.crash_probability:.1f}% - Beta: {r.beta:.2f}, Vol: {r.volatility_30d:.1f}%<br/>'
                elements.append(Paragraph(warning_text, ParagraphStyle(
                    'Warning', fontSize=9, textColor=RED, leading=12
                )))
                elements.append(Spacer(1, 10))

        # ========== CFQ VALUATION ==========
        if cfq_scores and len(cfq_scores) > 0:
            elements.append(Paragraph("CFQ VALUATION (Cashflow × Quality × Price)", section_title_style))

            cfq_data = [['Stock', 'Price', 'FCF', 'Quality', 'Price', 'Total', 'Action']]
            for s in cfq_scores:
                cfq_data.append([
                    f'{s.name}\n({s.symbol})',
                    f'${s.price:.2f}',
                    f'{s.fcf_score}/5',
                    f'{s.quality_score}/5',
                    f'{s.price_score}/5',
                    f'{s.total_score}/15',
                    s.recommendation
                ])

            cfq_table = Table(cfq_data, colWidths=[1.4*inch, 0.9*inch, 0.7*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.9*inch])
            cfq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('PADDING', (0, 1), (-1, -1), 5),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            # Color code recommendations
            for i, s in enumerate(cfq_scores, start=1):
                rec_color = {
                    'BUY': GREEN,
                    'WATCH': YELLOW,
                    'AVOID': RED,
                    'SKIP': GRAY
                }.get(s.recommendation, GRAY)
                cfq_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (6, i), (6, i), rec_color),
                    ('FONTNAME', (6, i), (6, i), 'Helvetica-Bold'),
                ]))

            elements.append(cfq_table)
            elements.append(Spacer(1, 10))

            # Buy recommendations highlight
            buy_stocks = [s for s in cfq_scores if s.recommendation == 'BUY']
            if buy_stocks:
                buy_text = '<b>TOP PICKS (Score ≥ 12):</b><br/>'
                for s in buy_stocks:
                    if s.ev_to_fcf:
                        buy_text += f'• {s.name}: {s.total_score}/15 - FCF Yield: {s.fcf_yield*100:.1f}%, EV/FCF: {s.ev_to_fcf:.1f}x<br/>'
                    else:
                        buy_text += f'• {s.name}: {s.total_score}/15 - FCF Yield: {s.fcf_yield*100:.1f}%<br/>'
                elements.append(Paragraph(buy_text, ParagraphStyle(
                    'BuyTip', fontSize=9, textColor=GREEN, leading=12
                )))
                elements.append(Spacer(1, 10))

        # ========== ETF-4Q EVALUATION ==========
        if etf_scores and len(etf_scores) > 0:
            elements.append(Paragraph("ETF-4Q EVALUATION (Macro × Quality × Valuation × Structure)", section_title_style))

            # Main scoring table with Role Tag
            # Grade: A+ (>=12), A (9-11), B (6-8), C (<6)
            etf_data = [['ETF', 'Role', 'ER%', 'M', 'Q', 'V', 'S', 'Total', 'Grade']]
            for s in etf_scores:
                # Get role tag, default to SATELLITE if not set
                role_tag = getattr(s, 'role_tag', 'SATELLITE') or 'SATELLITE'
                # Shorten role tag for display
                role_display = role_tag.replace('HEDGE-', 'H-').replace('AI-', 'AI-').replace('CORE-', 'C-')

                # Get expense ratio
                er_display = f'{s.expense_ratio:.2f}' if s.expense_ratio else '-'

                etf_data.append([
                    f'{s.symbol}\n({s.name[:10]})',
                    role_display,
                    er_display,
                    str(s.macro_score),
                    str(s.quality_score),
                    str(s.valuation_score),
                    str(s.structure_score),
                    f'{s.total_score}/15',
                    s.recommendation  # Now A+/A/B/C
                ])

            etf_table = Table(etf_data, colWidths=[0.9*inch, 0.7*inch, 0.4*inch, 0.3*inch, 0.3*inch, 0.3*inch, 0.3*inch, 0.55*inch, 0.55*inch])
            etf_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('PADDING', (0, 1), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            # Color code grades and role tags
            role_colors = {
                'CORE': colors.HexColor('#1a365d'),      # Dark blue
                'HEDGE': colors.HexColor('#276749'),     # Green
                'H-CASH': colors.HexColor('#276749'),
                'H-DURATION': colors.HexColor('#276749'),
                'H-INFL': colors.HexColor('#276749'),
                'INCOME': colors.HexColor('#744210'),    # Brown/Orange
                'AI-COMPUTE': colors.HexColor('#6b21a8'), # Purple
                'AI-SOFTWARE': colors.HexColor('#6b21a8'),
                'AI-POWER': colors.HexColor('#6b21a8'),
                'AI-DATA': colors.HexColor('#6b21a8'),
                'DEFENSE': colors.HexColor('#7c2d12'),   # Dark red
                'C-INTL': colors.HexColor('#1a365d'),
                'SATELLITE': colors.HexColor('#4a5568'), # Gray
            }

            for i, s in enumerate(etf_scores, start=1):
                # Grade colors: A+ green, A yellow-green, B orange, C gray
                grade_color = {
                    'A+': GREEN,
                    'A': colors.HexColor('#38a169'),  # Lighter green
                    'B': YELLOW,
                    'C': GRAY
                }.get(s.recommendation, GRAY)
                etf_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (8, i), (8, i), grade_color),
                    ('FONTNAME', (8, i), (8, i), 'Helvetica-Bold'),
                ]))
                # Color role tag column
                role_tag = getattr(s, 'role_tag', 'SATELLITE') or 'SATELLITE'
                role_display = role_tag.replace('HEDGE-', 'H-').replace('CORE-', 'C-')
                role_color = role_colors.get(role_display, role_colors.get(role_tag.split('-')[0], GRAY))
                etf_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, i), (1, i), role_color),
                    ('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'),
                ]))

            elements.append(etf_table)
            elements.append(Spacer(1, 8))

            # Role Tag Legend (English only to avoid font issues)
            legend_style = ParagraphStyle('Legend', fontSize=7, textColor=GRAY, leading=9)
            legend_text = '<b>Role Tags:</b> CORE=Core Holdings | HEDGE=Hedging(CASH/DURATION/INFL) | INCOME=Cash Flow | AI=AI Chain(COMPUTE/SOFTWARE/POWER/DATA) | DEFENSE=Aerospace&amp;Defense | SATELLITE=Satellite'
            elements.append(Paragraph(legend_text, legend_style))
            elements.append(Spacer(1, 8))

            # ETF Description section - grouped by role
            # Use Chinese font if available, otherwise skip Chinese descriptions
            if CHINESE_FONT_AVAILABLE:
                desc_style = ParagraphStyle('ETFDesc', fontSize=7, fontName=CHINESE_FONT_NAME,
                                           textColor=colors.HexColor('#2d3748'), leading=10)
            else:
                desc_style = ParagraphStyle('ETFDesc', fontSize=7,
                                           textColor=colors.HexColor('#2d3748'), leading=9)

            # Group ETFs by role for description
            role_groups = {}
            for s in etf_scores:
                role = getattr(s, 'role_tag', 'SATELLITE') or 'SATELLITE'
                base_role = role.split('-')[0] if '-' in role else role
                if base_role not in role_groups:
                    role_groups[base_role] = []
                role_groups[base_role].append(s)

            # Role display order and names (English for compatibility)
            role_order = ['CORE', 'HEDGE', 'INCOME', 'AI', 'DEFENSE', 'SATELLITE']
            role_names = {
                'CORE': 'CORE - Core Holdings',
                'HEDGE': 'HEDGE - Hedging Tools',
                'INCOME': 'INCOME - Cash Flow',
                'AI': 'AI - AI Infrastructure',
                'DEFENSE': 'DEFENSE - Aerospace &amp; Defense',
                'SATELLITE': 'SATELLITE - Thematic/Satellite'
            }

            desc_lines = []
            for role in role_order:
                if role in role_groups and role_groups[role]:
                    desc_lines.append(f'<b>{role_names.get(role, role)}</b>')
                    for s in role_groups[role]:
                        desc = getattr(s, 'description', '') or ''
                        er = s.expense_ratio if s.expense_ratio else 0
                        # Only include Chinese description if font is available
                        if desc and CHINESE_FONT_AVAILABLE:
                            desc_lines.append(f'  - <b>{s.symbol}</b> ({s.name}) [ER:{er:.2f}%]: {desc}')
                        else:
                            desc_lines.append(f'  - <b>{s.symbol}</b> ({s.name}) [ER:{er:.2f}%]')

            if desc_lines:
                elements.append(Paragraph('<br/>'.join(desc_lines), desc_style))
                elements.append(Spacer(1, 10))

            # Top ETF picks summary (Grade A+)
            top_etfs = [s for s in etf_scores if s.recommendation == 'A+']
            if top_etfs:
                top_text = '<b>TOP PICKS (Grade A+, Score >= 12):</b><br/>'
                for s in top_etfs:
                    role_tag = getattr(s, 'role_tag', '') or ''
                    top_text += f'• {s.symbol} [{role_tag}]: {s.total_score}/15<br/>'
                elements.append(Paragraph(top_text, ParagraphStyle(
                    'TopTip', fontSize=8, textColor=GREEN, leading=11
                )))
                elements.append(Spacer(1, 10))

        # ========== RECENT HISTORY ==========
        if recent_history and len(recent_history) > 0:
            elements.append(Paragraph("RECENT HISTORY (Last 5 Days)", section_title_style))

            history_data = [['Date', 'Crash Probability', 'Trend']]
            for hist_date, hist_prob in recent_history[-5:]:
                trend = "↑ Rising" if hist_prob > 50 else "↓ Falling" if hist_prob < 30 else "→ Stable"
                history_data.append([hist_date, f'{hist_prob:.1f}%', trend])

            history_table = Table(history_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
            history_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), MEDIUM_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('PADDING', (0, 1), (-1, -1), 8),
            ]))
            elements.append(history_table)
            elements.append(Spacer(1, 15))

        # ========== REFERENCE GUIDES ==========
        elements.append(Paragraph("INDICATOR REFERENCE GUIDE", section_title_style))

        # VIX Reference
        elements.append(Paragraph("<b>VIX (Volatility Index)</b> - Measures expected 30-day S&P 500 volatility", body_style))
        vix_ref_data = [
            ['Range', 'Level', 'Interpretation'],
            ['< 12', 'Very Low', 'Market complacent, potential reversal'],
            ['12 - 15', 'Low', 'Calm markets'],
            ['15 - 20', 'Normal', 'Typical conditions'],
            ['20 - 25', 'Elevated', 'Increased uncertainty'],
            ['25 - 30', 'High', 'Significant fear'],
            ['> 30', 'Very High', 'Market stress/panic'],
        ]
        vix_table = Table(vix_ref_data, colWidths=[1.5*inch, 1.5*inch, 4*inch])
        vix_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(vix_table)
        elements.append(Spacer(1, 10))

        # SKEW Reference
        elements.append(Paragraph("<b>SKEW Index</b> - Measures demand for out-of-money put options (tail risk)", body_style))
        skew_ref_data = [
            ['Range', 'Level', 'Interpretation'],
            ['< 115', 'Low', 'Balanced sentiment'],
            ['115 - 125', 'Normal', 'Typical hedging'],
            ['125 - 135', 'Elevated', 'Above-average hedging'],
            ['135 - 145', 'High', 'Smart money buying protection'],
            ['> 145', 'Very High', 'Heavy tail hedging'],
        ]
        skew_table = Table(skew_ref_data, colWidths=[1.5*inch, 1.5*inch, 4*inch])
        skew_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(skew_table)
        elements.append(Spacer(1, 10))

        # Credit Spread Reference
        elements.append(Paragraph("<b>Credit Spread</b> - HYG/LQD ratio change (High Yield vs Investment Grade bonds)", body_style))
        credit_ref_data = [
            ['5-Day Change', 'Interpretation'],
            ['> +1%', 'Spreads tightening (Risk appetite)'],
            ['-1% to +1%', 'Normal fluctuation'],
            ['< -1%', 'Spreads widening (Risk aversion)'],
            ['< -3%', 'Significant widening (Credit stress)'],
        ]
        credit_table = Table(credit_ref_data, colWidths=[2*inch, 5*inch])
        credit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(credit_table)
        elements.append(Spacer(1, 10))

        # Stress Score Reference
        elements.append(Paragraph("<b>Stress Score</b> - Composite index combining VIX, credit spreads, correlations, momentum (percentile)", body_style))
        stress_ref_data = [
            ['Range', 'Level', 'Interpretation'],
            ['0 - 25', 'Low', 'Bottom 25% historically'],
            ['25 - 50', 'Normal', 'Below average stress'],
            ['50 - 75', 'Elevated', 'Above average stress'],
            ['75 - 90', 'High', 'Top 25% - significant stress'],
            ['> 90', 'Critical', 'Top 10% - crisis levels'],
        ]
        stress_ref_table = Table(stress_ref_data, colWidths=[1.5*inch, 1.5*inch, 4*inch])
        stress_ref_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(stress_ref_table)
        elements.append(Spacer(1, 10))

        # Crash Probability Reference
        elements.append(Paragraph("<b>Crash Probability</b> - Model prediction of ≥15% drawdown in 20 days", body_style))
        prob_ref_data = [
            ['Range', 'Risk Level', 'Recommended Action'],
            ['0 - 20%', 'Low', 'Normal market conditions'],
            ['20 - 40%', 'Moderate', 'Monitor positions'],
            ['40 - 60%', 'Elevated', 'Consider reducing exposure'],
            ['60 - 80%', 'High', 'Significant de-risking recommended'],
            ['80 - 100%', 'Extreme', 'Maximum caution (2008/2020 levels)'],
        ]
        prob_ref_table = Table(prob_ref_data, colWidths=[1.5*inch, 1.5*inch, 4*inch])
        prob_ref_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(prob_ref_table)
        elements.append(Spacer(1, 10))

        # CAPE Reference
        elements.append(Paragraph("<b>Shiller CAPE</b> - Cyclically Adjusted Price-to-Earnings ratio (10-year smoothed)", body_style))
        cape_ref_data = [
            ['Range', 'Level', 'Interpretation'],
            ['< 15', 'Low', 'Below average - historically attractive'],
            ['15 - 22', 'Normal', 'Around historical average (~17.6)'],
            ['22 - 28', 'Elevated', 'Above average valuations'],
            ['28 - 35', 'High', 'Top 15% historically'],
            ['> 35', 'Extreme', 'Top 5% - similar to 1929, 2000 peaks'],
        ]
        cape_ref_table = Table(cape_ref_data, colWidths=[1.5*inch, 1.5*inch, 4*inch])
        cape_ref_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRAY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(cape_ref_table)
        elements.append(Spacer(1, 20))

        # ========== FOOTER ==========
        elements.append(HRFlowable(width="100%", thickness=1, color=GRAY, spaceBefore=10))

        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=GRAY,
            alignment=TA_CENTER,
            leading=10
        )
        elements.append(Paragraph(
            '<b>DISCLAIMER:</b> This report is for informational purposes only. '
            'It is not financial advice. Always consult qualified professionals before making investment decisions.',
            disclaimer_style
        ))
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(
            f'Generated by Crash Probability Index Monitor | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            disclaimer_style
        ))

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def send_sms_alert(self, message: str) -> bool:
        """
        Send SMS alert via Twilio

        Args:
            message: SMS message (keep under 160 chars for single message)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.twilio_account_sid or not self.twilio_auth_token:
            print("⚠️  SMS not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN")
            return False

        try:
            from twilio.rest import Client

            client = Client(self.twilio_account_sid, self.twilio_auth_token)

            # Send SMS
            sms = client.messages.create(
                body=message,
                from_=self.twilio_from,
                to=self.twilio_to
            )

            print(f"✓ SMS alert sent to {self.twilio_to} (SID: {sms.sid})")
            return True

        except ImportError:
            print("✗ Twilio not installed. Run: pip install twilio")
            return False
        except Exception as e:
            print(f"✗ Failed to send SMS: {e}")
            return False


if __name__ == "__main__":
    # Test alerter
    print("Testing Crash Alerter...")
    print("=" * 60)

    # Create alerter
    alerter = CrashAlerter(
        alert_threshold=60.0,
        enable_email=True,
        enable_sms=False
    )

    print(f"Alert threshold: {alerter.alert_threshold}%")
    print(f"Email enabled: {alerter.enable_email}")
    print(f"SMS enabled: {alerter.enable_sms}")
    print()

    # Test scenarios
    scenarios = [
        (30.5, "Normal conditions", False),
        (65.2, "High risk", True),
        (85.7, "Extreme risk", True),
    ]

    for prob, description, should_alert in scenarios:
        print(f"\nScenario: {description}")
        print(f"Crash probability: {prob:.1f}%")

        if prob >= alerter.alert_threshold:
            print(f"✓ Would trigger alert (>= {alerter.alert_threshold}%)")

            # Show what the alert would look like
            if should_alert:
                message = alerter._create_alert_message(
                    crash_probability=prob,
                    spy_price=450.25,
                    qqq_price=385.50,
                    vix_level=32.5,
                    risk_level="HIGH" if prob < 80 else "EXTREME",
                    urgency="HIGH" if prob >= 80 else "MODERATE",
                    date_str="2024-01-15"
                )
                print("\nAlert message preview:")
                print("-" * 60)
                print(message[:500] + "...")
        else:
            print(f"✗ Below threshold (< {alerter.alert_threshold}%)")

    print("\n" + "=" * 60)
    print("To enable alerts, set environment variables:")
    print("  export EMAIL_FROM='your-email@gmail.com'")
    print("  export EMAIL_PASSWORD='your-app-password'")
    print("  export EMAIL_TO='recipient@email.com'")
    print("\nFor SMS (optional):")
    print("  pip install twilio")
    print("  export TWILIO_ACCOUNT_SID='your-sid'")
    print("  export TWILIO_AUTH_TOKEN='your-token'")
    print("  export TWILIO_FROM='+1234567890'")
    print("  export TWILIO_TO='+0987654321'")
