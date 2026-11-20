#!/usr/bin/env python3
"""Print a human-readable coverage summary of a collected nba.json (read-only)."""
import collections
import json
import sys


def main(path):
    d = json.load(open(path, encoding='utf-8'))
    print(f"generatedAt={d.get('generatedAt')} season={d.get('season')} teams={len(d.get('teams', []))} games={len(d.get('games', []))}")
    print(f"history: games={len(d.get('history', []))} daysVerified={len(d.get('historyDaysFetched', []))}/{d.get('historyTotalDays')} "
          f"missing={d.get('historyMissingCount')} complete={d.get('historyComplete')} window={d.get('historyStart')}..{d.get('historyEnd')}")
    by_season = collections.Counter()
    for g in d.get('history', []):
        date = g['date'][:10]
        year = int(date[:4]) if date[5:7] >= '07' else int(date[:4]) - 1
        by_season[(f'{year}-{str(year + 1)[2:]}', g.get('seasonType'))] += 1
    for key in sorted(by_season):
        print(f'  history {key[0]} type {key[1]!r}: {by_season[key]} games')
    st = d.get('standings', {})
    print('divisions:', dict(collections.Counter(v.get('division') for v in st.values())))
    print('conferences:', dict(collections.Counter(v.get('conference') for v in st.values())))
    sample = next(iter(st.values()), {})
    print('sample standings stats keys:', sorted((sample.get('stats') or {}).keys()))
    print('division ranks sample:', [v['stats'].get('divisionRank') for v in list(st.values())[:8]])
    print('game seasonTypes:', dict(collections.Counter(g.get('seasonType') for g in d.get('games', []))))
    print('warnings:')
    for w in d.get('warnings', []):
        print('  -', w[:400])


if __name__ == '__main__':
    main(sys.argv[1])
