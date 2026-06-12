"""Nemo Cloud App — Flask server for Google Chat bot + Telegram bot + scheduled scans."""
import os, sys, json, logging, traceback
from datetime import datetime, time
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemo_engine as engine
import nemo_mailer
import nemo_news
import nemo_env

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('nemo')

app = Flask(__name__)

engine.CONFIG['backtest_mode'] = True
engine._INDEX_CACHE = {}

# --- Google Chat webhook ---
@app.route('/chat', methods=['POST'])
def google_chat():
    """Handle Google Chat bot messages."""
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message', {}).get('text', '')
        sender = data.get('user', {}).get('displayName', 'User')
        space = data.get('space', {}).get('name', '')
        log.info(f'Chat from {sender}: {message[:100]}')
        response_text = handle_command(message)
        return jsonify({'text': response_text})
    except Exception as e:
        log.error(f'Chat error: {e}')
        return jsonify({'text': f'Sorry, something went wrong: {str(e)}'})

# --- Telegram webhook ---
@app.route('/telegram', methods=['POST'])
def telegram():
    """Handle Telegram bot updates."""
    try:
        data = request.get_json(silent=True) or {}
        msg = data.get('message', {})
        chat_id = msg.get('chat', {}).get('id')
        text = msg.get('text', '')
        if not chat_id or not text:
            return 'ok'
        log.info(f'Telegram from {chat_id}: {text[:100]}')
        response_text = handle_command(text)
        import urllib.request, urllib.parse
        token = nemo_env.telegram_token()
        if token:
            payload = urllib.parse.urlencode({
                'chat_id': chat_id, 'text': response_text, 'parse_mode': 'Markdown'
            }).encode()
            urllib.request.urlopen(f'https://api.telegram.org/bot{token}/sendMessage', payload, timeout=10)
        return 'ok'
    except Exception as e:
        log.error(f'Telegram error: {e}')
        return 'ok'

# --- Scheduled task endpoints ---
@app.route('/morning-brief', methods=['GET'])
def morning_brief():
    try:
        import nemo_morning_update
        ok = nemo_morning_update.send_briefing()
        if ok:
            return 'Brief sent', 200
        return 'Failed', 500
    except Exception as e:
        log.error(f'Brief error: {e}')
        return str(e), 500

@app.route('/first-signal', methods=['GET'])
def first_signal():
    try:
        from nemo_first_signal import send_first_signal
        send_first_signal()
        return 'OK', 200
    except Exception as e:
        log.error(f'First signal error: {e}')
        return str(e), 500

@app.route('/scan', methods=['GET'])
def scan():
    try:
        from nemo_continuous_scan import run_scan
        signals = run_scan()
        return jsonify({'signals': len(signals)}), 200
    except Exception as e:
        log.error(f'Scan error: {e}')
        return str(e), 500

@app.route('/', methods=['GET'])
def health():
    return 'Nemo is alive', 200

