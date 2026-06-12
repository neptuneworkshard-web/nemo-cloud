import os, sys, time, warnings
from datetime import datetime
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nemo_engine as engine
import nemo_mailer
import nemo_news

engine.CONFIG['backtest_mode'] = True
engine._INDEX_CACHE = {}

def send_first_signal():
    idx5 = engine.fetch_index(period_days=5)
    breadth = engine.get_market_breadth(idx5)
    mkt_dir, mkt_bias, mkt_strength = engine.get_market_direction(idx5)

    best = None
    for sym in engine.NIFTY_50:
        df = engine.fetch_history(sym, period_days=5, interval='5m')
        if df is None: continue
        dc = engine.calc_indicators(df)
        if dc is None: continue
        sig = engine.analyze_signal(dc, sym, breadth, (mkt_dir, mkt_bias, mkt_strength))
        if sig is None: continue
        if best is None or sig['score'] > best['score']:
            best = sig

    if best:
        news = nemo_news.summarize(best['symbol'], max_items=3)
        best['news'] = news
        best['market_direction'] = mkt_dir

        dir_emoji = '\U0001F535' if best['direction'] == 'LONG' else '\U0001F534'
        date_str = datetime.now().strftime('%A, %d %B %Y')
        ts = datetime.now().strftime('%I:%M %p')

        print(f'First Signal: {best["symbol"]} {best["direction"]} score={best["score"]}')
        print(f'Entry: {best["entry"]:.1f} Stop: {best["stop"]:.1f} Target: {best["target"]:.1f}')
        print(f'ADX: {best["adx"]} RSI: {best["rsi"]} RVOL: {best["rvol"]} RR: {best["rr"]}')
        print(f'News: {len(news)} items')

        nemo_mailer.send_signal_email([best], subject=f'Nemo First Signal — {best["symbol"]} {best["direction"]} ({date_str})')
        return True
    else:
        print('No signals found')
        nemo_mailer.send_signal_email([], subject=f'Nemo First Signal — No Trades ({datetime.now().strftime("%d %b")})')
        return False

if __name__ == '__main__':
    t0 = time.time()
    send_first_signal()
    print(f'Done in {time.time()-t0:.0f}s')
