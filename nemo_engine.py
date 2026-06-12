import os, json, warnings, math, sys, time as _time_mod
from datetime import datetime, time
import numpy as np
import pandas as pd
import yfinance as yf
warnings.filterwarnings('ignore')

CONFIG = {
    'adx_min': 25, 'rvol_min': 1.3, 'adx_gate': 18, 'rvol_gate': 0.3,
    'ai_min_pct': 0.3,
    'target_atr': 2.5, 'stop_atr': 0.5, 'target_pct': 1.2, 'stop_pct': 0.3,
    'max_hold_bars': 24, 'max_signals_per_side': 3, 'min_score': 15, 'max_score': 25,
    'backtest_mode': False, 'long_only': False, 'rsi_long_max': 45,
    'use_supertrend': True,
}
NIFTY_50 = [
    'RELIANCE','TCS','INFY','HDFCBANK','ICICIBANK','SBIN','BHARTIARTL','LT',
    'KOTAKBANK','HINDUNILVR','WIPRO','MARUTI','TITAN','BAJFINANCE','NESTLEIND',
    'SUNPHARMA','TECHM','ADANIPORTS','ASIANPAINT','AXISBANK','HDFCLIFE','ITC',
    'ONGC','NTPC','POWERGRID','JSWSTEEL','ADANIENT','GRASIM','TATASTEEL',
    'HINDALCO','M&M','CIPLA','DRREDDY','APOLLOHOSP','INDIGO','BAJAJ-AUTO',
    'EICHERMOT','TRENT','TATACONSUM','ULTRACEMCO','SBILIFE','SHRIRAMFIN',
    'JIOFIN','BEL','HCLTECH','DIVISLAB','PERSISTENT','COFORGE','MPHASIS'
]

_FETCH_CACHE = {}
_INDEX_CACHE = {}
_last_fetch_time = 0.0

def fetch_history(symbol, period_days=5, interval='5m', end_date=None):
    key = f'{symbol}_{period_days}_{interval}_{end_date}'
    if key in _FETCH_CACHE:
        return _FETCH_CACHE[key]
    global _last_fetch_time
    try:
        elapsed = _time_mod.time() - _last_fetch_time
        if elapsed < 0.15:
            _time_mod.sleep(0.15 - elapsed)
        _last_fetch_time = _time_mod.time()
        t = yf.Ticker(symbol + '.NS')
        if end_date:
            end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
            start_dt = end_dt - pd.Timedelta(days=period_days)
            df = t.history(start=start_dt.strftime('%Y-%m-%d'), end=end_dt.strftime('%Y-%m-%d'), interval=interval)
        else:
            df = t.history(period=str(period_days)+'d', interval=interval)
        if df is None or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        _FETCH_CACHE[key] = df
        return df
    except:
        return None

def fetch_index(period_days=3, interval='5m', end_date=None):
    key = f'{period_days}_{interval}_{end_date}'
    if key in _INDEX_CACHE:
        return _INDEX_CACHE[key]
    global _last_fetch_time
    try:
        elapsed = _time_mod.time() - _last_fetch_time
        if elapsed < 0.15:
            _time_mod.sleep(0.15 - elapsed)
        _last_fetch_time = _time_mod.time()
        t = yf.Ticker('^NSEI')
        if end_date:
            end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
            start_dt = end_dt - pd.Timedelta(days=period_days)
            df = t.history(start=start_dt.strftime('%Y-%m-%d'), end=end_dt.strftime('%Y-%m-%d'), interval=interval)
        else:
            df = t.history(period=str(period_days)+'d', interval=interval)
        if df is not None and len(df) >= 3:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            _INDEX_CACHE[key] = df
            return df
    except:
        pass
    return None

def get_market_breadth(idx_df=None):
    df = idx_df if idx_df is not None else fetch_index(period_days=3)
    try:
        if df is not None and len(df) >= 5:
            ret = df['Close'].pct_change().dropna()
            positive = (ret > 0).sum()
            ad_ratio = (positive / len(ret)) * 100
            ema20 = df['Close'].ewm(20).mean()
            above_ema = (df['Close'] > ema20).sum() / len(df) * 100
            return {'ad_ratio': round(ad_ratio, 1), 'above_ema_pct': round(above_ema, 1)}
    except: pass
    return {'ad_ratio': 50, 'above_ema_pct': 50}

def _tf_direction(df):
    """Internal: assess direction on a single dataframe."""
    if df is None or len(df) < 20:
        return 'SIDEWAYS'
    try:
        cl = df['Close']; curr = float(cl.iloc[-1])
        op = float(df['Open'].iloc[0])
        e9 = float(cl.ewm(9, min_periods=5).mean().iloc[-1])
        e21 = float(cl.ewm(21, min_periods=10).mean().iloc[-1])
        if curr > e9 and curr > e21 and curr > op: return 'UPTREND'
        if curr < e9 and curr < e21 and curr < op: return 'DOWNTREND'
    except:
        pass
    return 'SIDEWAYS'

