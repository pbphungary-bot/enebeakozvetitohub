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
    print('--- P1 coverage')
    roster_ids = {p['id'] for rows in d.get('rosters', {}).values() for p in rows}
    season = d.get('playerSeason', {})
    print(f"playerSeason: {len(season)} players; rostered players with season stats: {len(roster_ids & set(season))} of {len(roster_ids)}")
    sample = next(iter(season.items()), None)
    print('  sample player:', sample)
    ts = d.get('teamStats', {})
    blanks = {k: sum(1 for v in ts.values() if v.get(k) is None) for k in (next(iter(ts.values())).keys() if ts else [])}
    print(f"teamStats: {len(ts)} teams; teams missing each field: { {k: n for k, n in blanks.items() if n} or 'none' }")
    print('  sample team:', next(iter(ts.items()), None))
    inj = d.get('injuries', {})
    print(f"injuries: {sum(len(v) for v in inj.values())} players across {len(inj)} teams; asOf={d.get('injuriesAsOf')}")
    news = d.get('news', [])
    team_ids = {t['id'] for t in d.get('teams', [])}
    tagged = [a for a in news if a.get('teamIds')]
    bad = [a for a in tagged if not set(a['teamIds']) <= team_ids]
    print(f"news: {len(news)} articles, {len(tagged)} team-tagged, {len(bad)} with an invalid team id; sources={dict(collections.Counter(a.get('source') for a in news))}")
    print('  sample tagged:', next(((a['title'][:70], a['teamIds']) for a in tagged), None))
    print('  sample title decoded (no entities):', not any('&#' in a.get('title', '') or '&amp;' in a.get('title', '') for a in news))
    boxes = d.get('boxscores', {})
    size_kb = len(json.dumps(boxes, separators=(',', ':'))) / 1024
    per_team = collections.Counter()
    games_by_id = {g['id']: g for g in d.get('games', [])}
    for gid in boxes:
        g = games_by_id.get(gid)
        if g:
            per_team[g['home']['id']] += 1
            per_team[g['away']['id']] += 1
    print(f"boxscores: {len(boxes)} games, {size_kb:.0f} KB; max games kept for one team={max(per_team.values(), default=0)}; "
          f"shape ok={all(isinstance(b, dict) and b.get('teams') for b in boxes.values())}")
    print('warnings:')
    for w in d.get('warnings', []):
        print('  -', w[:400])


if __name__ == '__main__':
    main(sys.argv[1])
