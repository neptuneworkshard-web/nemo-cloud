import os, sys, json, time, math, warnings, concurrent.futures
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemo_engine as engine
import nemo_mailer
import nemo_news
import nemo_env

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_signals')
os.makedirs(OUT_DIR, exist_ok=True)

def scan():
    print(f'[scan] {datetime.now().strftime("%H:%M")} — Scanning Nifty 50...')

    # Default params — best from backtest (both dir, 0.75% target, score>=10)
    engine.CONFIG['backtest_mode'] = True
    engine.CONFIG['long_only'] = False
    engine.CONFIG['min_score'] = 10
    engine.CONFIG['target_pct'] = 0.75
    engine.CONFIG['stop_pct'] = 0.4
    engine.CONFIG['adx_min'] = 25
    engine.CONFIG['rvol_min'] = 1.3
    engine.CONFIG['ai_min_pct'] = 0.3
    engine.CONFIG['rsi_long_max'] = 45
    engine._INDEX_CACHE = {}

    idx5 = engine.fetch_index(period_days=5)
    breadth = engine.get_market_breadth(idx5)
    mkt_dir, mkt_bias, mkt_strength = engine.get_market_direction(idx5)
    mkt_note = mkt_bias
    mkt_tuple = (mkt_dir, mkt_bias, mkt_strength)
    print(f'[scan] Market: {mkt_dir} ({mkt_note})  A/D: {breadth["ad_ratio"]}')

    signals = []
    for sym in engine.NIFTY_50:
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

    signals.sort(key=lambda x: x['score'], reverse=True)

    print(f'[scan] Found {len(signals)} signals')
    if signals:
        best = signals[0]
        print(f'[scan] Best: {best["symbol"]} {best["direction"]} score={best["score"]}')

    # Fetch news for ALL signals in parallel
    if signals:
        print(f'[scan] Fetching news for {len(signals)} signals...')
        sym_to_sig = {s['symbol']: s for s in signals}
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            fut = {pool.submit(nemo_news.summarize, sym, 2): sym for sym in sym_to_sig}
            for f in concurrent.futures.as_completed(fut):
                sym = fut[f]
                try:
                    news = f.result()
                    if news:
                        sym_to_sig[sym]['news'] = news
                except: pass
        print(f'[scan] News fetched')
    return signals, mkt_dir

def send_alerts(signals, mkt_dir):
    if not signals:
        # Send email saying no signals
        print('[scan] No signals — sending notification email')
        nemo_mailer.send_signal_email(signals, subject=f'Nemo Signals — No Active Trades ({datetime.now().strftime("%d %b")})')
        return

    print(f'[scan] Sending email with {len(signals)} signals...')
    nemo_mailer.send_signal_email(signals, subject=f'Nemo Signals — {len(signals)} Trades · {mkt_dir} ({datetime.now().strftime("%d %b %H:%M")})')

    # Telegram
    try:
        import requests
        token = nemo_env.telegram_token()
        chat_id = nemo_env.telegram_chat()
        if token and chat_id:
            top = signals[:5]
            lines = [f'\U0001F9D9 Nemo Signals ({len(signals)} active)']
            lines.append(f'\U0001F4C8 Market: {mkt_dir}')
            lines.append('')
            for s in top:
                emoji = '\U0001F535' if s['direction'] == 'LONG' else '\U0001F534'
                lines.append(f'{emoji} {s["symbol"]} {s["direction"]} \u20B9{s["entry"]:.1f}')
                lines.append(f'   Stop \u20B9{s["stop"]:.1f}  Target \u20B9{s["target"]:.1f}')
                lines.append(f'   Score {s["score"]}  ADX {s["adx"]}  RR {s["rr"]}')
            msg = '\n'.join(lines)
            url = f'https://api.telegram.org/bot{token}/sendMessage'
            requests.post(url, json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'})
            print('[scan] Telegram sent')
    except Exception as e:
        print(f'[scan] Telegram failed: {e}')

def save(signals):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(OUT_DIR, f'scan_{ts}.json')
    with open(path, 'w') as f:
        json.dump({'timestamp': ts, 'signals': signals}, f, indent=2)
    print(f'[scan] Saved to {path}')

if __name__ == '__main__':
    t0 = time.time()
    signals, mkt_dir = scan()
    elapsed = time.time() - t0
    print(f'[scan] Scan completed in {elapsed:.0f}s')
    save(signals)
    send_alerts(signals, mkt_dir)