def get_market_direction(idx_df=None):
    """Multi-timeframe market direction: 3d, 5d, 10d vote."""
    d3 = _tf_direction(idx_df) if idx_df is not None else _tf_direction(fetch_index(period_days=3, interval='15m'))
    d5 = _tf_direction(fetch_index(period_days=5, interval='30m'))
    d10 = _tf_direction(fetch_index(period_days=10, interval='60m'))
    votes = [d for d in [d3, d5, d10] if d != 'SIDEWAYS']
    uptrend_votes = votes.count('UPTREND')
    downtrend_votes = votes.count('DOWNTREND')
    total = uptrend_votes + downtrend_votes
    if total == 0:
        return 'SIDEWAYS', 'NO NEW TRADES', 0
    if uptrend_votes > downtrend_votes:
        bias = 'LONG'
        dir_label = 'UPTREND'
    elif downtrend_votes > uptrend_votes:
        bias = 'SHORT'
        dir_label = 'DOWNTREND'
    else:
        return 'SIDEWAYS', 'LONG & SHORT', 0
    strength = max(uptrend_votes, downtrend_votes)
    return dir_label, bias, strength

def calc_support_resistance(df):
    try:
        daily_h = df['High'].rolling(20).max().iloc[-1]
        daily_l = df['Low'].rolling(20).min().iloc[-1]
        daily_c = df['Close'].iloc[-1]
        pp = (daily_h + daily_l + daily_c) / 3
        r1 = 2 * pp - daily_l; r2 = pp + (daily_h - daily_l); r3 = daily_h + 2 * (pp - daily_l)
        s1 = 2 * pp - daily_h; s2 = pp - (daily_h - daily_l); s3 = daily_l - 2 * (daily_h - pp)
        return {
            'pp': round(pp, 2), 'r1': round(r1, 2), 'r2': round(r2, 2), 'r3': round(r3, 2),
            's1': round(s1, 2), 's2': round(s2, 2), 's3': round(s3, 2),
        }
    except: return None

def calc_market_sentiment(mkt_dir, breadth):
    if isinstance(mkt_dir, tuple):
        mkt_dir = mkt_dir[0]
    adr = breadth.get('ad_ratio', 50)
    if mkt_dir == 'UPTREND' and adr > 55: return 'BULLISH'
    if mkt_dir == 'DOWNTREND' and adr < 45: return 'BEARISH'
    if mkt_dir == 'UPTREND': return 'BULLISH'
    if mkt_dir == 'DOWNTREND': return 'BEARISH'
    if adr > 55: return 'BULLISH'
    if adr < 45: return 'BEARISH'
    return 'NEUTRAL'

def check_direction(trade_dir, mkt_dir, strength=0):
    """Returns (allowed: bool, penalty: int) based on multi-TF vote."""
    if mkt_dir == 'SIDEWAYS':
        return False, 0
    if mkt_dir == 'UPTREND' and trade_dir == 'SHORT':
        return False, 0
    if mkt_dir == 'DOWNTREND' and trade_dir == 'LONG':
        return False, 0
    return True, 0

def check_time_blackout():
    if CONFIG['backtest_mode']: return False
    now = datetime.now(); t = now.time()
    if time(9,15) <= t <= time(9,25): return True
    if time(12,0) <= t <= time(13,0): return True
    h = now.hour + now.minute / 60
    if h >= 14.5: return True
    return False

