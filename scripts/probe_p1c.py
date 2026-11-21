#!/usr/bin/env python3
"""Read-only: why does the player season-stats parser keep so few of ESPN's athletes?"""
import collections
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import update_nba as m


def main():
    url = m.COMMON + '/statistics/byathlete?' + m.stats_query(2027, isqualified='false', page=1, limit=500)
    print('URL', url)
    raw = m.get(url)
    athletes = raw.get('athletes', [])
    print('pagination', raw.get('pagination'))
    print('athletes', len(athletes))
    shapes = collections.Counter()
    reasons = collections.Counter()
    for entry in athletes:
        ath = entry.get('athlete') or {}
        cats = entry.get('categories') or []
        shapes[tuple((c.get('name'), len(c.get('values') or [])) for c in cats)] += 1
        pid = str(ath.get('id', ''))
        v = m.stat_values(raw.get('categories'), cats)
        gen = v.get(('general', 'all'), {})
        reasons['no id' if not pid else 'no general.gamesPlayed' if not gen.get('gamesPlayed') else 'ok'] += 1
    print('reasons', dict(reasons))
    print('category shapes (name,len(values)) -> count:')
    for shape, n in shapes.most_common(8):
        print(' ', n, shape)
    print('root category names/lens:', [(c.get('name'), len(c.get('names') or [])) for c in raw.get('categories', [])])
    for i in (0, 1, 2, 100, 400):
        if i < len(athletes):
            e = athletes[i]
            print(f'athlete[{i}]', (e.get('athlete') or {}).get('displayName'), 'keys', sorted(e.keys()),
                  [(c.get('name'), c.get('splitId'), len(c.get('values') or [])) for c in e.get('categories', [])])
    print('parsed:', len(m.player_season_stats(2027)), 'players')


if __name__ == '__main__':
    main()
