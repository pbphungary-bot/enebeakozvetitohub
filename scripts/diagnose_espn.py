#!/usr/bin/env python3
"""Read-only ESPN probe: prints real HTTP status/body details for each URL shape
the collector uses, so failures can be diagnosed from an Actions log.

Writes nothing. Usage: python scripts/diagnose_espn.py
"""
import collections
import json
import time
import urllib.error
import urllib.request

BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
CORE = 'https://site.web.api.espn.com/apis/v2/sports/basketball/nba'
UA = 'Mozilla/5.0 (compatible; NBACommentatorCenter/1.0)'
INTERESTING = ('retry-after', 'x-ratelimit', 'server', 'cf-', 'x-cache', 'via', 'content-type', 'content-length')


def probe(label, url, ua=UA):
    started = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept': 'application/json'})
    status, body, headers, err = None, b'', {}, ''
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            status, body, headers = r.status, r.read(5_000_000), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, headers = e.code, dict(e.headers)
        try:
            body = e.read(2000)
        except Exception:
            pass
        err = f'HTTPError {e.code} {e.reason}'
    except Exception as e:  # DNS, TLS, timeout...
        err = f'{type(e).__name__}: {e}'
    took = time.time() - started
    kept = {k: v for k, v in headers.items() if k.lower().startswith(INTERESTING)}
    print(f'\n### {label}\nURL: {url}\nSTATUS: {status}  ({took:.2f}s, {len(body)} bytes)  {err}')
    print('HEADERS:', json.dumps(kept))
    data = None
    try:
        data = json.loads(body)
    except Exception:
        print('BODY(not json):', body[:300])
    return status, data


def summarize_events(data):
    events = (data or {}).get('events')
    if not isinstance(events, list):
        print('EVENTS: missing/not a list; top-level keys:', sorted((data or {}).keys())[:15])
        return
    types = collections.Counter(str((e.get('season') or {}).get('type')) for e in events)
    dates = sorted(e.get('date', '')[:10] for e in events)
    status = collections.Counter(((e.get('status') or {}).get('type') or {}).get('name') for e in events)
    print(f'EVENTS: {len(events)}  seasonTypes={dict(types)}  status={dict(status)}')
    if dates:
        print(f'DATES: {dates[0]} .. {dates[-1]}  distinct={len(set(dates))}')
    print('PAGE META:', {k: data.get(k) for k in ('leagues',) if k in data and k != 'leagues'},
          'day' , data.get('day'))


def tree(node, depth=0, out=None, limit=60):
    out = [] if out is None else out
    if isinstance(node, dict) and len(out) < limit:
        name = node.get('name') or node.get('abbreviation')
        entries = len((node.get('standings') or {}).get('entries', []) or [])
        if name or entries:
            out.append(f"{'  ' * depth}{name!r} entries={entries}")
        for c in node.get('children', []) or []:
            tree(c, depth + 1, out, limit)
    return out


def main():
    scoreboard = BASE + '/scoreboard?'
    cases = [
        ('single day, regular season (what current-season fetch uses)', scoreboard + 'dates=20250115&limit=100'),
        ('single day, play-in', scoreboard + 'dates=20250415&limit=100'),
        ('single day, playoffs', scoreboard + 'dates=20250420&limit=100'),
        ('single day, NBA Finals', scoreboard + 'dates=20250619&limit=100'),
        ('single day, no games (offseason)', scoreboard + 'dates=20250815&limit=100'),
        ('collector history URL: month range, limit=1000', scoreboard + 'dates=20250101-20250131&limit=1000'),
        ('month range, limit=100', scoreboard + 'dates=20250101-20250131&limit=100'),
        ('month range, no limit', scoreboard + 'dates=20250101-20250131'),
        ('one-week range, no limit', scoreboard + 'dates=20250113-20250119'),
        ('season-year parameter', scoreboard + 'season=2025&seasontype=2&limit=1000'),
        ('whole history month failing in prod: 2022-10', scoreboard + 'dates=20221001-20221031&limit=1000'),
        ('previous-season single day', scoreboard + 'dates=20221025&limit=100'),
    ]
    for label, url in cases:
        status, data = probe(label, url)
        if status == 200:
            summarize_events(data)
    probe('same month URL, browser-like UA', scoreboard + 'dates=20250101-20250131&limit=1000',
          ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36')
    for level in (2, 3, 4):
        status, data = probe(f'standings level={level}', CORE + f'/standings?level={level}&sort=playoffseed%3Aasc')
        if status == 200:
            print('\n'.join(tree(data)))
    status, data = probe('team list (division field?)', BASE + '/teams?limit=100')
    if status == 200:
        try:
            t = data['sports'][0]['leagues'][0]['teams'][0]['team']
            print('TEAM KEYS:', sorted(t.keys()))
        except Exception as exc:
            print('team shape unexpected:', exc)


if __name__ == '__main__':
    main()