def calc_indicators(df):
    if df is None or len(df) < 50: return None
    close = df['Close'].astype(float); high = df['High'].astype(float)
    low = df['Low'].astype(float); vol = df['Volume'].astype(float)
    df['Typical'] = (high + low + close) / 3
    df['CumVol'] = vol.cumsum(); df['CumTP'] = (df['Typical'] * vol).cumsum()
    df['VWAP'] = df['CumTP'] / df['CumVol'].replace(0, 1)
    df['VWAP_std'] = close.rolling(20).std()
    st_period = 10; st_mult = 3
    hl2 = (high + low) / 2
    st_atr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1).rolling(st_period).mean()
    df['ST_upper'] = hl2 + st_mult * st_atr
    df['ST_lower'] = hl2 - st_mult * st_atr
    df['SuperTrend'] = 0
    for i in range(1, len(df)):
        prev_st = df['SuperTrend'].iloc[i-1]
        if close.iloc[i] > df['ST_upper'].iloc[i-1]:
            df.loc[df.index[i], 'SuperTrend'] = 1
        elif close.iloc[i] < df['ST_lower'].iloc[i-1]:
            df.loc[df.index[i], 'SuperTrend'] = -1
        else:
            df.loc[df.index[i], 'SuperTrend'] = prev_st
    for p in [1,2]: df['VWAP_u'+str(p)] = df['VWAP'] + p * df['VWAP_std']; df['VWAP_l'+str(p)] = df['VWAP'] - p * df['VWAP_std']
    for s in [5,9,13,21]: df['EMA'+str(s)] = close.ewm(span=s).mean()
    hilo = high - low; hic = abs(high - close.shift()); loc = abs(low - close.shift())
    df['ATR'] = pd.concat([hilo, hic, loc], axis=1).max(axis=1).rolling(14).mean()
    p_dm = high.diff(); n_dm = -low.diff()
    p_dm[p_dm < 0] = 0; n_dm[n_dm < 0] = 0
    atr_s = df['ATR'].replace(0, 1)
    pdi = 100 * (p_dm.rolling(14).mean() / atr_s)
    ndi = 100 * (n_dm.rolling(14).mean() / atr_s)
    df['ADX'] = (100 * abs(pdi - ndi) / (pdi + ndi + 1e-10)).rolling(14).mean()
    e12 = close.ewm(12).mean(); e26 = close.ewm(26).mean()
    df['MACD'] = e12 - e26; df['MACD_sig'] = df['MACD'].ewm(9).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_sig']
    delta = close.diff(); gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))
    df['VolMA5'] = vol.rolling(5).mean(); df['VolMA20'] = vol.rolling(20).mean()
    df['RVOL'] = vol / df['VolMA20'].replace(0, 1)
    df['Delta'] = close.diff() * vol; df['DeltaMA5'] = df['Delta'].rolling(5).mean()
    df['VPT'] = (close.pct_change() * vol).cumsum(); df['VPT_slope'] = df['VPT'].diff(5)
    df['BB_mid'] = close.rolling(20).mean(); df['BB_std'] = close.rolling(20).std()
    df['BB_u'] = df['BB_mid'] + 2 * df['BB_std']; df['BB_l'] = df['BB_mid'] - 2 * df['BB_std']
    return df

def predict_ml(df):
    if df is None or len(df) < 30: return 0, 0, True
    latest = df.iloc[-1]; momentum = latest['Close'] / df['Close'].iloc[-10] - 1
    vf = min(latest['RVOL'] / 3, 1) if 'RVOL' in df else 0.5
    lr = max(min(momentum * 100 * vf, 3), -3)
    ls = max(min(momentum * 95 * vf, 2.8), -2.8)
    stable = True
    if len(df) >= 18:
        c1 = (df['Close'].iloc[-2] / df['Close'].iloc[-7] - 1) * 100
        c2 = (df['Close'].iloc[-4] / df['Close'].iloc[-9] - 1) * 100
        same = (lr > 0 and c1 > 0 and c2 > 0) or (lr < 0 and c1 < 0 and c2 < 0)
        stable = same and abs(lr) > 0.2
    return round(lr, 2), round(ls, 2), stable

def _last_valid_row(df):
    """Get the last row with non-zero volume (skip incomplete bars)."""
    valid = df[df['Volume'] > 0]
    if len(valid) == 0: return df.iloc[-1]
    idx = df.index.get_loc(valid.index[-1])
    if idx < len(df) - 2:
        return df.iloc[-1]
    return valid.iloc[-1]