# --- Command handler ---
def handle_command(text):
    t = text.lower().strip()
    try:
        if t in ('hi', 'hello', 'hey'):
            return 'Hello! I\'m Nemo. Ask me about the market, stocks, or try:\n• `market` — market status\n• `scan` — top signals now\n• `nifty` — Nifty 50\n• `portfolio` — your trades\n• `help` — all commands'

        if t == 'help':
            return '**Nemo Commands:**\n`market` — Market direction & breadth\n`scan` — Top 5 signals\n`nifty` — Nifty 50 level\n`sectors` — Sector performance\n`portfolio` — Open trades\n`news` — Latest market news\n`[stock]` — e.g. `RELIANCE` for analysis'

        if t in ('market', 'status'):
            idx = engine.fetch_index(period_days=5)
            if idx is None: return 'Can\'t fetch market data right now.'
            b = engine.get_market_breadth(idx)
            md = engine.get_market_direction(idx)
            close = idx['Close'].iloc[-1]
            prev = idx['Close'].iloc[-2] if len(idx) > 1 else close
            chg = (close - prev) / prev * 100
            dir_label = md[0] if isinstance(md, tuple) else md
            return f'*Nifty 50:* {close:.0f} ({chg:+.2f}%)\n*Direction:* {dir_label}\n*A/D:* {b["ad_ratio"]:.0f}\n*Stocks above EMA:* {b["above_ema_pct"]:.0f}%'

        if t == 'scan':
            sigs = run_full_scan()
            if not sigs: return 'No signals right now.'
            lines = ['*Top Signals:*']
            for s in sigs[:5]:
                emoji = '🟢' if s['direction'] == 'LONG' else '🔴'
                lines.append(f'{emoji} {s["symbol"]} {s["direction"]} score={s["score"]} entry={s["entry"]} stop={s["stop"]}')
            return '\n'.join(lines)

        if t in ('nifty', 'nifty 50', 'sensex'):
            idx = engine.fetch_index(period_days=2)
            if idx is None: return 'Can\'t fetch data.'
            c = idx['Close'].iloc[-1]; p = idx['Close'].iloc[-2] if len(idx) > 1 else c
            return f'Nifty 50: {c:.0f} ({(c-p)/p*100:+.2f}%)'

        if t.startswith('news'):
            news = nemo_news.summarize('', max_items=5)
            if not news: return 'No news right now.'
            lines = ['*Market News:*']
            for n in news:
                icon = {'positive': '🟢', 'negative': '🔴'}.get(n.get('sentiment'), '⚪')
                lines.append(f'{icon} {n["title"][:80]}')
            return '\n'.join(lines)

        stock = t.upper()
        if stock in engine.NIFTY_50:
            df = engine.fetch_history(stock, period_days=5, interval='5m')
            if df is None: return f'Can\'t fetch {stock}.'
            dc = engine.calc_indicators(df)
            if dc is None: return f'No data for {stock}.'
            l = engine._last_valid_row(df)
            idx = engine.fetch_index(period_days=5)
            b = engine.get_market_breadth(idx) if idx is not None else {'ad_ratio': 50, 'above_ema_pct': 50}
            md = engine.get_market_direction(idx) if idx is not None else ('SIDEWAYS', 'NONE', 0)
            sig = engine.analyze_signal(dc, stock, b, (md[0], md[1], md[2]) if isinstance(md, tuple) else (md, 'NONE', 0))
            lines = [f'*{stock}:* {l["Close"]:.1f}']
            lines.append(f'ADX {l["ADX"]:.0f} RSI {l["RSI"]:.0f} RVOL {l["RVOL"]:.1f} ATR {l["ATR"]:.1f}')
            if sig:
                emoji = '🟢' if sig['direction'] == 'LONG' else '🔴'
                lines.append(f'{emoji} Signal: {sig["direction"]} score={sig["score"]}')
                lines.append(f'Entry {sig["entry"]} Stop {sig["stop"]} Target {sig["target"]}')
            else:
                lines.append('No signal')
            return '\n'.join(lines)

        return f'I don\'t understand "{text}". Try `help` for commands.'
    except Exception as e:
        log.error(f'Command error: {traceback.format_exc()}')
        return f'Sorry, error: {str(e)[:100]}'

def run_full_scan():
    idx = engine.fetch_index(period_days=5)
    if idx is None: return []
    b = engine.get_market_breadth(idx)
    md = engine.get_market_direction(idx)
    mkt_tuple = (md[0], md[1], md[2]) if isinstance(md, tuple) else (md, 'NONE', 0)
    sigs = []
    for sym in engine.NIFTY_50:
        df = engine.fetch_history(sym, period_days=5, interval='5m')
        if df is None: continue
        dc = engine.calc_indicators(df)
        if dc is None: continue
        s = engine.analyze_signal(dc, sym, b, mkt_tuple)
        if s: sigs.append(s)
    sigs.sort(key=lambda x: -x['score'])
    return sigs[:5]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
