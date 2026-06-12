import os, sys, json, time, warnings
from datetime import datetime
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemo_engine as engine
import nemo_mailer
import nemo_news

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_signals')
os.makedirs(OUT_DIR, exist_ok=True)

engine.CONFIG['backtest_mode'] = True
engine._INDEX_CACHE = {}

def build_briefing():
    idx5 = engine.fetch_index(period_days=5)
    breadth = engine.get_market_breadth(idx5)
    mkt_dir, mkt_bias, mkt_strength = engine.get_market_direction(idx5)
    mkt_note = mkt_bias

    # Scan all stocks for watchlist
    candidates = []
    for sym in engine.NIFTY_50:
        df = engine.fetch_history(sym, period_days=5, interval='5m')
        if df is None: continue
        dc = engine.calc_indicators(df)
        if dc is None: continue
        sig = engine.analyze_signal(dc, sym, breadth, (mkt_dir, mkt_bias, mkt_strength))
        if sig is None: continue
        candidates.append(sig)

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top5 = candidates[:5]

    # Fetch news for all top 5
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        fut = {pool.submit(nemo_news.summarize, s['symbol'], 2): s for s in top5}
        for f in concurrent.futures.as_completed(fut):
            s = fut[f]
            try:
                news = f.result()
                if news: s['news'] = news
            except: pass

    # Key levels from index
    idx_close = idx5['Close'].iloc[-1]
    prev_close = idx5['Close'].iloc[-2] if len(idx5) > 1 else idx_close
    day_change = ((idx_close - prev_close) / prev_close) * 100

    # Count breakouts / breakdowns
    if candidates:
        long_count = len([s for s in candidates if s['direction'] == 'LONG'])
        short_count = len([s for s in candidates if s['direction'] == 'SHORT'])
    else:
        long_count = short_count = 0

    mkt_sent = engine.calc_market_sentiment(mkt_dir, breadth)
    return {
        'mkt_dir': mkt_dir,
        'mkt_note': mkt_note,
        'mkt_sent': mkt_sent,
        'ad_ratio': breadth['ad_ratio'],
        'idx_close': idx_close,
        'day_change': day_change,
        'long_count': long_count,
        'short_count': short_count,
        'total_candidates': len(candidates),
        'top5': top5,
    }

