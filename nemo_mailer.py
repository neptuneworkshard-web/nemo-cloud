import os, smtplib, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.env')

def load_creds():
    d = {}
    try:
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    d[k.strip()] = v.strip()
    except: pass
    return d

def send_signal_email(signals, subject=None):
    creds = load_creds()
    gmail_user = creds.get('GMAIL_USER', 'neptune.works.hard@gmail.com')
    gmail_app_pw = creds.get('GMAIL_APP_PASSWORD', '')
    to_email = creds.get('EMAIL_TO', gmail_user)

    if not gmail_app_pw:
        print('[mailer] No GMAIL_APP_PASSWORD in credentials.env')
        return False

    ts = datetime.now().strftime('%I:%M %p')
    date_str = datetime.now().strftime('%A, %d %B %Y')
    if not subject:
        subject = f'Nemo Market Signals — {date_str}'

    html = build_html(signals, date_str, ts)
    msg = MIMEMultipart('alternative')
    msg['From'] = gmail_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_app_pw)
        server.sendmail(gmail_user, [to_email], msg.as_string())
        server.quit()
        print(f'[mailer] Email sent to {to_email}')
        return True
    except Exception as e:
        print(f'[mailer] Failed: {e}')
        return False

SENTIMENT_ICONS = {'positive': '🟢', 'negative': '🔴', 'neutral': '⚪'}

def render_news(news_items):
    if not news_items:
        return ''
    items_html = ''
    for item in news_items[:3]:
        sent = item.get('sentiment', 'neutral')
        icon = SENTIMENT_ICONS.get(sent, '⚪')
        title = item.get('title', '')
        items_html += f'<div style="font-size:12px;color:#8892b0;padding:4px 0;">{icon} {title}</div>'
    return f'''
    <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.06);">
        <div style="font-size:11px;color:#495670;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">📰 Latest News · Moneycontrol</div>
        {items_html}
    </div>'''

def render_sr(sr):
    if not sr: return ''
    return f'''
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-top:8px;">
        <div style="font-size:10px;color:#ff4757;">
            <div style="color:#495670;text-transform:uppercase;margin-bottom:2px;">Resistance</div>
            <div>R3: ₹{sr["r3"]:.1f}</div>
            <div>R2: ₹{sr["r2"]:.1f}</div>
            <div>R1: ₹{sr["r1"]:.1f}</div>
        </div>
        <div style="font-size:10px;color:#00c896;text-align:right;">
            <div style="color:#495670;text-transform:uppercase;margin-bottom:2px;">Support</div>
            <div>S1: ₹{sr["s1"]:.1f}</div>
            <div>S2: ₹{sr["s2"]:.1f}</div>
            <div>S3: ₹{sr["s3"]:.1f}</div>
        </div>
    </div>'''

