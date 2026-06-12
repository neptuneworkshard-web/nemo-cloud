import requests, re
from bs4 import BeautifulSoup

SLUG_MAP = {
    'TCS': 'tata-consultancy-services',
    'HDFCBANK': 'hdfc-bank',
    'HINDUNILVR': 'hindustan-unilever',
    'SBIN': 'state-bank-of-india',
    'ICICIBANK': 'icici-bank',
    'BHARTIARTL': 'bharti-airtel',
    'KOTAKBANK': 'kotak-mahindra-bank',
    'BAJFINANCE': 'bajaj-finance',
    'LT': 'larsen-and-toubro',
    'AXISBANK': 'axis-bank',
    'MARUTI': 'maruti-suzuki',
    'M&M': 'mahindra-and-mahindra',
    'SUNPHARMA': 'sun-pharmaceutical',
    'HCLTECH': 'hcl-technologies',
    'ULTRACEMCO': 'ultratech-cement',
    'BAJAJFINSV': 'bajaj-finserv',
    'ASIANPAINT': 'asian-paints',
    'NESTLEIND': 'nestle-india',
    'TECHM': 'tech-mahindra',
    'BRITANNIA': 'britannia',
    'TATAMOTORS': 'tata-motors',
    'TATASTEEL': 'tata-steel',
    'JSWSTEEL': 'jsw-steel',
    'ADANIPORTS': 'adani-ports',
    'COALINDIA': 'coal-india',
    'HEROMOTOCO': 'hero-motocorp',
    'BAJAJ-AUTO': 'bajaj-auto',
    'DRREDDY': 'dr-reddys',
    'DIVISLAB': 'divi-s-laboratories',
    'APOLLOHOSP': 'apollo-hospitals',
    'HDFCLIFE': 'hdfc-life',
    'SBILIFE': 'sbi-life',
    'TATACONSUM': 'tata-consumer',
    'INDUSINDBK': 'indusind-bank',
    'EICHERMOT': 'eicher-motors',
    'POWERGRID': 'power-grid',
    'NTPC': 'ntpc',
    'ONGC': 'ongc',
    'GRASIM': 'grasim',
    'CIPLA': 'cipla',
    'DABUR': 'dabur',
    'MARICO': 'marico',
    'ADANIENT': 'adani-enterprises',
}

NOISE_WORDS = {'saturn', 'moon', 'methane', 'nasa', 'submarine', 'prebiotic',
               'bizarre chemistry', 'molecular bonds', 'frozen', 'solar system',
               'alien', 'space', 'ocean', 'icy crust', 'slushy',
               'titan hosts', 'titan story', 'titan movie',
               'entertainment', 'made in india'}
AMBIGUOUS = {'TITAN'}

POSITIVE = {'profit', 'surge', 'jump', 'rise', 'gain', 'growth', 'high', 'upgrad',
            'bullish', 'strong', 'beat', 'positive', 'record', 'rally', 'soar',
            'up', 'robust'}
NEGATIVE = {'loss', 'fall', 'decline', 'down', 'cut', 'weak', 'sell', 'bearish',
            'slump', 'drop', 'low', 'negative', 'warning', 'crash', 'pressure',
            'costlier', 'sell-off', 'halt'}

def to_slug(symbol):
    return SLUG_MAP.get(symbol, symbol.lower().replace('&', 'and'))

def classify(title):
    lower = title.lower()
    pos = sum(1 for w in POSITIVE if w in lower)
    neg = sum(1 for w in NEGATIVE if w in lower)
    if pos > neg:
        return 'positive'
    if neg > pos:
        return 'negative'
    return 'neutral'

def summarize(symbol, max_items=3):
    slug = to_slug(symbol)
    url = f'https://www.moneycontrol.com/news/tags/{slug}.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    seen_urls = set()
    results = []

    for h2 in soup.find_all('h2'):
        title = h2.get_text(strip=True)
        if not title or len(title) < 20:
            continue

        # Try to find associated article link
        parent = h2.find_parent('li') or h2.find_parent('div')
        a_tag = parent.find('a') if parent else None
        if not a_tag or not a_tag.get('href'):
            continue

        href = a_tag['href']
        if href.startswith('/'):
            href = 'https://www.moneycontrol.com' + href
        if 'moneycontrol.com/news/' not in href:
            continue
        if not re.search(r'\d{4,}', href):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        if symbol in AMBIGUOUS:
            lower = title.lower()
            if any(w in lower for w in NOISE_WORDS):
                continue

        results.append({'title': title, 'url': href, 'sentiment': classify(title)})
        if len(results) >= max_items:
            break

    return results