def build_briefing_html(b):
    cards = ''
    for i, s in enumerate(b['top5']):
        dc = '#00c896' if s['direction'] == 'LONG' else '#ff4757'
        bg = 'rgba(0,200,150,0.08)' if s['direction'] == 'LONG' else 'rgba(255,71,87,0.08)'
        border = '2px solid rgba(0,200,150,0.3)' if s['direction'] == 'LONG' else '2px solid rgba(255,71,87,0.3)'
        factors = ', '.join(s.get('factors', [])[:4])

        news_html = ''
        for n in s.get('news', []):
            icon = {'positive': '🟢', 'negative': '🔴', 'neutral': '⚪'}.get(n.get('sentiment'), '⚪')
            news_html += f'<div style="font-size:11px;color:#8892b0;padding:2px 0;">{icon} {n["title"]}</div>'
        sr = s.get('sr', {})
        sr_html = ''
        if sr:
            sr_html = f'''
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-top:6px;">
                <div style="font-size:9px;color:#ff4757;">
                    <span style="color:#495670;">R:</span> {sr["r3"]:.0f} | {sr["r2"]:.0f} | {sr["r1"]:.0f}
                </div>
                <div style="font-size:9px;color:#00c896;text-align:right;">
                    <span style="color:#495670;">S:</span> {sr["s1"]:.0f} | {sr["s2"]:.0f} | {sr["s3"]:.0f}
                </div>
            </div>'''

        news_section = ''
        if news_html:
            news_section = f'''
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.06);">
                <div style="font-size:10px;color:#495670;text-transform:uppercase;margin-bottom:4px;">📰 Moneycontrol</div>
                {news_html}
            </div>'''

        cards += f'''
        <div style="background:{bg};border:{border};border-radius:10px;padding:14px;margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-size:16px;font-weight:700;color:{dc};">{s['symbol']} — {s['direction']}</span>
                <span style="background:{dc};color:#fff;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;">Score {s['score']}</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:6px;">
                <div style="background:rgba(255,255,255,0.06);border-radius:6px;padding:6px;text-align:center;">
                    <div style="font-size:10px;color:#8892b0;">Entry</div>
                    <div style="font-size:15px;font-weight:700;color:#ccd6f6;">₹{s['entry']:.1f}</div>
                </div>
                <div style="background:rgba(255,255,255,0.06);border-radius:6px;padding:6px;text-align:center;">
                    <div style="font-size:10px;color:#8892b0;">Stop</div>
                    <div style="font-size:15px;font-weight:700;color:#ff4757;">₹{s['stop']:.1f}</div>
                </div>
                <div style="background:rgba(255,255,255,0.06);border-radius:6px;padding:6px;text-align:center;">
                    <div style="font-size:10px;color:#8892b0;">Target</div>
                    <div style="font-size:15px;font-weight:700;color:#00c896;">₹{s['target']:.1f}</div>
                </div>
            </div>
            {sr_html}
            <div style="font-size:11px;color:#8892b0;display:flex;gap:10px;flex-wrap:wrap;margin-top:4px;">
                <span>ADX {s['adx']}</span>
                <span>RSI {s['rsi']}</span>
                <span>RVOL {s['rvol']}</span>
                <span>RR {s['rr']}</span>
                {f'<span style="color:{dc};">{factors}</span>' if factors else ''}
            </div>
            {news_section}
        </div>'''

    if not cards:
        cards = '<div style="text-align:center;padding:40px;color:#8892b0;">No candidates today.</div>'

    arrow = '📈' if b['day_change'] > 0 else '📉' if b['day_change'] < 0 else '➡️'
    mkt_color = '#00c896' if b['mkt_dir'] == 'UPTREND' else '#ff4757' if b['mkt_dir'] == 'DOWNTREND' else '#ffd700'

    sent_color = '#00c896' if b['mkt_sent'] == 'BULLISH' else '#ff4757' if b['mkt_sent'] == 'BEARISH' else '#ffd700'

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#0a192f;color:#ccd6f6;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a192f;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;">
<tr><td style="padding:40px 20px 20px;">
    <div style="text-align:center;margin-bottom:28px;">
        <div style="font-size:32px;margin-bottom:4px;">🌅</div>
        <div style="font-size:20px;font-weight:800;color:#00c896;letter-spacing:2px;">NEMO MORNING BRIEF</div>
        <div style="font-size:12px;color:#495670;margin-top:4px;">{datetime.now().strftime("%A, %d %B %Y")} · 8:30 AM IST</div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:20px;">
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:14px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Nifty 50 Close</div>
            <div style="font-size:22px;font-weight:700;color:#ccd6f6;">{b['idx_close']:.0f}</div>
            <div style="font-size:12px;color:{mkt_color};">{arrow} {b['day_change']:+.2f}%</div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:14px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:10px;color:#495670;text-transform:uppercase;">Market</div>
            <div style="font-size:16px;font-weight:700;color:{mkt_color};">{b['mkt_dir']}</div>
            <div style="font-size:11px;color:{sent_color};font-weight:600;">{b['mkt_sent']}</div>
            <div style="font-size:9px;color:#8892b0;">{b['mkt_note']}</div>
        </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px;">
        <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:#495670;">A/D Ratio</div>
            <div style="font-size:16px;font-weight:700;">{b['ad_ratio']:.1f}</div>
        </div>
        <div style="background:rgba(0,200,150,0.06);border-radius:8px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:#495670;">Long</div>
            <div style="font-size:16px;font-weight:700;color:#00c896;">{b['long_count']}</div>
        </div>
        <div style="background:rgba(255,71,87,0.06);border-radius:8px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:#495670;">Short</div>
            <div style="font-size:16px;font-weight:700;color:#ff4757;">{b['short_count']}</div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:10px;color:#495670;">Candidates</div>
            <div style="font-size:16px;font-weight:700;">{b['total_candidates']}</div>
        </div>
    </div>

    <div style="background:rgba(255,255,255,0.03);border-radius:10px;padding:14px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.06);">
        <div style="font-size:11px;color:#495670;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">🎯 Stocks to Watch Today</div>
        {cards}
    </div>

    <div style="text-align:center;margin-top:20px;padding:16px;border-top:1px solid rgba(255,255,255,0.06);">
        <div style="font-size:11px;color:#495670;">
            ⏰ Next signal at <span style="color:#00c896;font-weight:600;">9:00 AM</span><br>
            Nemo Trading System · Not financial advice · Trade at your own risk
        </div>
    </div>
</td></tr></table>
</td></tr></table>
</body>
</html>'''
    return html

def send_briefing():
    b = build_briefing()
    html = build_briefing_html(b)

    creds = nemo_mailer.load_creds()
    gmail_user = creds.get('GMAIL_USER', 'neptune.works.hard@gmail.com')
    gmail_app_pw = creds.get('GMAIL_APP_PASSWORD', '')
    to_email = creds.get('EMAIL_TO', gmail_user)
    if not gmail_app_pw:
        print('[brief] No GMAIL_APP_PASSWORD')
        return False

    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib

    msg = MIMEMultipart('alternative')
    msg['From'] = gmail_user
    msg['To'] = to_email
    date_str = datetime.now().strftime('%A, %d %B %Y')
    msg['Subject'] = f'Nemo Morning Brief · {b["mkt_dir"]} · {date_str}'
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_app_pw)
        server.sendmail(gmail_user, [to_email], msg.as_string())
        server.quit()
        print(f'[brief] Morning briefing sent to {to_email}')
        return True
    except Exception as e:
        print(f'[brief] Failed: {e}')
        return False

if __name__ == '__main__':
    t0 = time.time()
    b = build_briefing()
    print(f'Market: {b["mkt_dir"]} · {b["mkt_note"]}')
    print(f'Nifty: {b["idx_close"]:.0f} ({b["day_change"]:+.2f}%)')
    print(f'A/D: {b["ad_ratio"]:.1f} · Long: {b["long_count"]} · Short: {b["short_count"]}')
    print(f'Top: {[s["symbol"]+" "+s["direction"] for s in b["top5"][:3]]}')
    send_briefing()
    print(f'Done in {time.time()-t0:.0f}s')
