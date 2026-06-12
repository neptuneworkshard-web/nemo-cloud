"""Load credentials from env vars or credentials.env"""
import os

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.env')
_CACHE = {}

def _load():
    if _CACHE:
        return _CACHE
    d = {}
    try:
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    d[k.strip()] = v.strip()
    except:
        pass
    _CACHE.update(d)
    return d

def get(key, default=''):
    return os.environ.get(key, _load().get(key, default))

def telegram_token():
    return get('TELEGRAM_TOKEN')

def telegram_chat_id():
    return get('TELEGRAM_CHAT_ID')

def gemini_key():
    return get('GEMINI_API_KEY')
