#!/usr/bin/env python3
"""Read-only: stat label definitions for league player/team stats, and injury detail fields."""
import collections
import json
import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from probe_p1 import fetch, COMMON, SITE


def get(url):
    status, body, took, err = fetch(url)
    print(f'STATUS {status} {len(body)} bytes {took:.2f}s {err}')
    return json.loads(body) if status == 200 else None


def show_categories(label, d):
    print(f'\n##### {label}: root keys', sorted(d.keys()))
    for c in d.get('categories', []):
        print(' ROOT CATEGORY', c.get('name'), '| names:', c.get('names'), '| labels:', c.get('labels'), '| displayNames:', c.get('displayNames'))


def main():
    base = f'{COMMON}/statistics/byathlete?region=us&lang=en&contentorigin=espn&isqualified=false&sort=offensive.avgPoints%3Adesc&season=2027&seasontype=2'
    print('--- byathlete limit=500')
    d = get(base + '&page=1&limit=500')
    if d:
        print('pagination', d.get('pagination', {}).get('count'), 'pages', d.get('pagination', {}).get('pages'), 'athletes on page', len(d['athletes']))
        show_categories('byathlete', d)
        a = d['athletes'][0]
        print('athlete', a['athlete']['displayName'], 'teamId', a['athlete'].get('teamId'))
        for c in a['categories']:
            print(' ATHLETE CATEGORY', c.get('name'), 'values:', c.get('values'), 'totals:', c.get('totals'))
        print('sort', d.get('sort'))
        ids = [x['athlete']['id'] for x in d['athletes']]
        print('unique ids', len(set(ids)), 'of', len(ids))
    print('\n--- byteam')
    t = get(f'{COMMON}/statistics/byteam?region=us&lang=en&contentorigin=espn&sort=offensive.avgPoints%3Adesc&season=2027&seasontype=2')
    if t:
        show_categories('byteam', t)
        e = t['teams'][0]
        print('team', e['team']['displayName'])
        for c in e['categories']:
            print(' TEAM CATEGORY', c.get('name'), 'splitId', c.get('splitId'), 'values:', c.get('values'), 'totals:', c.get('totals'))
    print('\n--- team statistics (site)')
    s = get(f'{SITE}/teams/18/statistics')
    if s:
        for c in s['results']['stats']['categories']:
            print(' ', c['name'], [(x.get('name'), x.get('displayValue')) for x in c.get('stats', [])])
    print('\n--- injuries')
    inj = get(f'{SITE}/injuries')
    if inj:
        flat = [i for team in inj['injuries'] for i in team['injuries']]
        print('teams', len(inj['injuries']), 'injury rows', len(flat))
        print('status counts', dict(collections.Counter(i.get('status') for i in flat)))
        print('team ids/names sample', [(x['id'], x['displayName']) for x in inj['injuries'][:3]])
        print('one row:', json.dumps(flat[0])[:1500])
        print('type counts', dict(collections.Counter(json.dumps(i.get('type'), sort_keys=True)[:80] for i in flat).most_common(5)))
        print('details sample', json.dumps(flat[0].get('details')), json.dumps(flat[5].get('details')))


if __name__ == '__main__':
    main()
