"""Nemo Continuous Scanner — runs market-hours, scans every 15 min, sends Telegram + email alerts."""
import os, sys, json, time, warnings, traceback
from datetime import datetime, time as dtime
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemo_engine as engine
import nemo_mailer
import nemo_news
import nemo_env

engine.CONFIG['backtest_mode'] = False
engine._INDEX_CACHE = {}

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_signals', 'continuous_scan_log.txt')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def is_market_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)

def should_scan():
    if not is_market_hours():
        return False
    if engine.check_time_blackout():
        return False
    return True

def run_scan():
    idx5 = engine.fetch_index(period_days=5)
    if idx5 is None or len(idx5) < 30:
        log('No index data, skipping')
        return []
    breadth = engine.get_market_breadth(idx5)
    mkt_dir, mkt_bias, mkt_strength = engine.get_market_direction(idx5)
    mkt_tuple = (mkt_dir, mkt_bias, mkt_strength)

    signals = []
    for sym in engine.NIFTY_50:
        try:
            df = engine.fetch_history(sym, period_days=5, interval='5m')
            if df is None:
                continue
            dc = engine.calc_indicators(df)
            if dc is None:
                continue
            sig = engine.analyze_signal(dc, sym, breadth, mkt_tuple)
            if sig is None:
                continue
            sig['market_direction'] = mkt_dir
            signals.append(sig)
        except:
            continue

    signals.sort(key=lambda x: x['score'], reverse=True)
    return signals[:5]

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_signals', 'continuous_state.json')

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {'sent_signals': {}, 'last_alert_time': 0, 'alerted_today': False}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def main():
    log('Nemo Continuous Scanner started')
    state = load_state()

    # Check if we should reset for a new day
    today = datetime.now().strftime('%Y-%m-%d')
    if state.get('last_date') != today:
        state = {'sent_signals': {}, 'last_alert_time': 0, 'alerted_today': False, 'last_date': today}
        save_state(state)

    signals = run_scan()
    if not signals:
        log('No signals found')
        return

    best = signals[0]
    sig_key = f"{best['symbol']}_{best['direction']}"

    # Only alert on NEW signals or if score increased
    prev = state['sent_signals'].get(sig_key, 0)
    if best['score'] > prev:
        log(f'NEW/IMPROVED signal: {best["symbol"]} {best["direction"]} score={best["score"]} (was {prev})')

        try:
            news = nemo_news.summarize(best['symbol'], max_items=3)
            best['news'] = news
        except:
            best['news'] = []

        nemo_mailer.send_signal_email([best], subject=f'Alert: {best["symbol"]} {best["direction"]} ({best["score"]})')

        try:
            import urllib.request, urllib.parse
            try:
                token = nemo_env.telegram_token()
                chat_id = nemo_env.telegram_chat()
                if token and chat_id:
                    dir_emoji = '\U0001F535' if best['direction'] == 'LONG' else '\U0001F534'
                    text = f'''{dir_emoji} *{best["symbol"]} {best["direction"]}* (Score {best["score"]})
Entry: {best["entry"]} | Stop: {best["stop"]} | Target: {best["target"]}
ADX: {best["adx"]} | RSI: {best["rsi"]} | RR: {best["rr"]}
Market: {mkt_dir}'''
                    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}).encode()
                    urllib.request.urlopen(f'https://api.telegram.org/bot{token}/sendMessage', data, timeout=10)
            except:
                pass
        except:
            pass

        state['sent_signals'][sig_key] = best['score']
        state['last_alert_time'] = time.time()
        state['alerted_today'] = True
        save_state(state)
    else:
        log(f'No new signals (best: {best["symbol"]} {best["direction"]} {best["score"]})')

if __name__ == '__main__':
    try:
        main()
    except:
        log(traceback.format_exc())