def analyze_signal(df, symbol, breadth, mkt_dir):
    if df is None or len(df) < 50: return None
    l = _last_valid_row(df); p = l['Close']; v = l['VWAP']; a = l['ADX']; at = l['ATR']
    rv = l['RVOL']; rs = l['RSI']; m5 = l['EMA5']; m13 = l['EMA13']; m21 = l['EMA21']
    mh = l['MACD_hist']; bb_u = l['BB_u']; bb_l = l['BB_l']; st = l.get('SuperTrend', 0)
    if isinstance(mkt_dir, tuple):
        mkt_dir_label, mkt_bias, mkt_strength = mkt_dir
    else:
        mkt_dir_label, mkt_bias, mkt_strength = mkt_dir, 'LONG', 0
    lr, ls_pred, ai_st = predict_ml(df)
    bw = check_time_blackout()

    # --- HARD GATES ---
    if a < CONFIG['adx_gate']: return None
    if rv < CONFIG['rvol_gate']: return None

    long_score = 0; long_factors = []; long_warnings = []
    short_score = 0; short_factors = []; short_warnings = []

    if p > v: long_score += 4; long_factors.append('VWAP+')
    if p > m5 > m13 > m21: long_score += 4; long_factors.append('EMA bullish')
    ema_dist = (p - m21) / at if at > 0 else 99
    if ema_dist < 1.5 and p > m21: long_score += 4; long_factors.append('Pullback')
    if ema_dist > 2.5: long_score -= 20; long_warnings.append('Extended')
    if a >= CONFIG['adx_min']: long_score += 3; long_factors.append('ADX')
    if CONFIG['use_supertrend']:
        if st == 1: long_score += 3; long_factors.append('ST+')
    if rs < CONFIG['rsi_long_max']: long_score += 3; long_factors.append('RSI')
    elif rs < CONFIG['rsi_long_max'] + 10: long_score += 1; long_factors.append('RSI mid')
    if rv >= CONFIG['rvol_min']: long_score += 2; long_factors.append('RVOL')
    if l['Delta'] > 0: long_score += 1; long_factors.append('D+')
    if mh > 0: long_score += 1; long_factors.append('MACD+')
    if lr >= CONFIG['ai_min_pct'] and ai_st: long_score += 3; long_factors.append('AI')
    oh = df.iloc[:3]['High'].max()
    if oh and p > oh: long_score += 2; long_factors.append('ORB+')
    adr = breadth['ad_ratio']; aema = breadth['above_ema_pct']
    if adr > 50 and aema > 45: long_score += 1; long_factors.append('B+')
    if p < bb_u: long_score += 1; long_factors.append('BB')
    lo_allowed, _ = check_direction('LONG', mkt_dir_label, mkt_strength)
    if not lo_allowed: long_score = 0; long_warnings.append('Mkt')

    if p < v: short_score += 4; short_factors.append('VWAP-')
    if p < m5 < m13 < m21: short_score += 4; short_factors.append('EMA bearish')
    ema_dist_short = (m21 - p) / at if at > 0 else 99
    if ema_dist_short < 1.5 and p < m21: short_score += 4; short_factors.append('Pullback')
    if ema_dist_short > 2.5: short_score -= 20; short_warnings.append('Extended')
    if a >= CONFIG['adx_min']: short_score += 3; short_factors.append('ADX')
    if CONFIG['use_supertrend']:
        if st == -1: short_score += 3; short_factors.append('ST-')
    if rs > 55: short_score += 3; short_factors.append('RSI')
    elif rs > 45: short_score += 1; short_factors.append('RSI mid')
    if rv >= CONFIG['rvol_min']: short_score += 2; short_factors.append('RVOL')
    if l['Delta'] < 0: short_score += 1; short_factors.append('D-')
    if mh < 0: short_score += 1; short_factors.append('MACD-')
    if lr <= -CONFIG['ai_min_pct'] and ai_st: short_score += 3; short_factors.append('AI')
    ol = df.iloc[:3]['Low'].min()
    if ol and p < ol: short_score += 2; short_factors.append('ORB-')
    if adr < 50 and aema < 55: short_score += 1; short_factors.append('B-')
    if p > bb_l: short_score += 1; short_factors.append('BB')
    sh_allowed, _ = check_direction('SHORT', mkt_dir_label, mkt_strength)
    if not sh_allowed: short_score = 0; short_warnings.append('Mkt')

    ms = CONFIG['min_score']; mxs = CONFIG['max_score']
    lo = long_score >= ms and long_score <= mxs and not bw
    so = short_score >= ms and short_score <= mxs and not bw and not CONFIG['long_only']
    entries = []
    if lo and so:
        if CONFIG['long_only']: entries.append(('LONG', long_score, long_factors, long_warnings))
        else: entries.append(('LONG', long_score, long_factors, long_warnings) if long_score > short_score else ('SHORT', short_score, short_factors, short_warnings))
    elif lo: entries.append(('LONG', long_score, long_factors, long_warnings))
    elif so: entries.append(('SHORT', short_score, short_factors, short_warnings))
    if not entries: return None

    d, sc, fac, wa = entries[0]; e = p
    asl = max(at * CONFIG['stop_atr'], e * CONFIG['stop_pct'] / 100)
    atg = max(at * CONFIG['target_atr'], e * CONFIG['target_pct'] / 100)
    if d == 'LONG': st = round(e - asl, 2); tg = round(e + atg, 2)
    else: st = round(e + asl, 2); tg = round(e - atg, 2)
    rr = round(atg / asl, 2) if asl > 0 else 1
    conf = min(99, round(sc * 5))
    sr = calc_support_resistance(df)
    mkt_sent = calc_market_sentiment((mkt_dir_label, mkt_bias, mkt_strength), breadth)
    return {'symbol': symbol, 'direction': d, 'entry': round(e, 2), 'stop': st, 'target': tg,
            'score': sc, 'conf': conf, 'rr': rr, 'factors': fac, 'warnings': wa,
            'adx': round(a, 1), 'rsi': round(rs, 1), 'rvol': round(rv, 1),
            'atr': round(at, 2), 'sr': sr, 'market_sentiment': mkt_sent}
