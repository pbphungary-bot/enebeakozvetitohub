#!/usr/bin/env python3
"""Read-only probe of ESPN endpoints for player season stats, injuries, team stats, news and RSS.
Prints response SHAPES (keys/types/sample values) so the collector is built on real responses."""
import gzip
import json
import time
import urllib.error
import urllib.request

UA = 'Mozilla/5.0 (compatible; NBACommentatorCenter/1.0)'
BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
SITE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
WEB = 'https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba'
COMMON = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba'


def fetch(url, ua=UA):
    t = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(8_000_000)
            return r.status, body, time.time() - t, ''
    except urllib.error.HTTPError as e:
        body = e.read(500)
        if body[:2] == b'\x1f\x8b':
            body = gzip.decompress(body)
        return e.code, body, time.time() - t, f'HTTPError {e.code}'
    except Exception as e:
        return None, b'', time.time() - t, f'{type(e).__name__}: {e}'


def shape(x, depth=0, maxdepth=4, out=None, key=''):
    out = [] if out is None else out
    pad = '  ' * depth
    if isinstance(x, dict):
        out.append(f'{pad}{key}{{{len(x)} keys}}')
        if depth < maxdepth:
            for k, v in list(x.items())[:40]:
                shape(v, depth + 1, maxdepth, out, f'{k}: ')
    elif isinstance(x, list):
        out.append(f'{pad}{key}[{len(x)} items]')
        if x and depth < maxdepth:
            shape(x[0], depth + 1, maxdepth, out, 'item0: ')
    else:
        out.append(f'{pad}{key}{type(x).__name__} = {str(x)[:70]!r}')
    return out


def probe(label, url, maxdepth=3, ua=UA, show=60):
    status, body, took, err = fetch(url, ua)
    print(f'\n### {label}\nURL: {url}\nSTATUS: {status} ({took:.2f}s, {len(body)} bytes) {err}')
    try:
        data = json.loads(body)
    except Exception:
        print('NOT JSON:', body[:200])
        return None
    lines = shape(data, 0, maxdepth)
    print('\n'.join(lines[:show]))
    if len(lines) > show:
        print(f'... ({len(lines) - show} more lines)')
    return data


def probe_rss(label, url):
    for ua_name, ua in (('app UA', UA), ('browser UA', BROWSER)):
        status, body, took, err = fetch(url, ua)
        head = body[:160].decode('utf-8', 'replace').replace('\n', ' ')
        print(f'\n### RSS {label} [{ua_name}] -> {status} {len(body)} bytes {err}\n  {head!r}')
        if status == 200 and body:
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(body)
                items = root.findall('.//item')
                print(f'  items={len(items)} first={items[0].findtext("title") if items else None!r} link={items[0].findtext("link") if items else None!r}')
            except Exception as exc:
                print('  XML parse failed:', exc)


def main():
    team = '18'  # New York Knicks (id seen in live data)
    probe('team roster (one athlete shape)', f'{SITE}/teams/{team}/roster', maxdepth=3, show=40)
    for season in (2027, 2026):
        d = probe(f'byathlete league stats season={season} regular', f'{COMMON}/statistics/byathlete?region=us&lang=en&contentorigin=espn&isqualified=false&page=1&limit=50&sort=offensive.avgPoints%3Adesc&season={season}&seasontype=2', maxdepth=5, show=90)
    d = probe('athlete season stats (stats endpoint)', f'{COMMON}/athletes/4277919/stats', maxdepth=4, show=70)
    probe('athlete overview', f'{COMMON}/athletes/4277919/overview', maxdepth=3, show=50)
    probe('league injuries', f'{SITE}/injuries', maxdepth=5, show=60)
    probe('team injuries', f'{SITE}/teams/{team}/injuries', maxdepth=4, show=40)
    probe('team statistics (site)', f'{SITE}/teams/{team}/statistics', maxdepth=5, show=70)
    probe('team statistics (web, season)', f'{WEB}/teams/{team}/statistics?season=2027&seasontype=2', maxdepth=5, show=40)
    probe('byteam league stats', f'{COMMON}/statistics/byteam?region=us&lang=en&contentorigin=espn&sort=offensive.avgPoints%3Adesc&season=2027&seasontype=2', maxdepth=5, show=70)
    d = probe('team detail with roster/stats', f'{WEB}/teams/{team}?enable=roster,stats', maxdepth=3, show=40)
    news = probe('news (tagging structure)', f'{SITE}/news?limit=3', maxdepth=4, show=80)
    for a in ((news or {}).get('articles') or [])[:2]:
        print('CATEGORIES of one article:', json.dumps(a.get('categories'))[:900])
    for label, url in (('ESPN NBA', 'https://www.espn.com/espn/rss/nba/news'),
                       ('CBS NBA', 'https://www.cbssports.com/rss/headlines/nba/'),
                       ('Yahoo NBA', 'https://sports.yahoo.com/nba/rss/'),
                       ('NBA.com', 'https://www.nba.com/rss/nba_rss.xml'),
                       ('HoopsHype', 'https://hoopshype.com/feed/')):
        probe_rss(label, url)


if __name__ == '__main__':
    main()
