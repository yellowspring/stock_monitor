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
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


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
        stress_score: float = None,
        stress_acceleration: float = None,
        false_calm: bool = False,
        skew_level: float = None,
        credit_spread_change: float = None,
        recent_history: list = None,
        stock_risks: list = None,
        date: Optional[str] = None
    ) -> bool:
        """
        Send daily market report email (regardless of alert threshold)

        Args:
            crash_probability: Current crash probability (0-100)
            spy_price: Current SPY price
            qqq_price: Current QQQ price
            vix_level: Current VIX level
            stress_score: Current stress composite score (0-100)
            stress_acceleration: 5-day stress acceleration
            false_calm: Whether false calm detector is triggered
            skew_level: Current SKEW index level
            credit_spread_change: 5-day credit spread change %
            recent_history: List of recent probabilities [(date, prob), ...]
            stock_risks: List of StockRisk objects for individual stocks
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
            risk_level=risk_level,
            stress_score=stress_score,
            stress_level=stress_level,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
            date_str=date_str
        )

        # Generate PDF report
        pdf_bytes = self._create_pdf_report(
            crash_probability=crash_probability,
            spy_price=spy_price,
            qqq_price=qqq_price,
            vix_level=vix_level,
            risk_level=risk_level,
            stress_score=stress_score,
            stress_level=stress_level,
            stress_acceleration=stress_acceleration,
            false_calm=false_calm,
            skew_level=skew_level,
            credit_spread_change=credit_spread_change,
            recent_history=recent_history,
            stock_risks=stock_risks,
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
        risk_level: str,
        stress_score: float,
        stress_level: str,
        stress_acceleration: float,
        false_calm: bool,
        skew_level: float,
        credit_spread_change: float,
        recent_history: list,
        stock_risks: list,
        date_str: str
    ) -> str:
        """Create formatted daily report message"""

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
{stress_section}
{false_calm_warning}
{stock_section}
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
        risk_level: str,
        stress_score: float,
        stress_level: str,
        stress_acceleration: float,
        false_calm: bool,
        skew_level: float,
        credit_spread_change: float,
        recent_history: list,
        stock_risks: list,
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

        market_data = [
            ['Indicator', 'Value', 'Status'],
            ['SPY', f'${spy_price:.2f}', '—'],
            ['QQQ', f'${qqq_price:.2f}', '—'],
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
