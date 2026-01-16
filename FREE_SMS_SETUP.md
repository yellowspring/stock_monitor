# FREE SMS Alerts via Email-to-SMS Gateway

## What is Email-to-SMS Gateway?

Most phone carriers let you send SMS messages **for FREE** by sending email to a special address!

**Example:**
- Your phone: (555) 123-4567
- AT&T email-to-SMS: `5551234567@txt.att.net`
- Send email there → Arrives as SMS on your phone!

---

## Step 1: Find Your Carrier's Gateway

### Major US Carriers:

| Carrier | Email-to-SMS Address | Format |
|---------|---------------------|--------|
| **AT&T** | `[phone]@txt.att.net` | Remove dashes/spaces |
| **T-Mobile** | `[phone]@tmomail.net` | 10 digits only |
| **Verizon** | `[phone]@vtext.com` | 10 digits only |
| **Sprint** | `[phone]@messaging.sprintpcs.com` | 10 digits only |
| **US Cellular** | `[phone]@email.uscc.net` | 10 digits only |
| **Boost Mobile** | `[phone]@sms.myboostmobile.com` | 10 digits only |
| **Cricket** | `[phone]@mms.cricketwireless.net` | 10 digits only |
| **Google Fi** | `[phone]@msg.fi.google.com` | 10 digits only |

### International Carriers:

**Check:** https://en.wikipedia.org/wiki/SMS_gateway for your carrier

---

## Step 2: Get Your Phone Number in Correct Format

**Example:**
- Your phone: **(555) 123-4567**
- Remove all formatting: **5551234567**
- Add carrier domain: **5551234567@txt.att.net**

---

## Step 3: Update Your .env File

```bash
# Edit .env
nano .env

# Update EMAIL_TO to include your SMS gateway:
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com,YOUR-NUMBER@txt.att.net
```

**Example (if your AT&T number is 555-123-4567):**
```
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com,5551234567@txt.att.net
```

**That's it!** No code changes needed.

---

## Step 4: Test It

```bash
# Load environment
source .env

# Test the alert (will send to all 3 addresses)
python monitor_with_alerts.py --threshold 60 --email
```

You should receive:
1. ✅ Email to tao.zhang.1977@gmail.com
2. ✅ Email to gao.yuan.77@gmail.com
3. ✅ **SMS to your phone!**

---

## SMS Message Preview

The SMS will be shortened to fit 160 characters:

```
🚨 CRASH ALERT: 75.5% Risk - EXTREME
Date: 2024-01-15
SPY: $450.25
QQQ: $385.50
VIX: 32.50
Risk: EXTREME - Reduce exposure immediately
```

---

## Troubleshooting

### SMS Not Arriving?

**1. Verify carrier gateway address**
- AT&T: `@txt.att.net` (NOT `@mms.att.net`)
- Make sure you're using the right domain

**2. Check carrier settings**
- Some carriers block email-to-SMS by default
- Log into your carrier account
- Enable "email to text" or "text messaging from email"

**3. Check spam/blocked messages**
- SMS might be filtered
- Add Gmail to your contacts

**4. Test manually**
- Send test email from Gmail to `YOUR-NUMBER@txt.att.net`
- If that doesn't work, contact carrier support

### Message Too Long?

Email-to-SMS has limits (usually 160 chars). The system will send the full message, but it may arrive as multiple texts.

**Solution:** Use regular email for full details, SMS for quick alerts.

---

## Comparison: Email-to-SMS vs. Twilio

| Feature | Email-to-SMS | Twilio SMS |
|---------|-------------|------------|
| **Cost** | ✅ FREE | ❌ ~$1.30/month |
| **Setup** | ✅ 1 minute | ⚠️ 10 minutes |
| **Reliability** | ⚠️ 95-99% | ✅ 99.9% |
| **Message length** | ⚠️ 160 chars | ✅ 1600 chars |
| **Delivery speed** | ⚠️ 1-5 minutes | ✅ Instant |
| **Works for you?** | ✅ YES! | ⚠️ Overkill |

**Verdict:** Email-to-SMS is **perfect** for your use case! 🎯

---

## Complete Setup Example

**If your phone is 555-123-4567 on AT&T:**

```bash
# 1. Edit .env
nano .env

# 2. Set EMAIL_TO to:
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com,5551234567@txt.att.net

# 3. Save and load
source .env

# 4. Test
python monitor_with_alerts.py --threshold 60 --email
```

**Done! FREE SMS alerts!** 📱✅

---

## Advanced: Multiple Phone Numbers

Want SMS to multiple phones?

```bash
# Add all SMS gateways (comma-separated)
EMAIL_TO=tao.zhang.1977@gmail.com,gao.yuan.77@gmail.com,5551111111@txt.att.net,5552222222@vtext.com

# Now alerts go to:
# - 2 email addresses
# - 2 phone numbers (SMS)
# All FREE!
```

---

## Summary

✅ **100% FREE** SMS via email-to-SMS gateway
✅ **No signup** or account needed
✅ **No monthly fees**
✅ **Works with existing system**
✅ **Just add one line** to .env file

**vs.**

❌ Twilio: $1-2/month, requires signup, overkill for this

**Winner:** Email-to-SMS Gateway! 🏆
