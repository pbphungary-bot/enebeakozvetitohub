"""Shared synthetic datasets for tests. Never packaged as NBA data."""
import datetime as dt


def valid_data(now=None):
    """A structurally valid, internally consistent dataset (every team 1-1)."""
    now = now or dt.datetime(2026, 11, 19, 10, tzinfo=dt.timezone.utc)
    teams = [{'id': str(i), 'name': f'Team {i}', 'abbr': f'T{i}', 'division': f'Division {(i - 1) // 5}'} for i in range(1, 31)]
    games = [{'id': str(i), 'date': '2026-11-18T20:00:00Z', 'completed': True, 'seasonType': '2',
              'home': {'id': str(i % 30 + 1), 'score': 100}, 'away': {'id': str((i + 1) % 30 + 1), 'score': 90}} for i in range(30)]
    standings = {str(i): {'conference': 'Eastern Conference' if i <= 15 else 'Western Conference',
                          'division': f'Division {(i - 1) // 5}',
                          'stats': {'wins': '1', 'losses': '1', 'playoffSeed': str(i if i <= 15 else i - 15)}} for i in range(1, 31)}
    return {'teams': teams, 'games': games, 'standings': standings,
            'rosters': {str(i): [{'id': 'p'}] for i in range(1, 31)},
            'seasonComplete': True, 'seasonStart': '2026-07-01', 'generatedAt': (now - dt.timedelta(hours=1)).isoformat(),
            'history': [], 'historyComplete': False, 'historyTotalDays': 1093, 'historyMissingCount': 1093,
            'historyDaysFetched': [], 'historyStart': '2022-10-01', 'historyEnd': '2026-06-30'}


def full_history(start_year=2022, seasons=4, per_season=1230):
    """Plausible complete regular-season history for the validator's sanity check."""
    out = []
    for y in range(start_year, start_year + seasons):
        for n in range(per_season):
            out.append({'id': f'{y}-{n}', 'date': f'{y}-12-01T00:00Z', 'seasonType': '2',
                        'home': {'id': '1', 'score': 100}, 'away': {'id': '2', 'score': 90}})
    return out