def build_html(signals, date_str, ts):
    cards = ''
    for i, s in enumerate(signals[:30]):
        dir_emoji = '🔵' if s.get('direction') == 'LONG' else '🔴'
        dir_color = '#00c896' if s.get('direction') == 'LONG' else '#ff4757'
        bg = 'rgba(0,200,150,0.08)' if s.get('direction') == 'LONG' else 'rgba(255,71,87,0.08)'
        border = '2px solid rgba(0,200,150,0.3)' if s.get('direction') == 'LONG' else '2px solid rgba(255,71,87,0.3)'
        factors = ', '.join(s.get('factors', [])[:5])
        entry = s.get('entry', 0)
        stop = s.get('stop', 0)
        target = s.get('target', 0)
        score = s.get('score', 0)
        conf = s.get('conf', 0)
        rr = s.get('rr', 0)

        cards += f'''
        <div class="card" style="background:{bg};border:{border};border-radius:12px;padding:16px;margin-bottom:12px;">
            <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:18px;font-weight:700;color:{dir_color};">{dir_emoji} {s.get('symbol','')} — {s.get('direction','')}</span>
                <span class="badge" style="background:{dir_color};color:#fff;border-radius:20px;padding:4px 12px;font-size:13px;font-weight:600;">Score {score} · Conf {conf}%</span>
            </div>
            <div class="prices" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:8px;">
                <div class="price-box" style="background:rgba(255,255,255,0.06);border-radius:8px;padding:8px;text-align:center;">
                    <div style="font-size:11px;color:#8892b0;text-transform:uppercase;letter-spacing:0.5px;">Entry</div>
                    <div style="font-size:17px;font-weight:700;color:#ccd6f6;">₹{entry:.1f}</div>
                </div>
                <div class="price-box" style="background:rgba(255,255,255,0.06);border-radius:8px;padding:8px;text-align:center;">
                    <div style="font-size:11px;color:#8892b0;text-transform:uppercase;letter-spacing:0.5px;">Stop</div>
                    <div style="font-size:17px;font-weight:700;color:#ff4757;">₹{stop:.1f}</div>
                </div>
                <div class="price-box" style="background:rgba(255,255,255,0.06);border-radius:8px;padding:8px;text-align:center;">
                    <div style="font-size:11px;color:#8892b0;text-transform:uppercase;letter-spacing:0.5px;">Target</div>
                    <div style="font-size:17px;font-weight:700;color:#00c896;">₹{target:.1f}</div>
                </div>
            </div>
            <div style="display:flex;gap:12px;font-size:12px;color:#8892b0;flex-wrap:wrap;">
                <span>ADX: {s.get('adx','-')}</span>
                <span>RSI: {s.get('rsi','-')}</span>
                <span>RVOL: {s.get('rvol','-')}</span>
                <span>RR: {rr}</span>
                {f'<span style="color:{dir_color};">{factors}</span>' if factors else ''}
            </div>
            {render_news(s.get('news', []))}
            {render_sr(s.get('sr'))}
        </div>'''

    if not cards:
        cards = '<div style="text-align:center;padding:40px;color:#8892b0;font-size:16px;">No active signals at this time.</div>'

    total = len(signals)
    longs = len([s for s in signals if s.get('direction') == 'LONG'])
    shorts = total - longs
    mkt_dir = 'SIDEWAYS'
    mkt_sent = 'NEUTRAL'
    if signals:
        mkt_dir = signals[0].get('market_direction', 'SIDEWAYS')
        mkt_sent = signals[0].get('market_sentiment', 'NEUTRAL')
    sent_color = '#00c896' if mkt_sent == 'BULLISH' else '#ff4757' if mkt_sent == 'BEARISH' else '#ffd700'

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#0a192f;color:#ccd6f6;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a192f;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;">
<tr><td style="padding:40px 20px 20px;">
    <div style="text-align:center;margin-bottom:32px;">
        <div style="font-size:36px;margin-bottom:4px;">🧿</div>
        <div style="font-size:22px;font-weight:800;color:#00c896;letter-spacing:2px;">NEMO SIGNALS</div>
        <div style="font-size:13px;color:#495670;margin-top:4px;">{date_str} · {ts} IST</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px;">
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Signals</div>
            <div style="font-size:20px;font-weight:700;color:#ccd6f6;">{total}</div>
        </div>
        <div style="background:rgba(0,200,150,0.06);border-radius:10px;padding:12px;text-align:center;border:1px solid rgba(0,200,150,0.15);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Long</div>
            <div style="font-size:20px;font-weight:700;color:#00c896;">{longs}</div>
        </div>
        <div style="background:rgba(255,71,87,0.06);border-radius:10px;padding:12px;text-align:center;border:1px solid rgba(255,71,87,0.15);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Short</div>
            <div style="font-size:20px;font-weight:700;color:#ff4757;">{shorts}</div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Sentiment</div>
            <div style="font-size:16px;font-weight:700;color:{sent_color};">{mkt_sent}</div>
        </div>
    </div>
    <div style="text-align:center;font-size:12px;color:#495670;margin-bottom:20px;">
        Market: <span style="color:#ccd6f6;font-weight:600;">{mkt_dir}</span>
        · Generated by <span style="color:#00c896;">Nemo v4.1</span>
        · Nifty 50 Scan
    </div>
    {cards}
    <div style="text-align:center;margin-top:24px;padding:20px;border-top:1px solid rgba(255,255,255,0.06);">
        <div style="font-size:11px;color:#495670;">
            Nemo Trading System · Not financial advice · Trade at your own risk<br>
            <span style="color:#00c896;">Stop-losses are mandatory</span>
        </div>
    </div>
</td></tr></table>
</td></tr></table>
</body>
</html>'''
    return html

if __name__ == '__main__':
    test_signals = [
        {'symbol':'RELIANCE','direction':'LONG','entry':1405,'stop':1398,'target':1420,
         'score':15,'conf':90,'rr':2.1,'adx':28,'rsi':42,'rvol':1.6,
         'factors':['VWAP+','ADX','RVOL','RSI']},
        {'symbol':'TCS','direction':'SHORT','entry':2390,'stop':2405,'target':2365,
         'score':14,'conf':84,'rr':1.8,'adx':32,'rsi':58,'rvol':1.4,
         'factors':['VWAP-','ADX','RSI','MACD-']},
    ]
    print(build_html(test_signals, 'Thursday, 11 June 2026', '3:15 PM'))
