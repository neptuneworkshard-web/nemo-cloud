"""Load credentials from env vars or credentials.env"""
import os

ENV_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.env'),
    os.path.expanduser('~/.config/opencode/credentials.env'),
]
_CACHE = {}

def _load():
    if _CACHE:
        return _CACHE
    d = {}
    for env_path in ENV_PATHS:
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, _, v = line.partition('=')
                        d[k.strip()] = v.strip().strip('"').strip("'")
        except OSError:
            continue
    _CACHE.update(d)
    return d

def get(key, default=''):
    return os.environ.get(key, _load().get(key, default))

def telegram_token():
    return get('TELEGRAM_TOKEN')

def telegram_chat_id():
    return get('TELEGRAM_CHAT_ID')

def telegram_chat():
    return telegram_chat_id()

def kotak_consumer_key():
    return get('KOTAK_CONSUMER_KEY')

def kotak_mobile_number():
    return get('KOTAK_MOBILE_NUMBER')

def kotak_ucc():
    return get('KOTAK_UCC')

def kotak_mpin():
    return get('KOTAK_MPIN')

def kotak_totp_secret():
    return get('KOTAK_TOTP_SECRET')

def gemini_key():
    return get('GEMINI_API_KEY')
