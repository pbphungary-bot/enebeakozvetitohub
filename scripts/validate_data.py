#!/usr/bin/env python3
"""Fail release checks when NBA collection is structurally inconsistent."""
import argparse
import datetime as dt
import json
from pathlib import Path


MIN_REGULAR_SEASON_GAMES = 1200  # a full NBA regular season is 1,230 games


def history_sanity_problems(history, start, end):
    """Each completed season in the window must contain a plausible number of regular-season games.

    Used by the collector before it may claim complete history, and by the validator
    as a backstop for that claim.
    """
    problems = []
    try:
        first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    except (TypeError, ValueError):
        return ['History window missing or invalid']
    for year in range(first.year, last.year):
        lo, hi = f'{year}-10-01', f'{year + 1}-07-01'
        count = sum(1 for g in history if str(g.get('seasonType')) == '2' and lo <= str(g.get('date', ''))[:10] <= hi)
        if count < MIN_REGULAR_SEASON_GAMES:
            problems.append(f'Season {year}-{str(year + 1)[2:]} has only {count} regular-season games (expected ~1,230)')
    return problems


def _record(stats):
    try:
        return int(stats['wins']), int(stats['losses'])
    except (KeyError, TypeError, ValueError):
        return None


def standings_problems(data, team_ids):
    """Every team needs a conference, a division and an official record."""
    problems = []
    standings = data.get('standings') if isinstance(data.get('standings'), dict) else {}
    divisions = {}
    for tid in team_ids:
        entry = standings.get(tid)
        if not isinstance(entry, dict):
            problems.append(f'Team {tid} missing from standings')
            continue
        if not entry.get('conference'):
            problems.append(f'Team {tid} has no conference')
        if not entry.get('division'):
            problems.append(f'Team {tid} has no division')
        else:
            divisions.setdefault(entry['division'], set()).add(entry.get('conference'))
        if _record(entry.get('stats') or {}) is None:
            problems.append(f'Team {tid} has no official wins/losses')
    for name, conferences in divisions.items():
        if len(conferences) > 1:
            problems.append(f'Division {name} spans several conferences')
    return problems


def record_reconciliation_problems(data, tolerance=1):
    """Collected regular-season results must match ESPN's official W-L (within one in-flight game).

    Catches preseason leakage, missing days and duplicated games. Only meaningful when
    every current-season day was verified.
    """
    if not data.get('seasonComplete'):
        return []
    start = str(data.get('seasonStart', ''))
    tally = {}
    for g in data.get('games', []):
        if not g.get('completed') or str(g.get('seasonType')) != '2' or str(g.get('date', ''))[:10] < start:
            continue
        home, away = g.get('home', {}), g.get('away', {})
        if not isinstance(home.get('score'), int) or not isinstance(away.get('score'), int):
            continue
        hw = home['score'] > away['score']
        tally.setdefault(home.get('id'), [0, 0])[0 if hw else 1] += 1
        tally.setdefault(away.get('id'), [0, 0])[1 if hw else 0] += 1
    problems = []
    for tid, entry in (data.get('standings') or {}).items():
        official = _record((entry or {}).get('stats') or {})
        if official is None:
            continue
        w, l = tally.get(tid, [0, 0])
        if abs(w - official[0]) > tolerance or abs(l - official[1]) > tolerance:
            problems.append(f'Team {tid}: collected regular-season record {w}-{l} does not match official {official[0]}-{official[1]}')
    return problems


def season_stats_problems(data, team_ids):
    """Season stats and injuries may be empty (their sources can fail independently) but must be well-formed."""
    problems = []
    known = set(team_ids)
    for key in ('playerSeason', 'teamStats', 'injuries'):
        if not isinstance(data.get(key), dict):
            problems.append(f'{key} missing or malformed')
    team_stats = data.get('teamStats') if isinstance(data.get('teamStats'), dict) else {}
    if team_stats and len(team_stats) < 28:
        problems.append(f'Team statistics cover only {len(team_stats)} teams')
    for tid in list(team_stats) + list(data.get('injuries') if isinstance(data.get('injuries'), dict) else {}):
        if tid not in known:
            problems.append(f'Statistics or injuries reference unknown team {tid}')
    for tid, rows in (data.get('injuries') if isinstance(data.get('injuries'), dict) else {}).items():
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get('name') or not r.get('status') for r in rows):
            problems.append(f'Malformed injury rows for team {tid}')
    return problems


def history_problems(data):
    """Historical coverage may be partial, but it must never be claimed complete falsely."""
    problems = []
    if not isinstance(data.get('historyComplete'), bool):
        return ['historyComplete flag missing']
    if data['historyComplete']:
        if data.get('historyMissingCount'):
            problems.append('History marked complete but days are missing')
        problems.extend(history_sanity_problems(data.get('history', []), data.get('historyStart'), data.get('historyEnd')))
    elif not data.get('historyTotalDays'):
        problems.append('History coverage metadata missing (historyTotalDays)')
    return problems


def validate(data, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    errors = []
    teams = data.get('teams', [])
    ids = [str(t.get('id', '')) for t in teams if isinstance(t, dict)]
    if len(teams) != 30 or len(set(ids)) != 30 or not all(ids):
        errors.append('Expected exactly 30 uniquely identified NBA teams')
    games = data.get('games', [])
    if len(games) < 30:
        errors.append('Fewer than 30 schedule/results games')
    game_ids = set()
    for game in games:
        gid = str(game.get('id', ''))
        if not gid or gid in game_ids:
            errors.append(f'Missing/duplicate game ID: {gid}')
        game_ids.add(gid)
        home, away = game.get('home', {}), game.get('away', {})
        if home.get('id') not in ids or away.get('id') not in ids or home.get('id') == away.get('id'):
            errors.append(f'Unknown or identical competitors for game {gid} (home={home.get("id")}, away={away.get("id")})')
        if game.get('completed'):
            if not isinstance(home.get('score'), int) or not isinstance(away.get('score'), int):
                errors.append(f'Completed game {gid} lacks numeric scores')
        try:
            dt.datetime.fromisoformat(game['date'].replace('Z', '+00:00'))
        except (KeyError, ValueError, AttributeError):
            errors.append(f'Invalid date for game {gid}')
    try:
        generated = dt.datetime.fromisoformat(data['generatedAt'].replace('Z', '+00:00'))
        if generated.tzinfo is None:
            errors.append('generatedAt must have timezone')
        elif generated > now + dt.timedelta(minutes=10) or now - generated > dt.timedelta(hours=36):
            errors.append('NBA data is stale or dated in the future (>36h)')
    except (KeyError, ValueError, AttributeError):
        errors.append('Missing/invalid generatedAt')
    if not isinstance(data.get('standings'), dict) or not data['standings']:
        errors.append('No standings data available')
    else:
        errors.extend(standings_problems(data, ids))
    if not isinstance(data.get('rosters'), dict) or len(data['rosters']) < 28:
        errors.append('Rosters missing for more than two teams')
    if not data.get('seasonComplete'):
        missing = data.get('seasonMissingDays', [])
        covered = data.get('seasonDaysFetched', [])
        # A first-run ESPN response can omit individual days; retain an honest
        # incomplete flag in the JSON while allowing a useful partial snapshot.
        # Require enough verified days and a recently verified scoreboard.
        if not covered or len(covered) < 7 or len(missing) > max(5, len(covered) // 10):
            errors.append('Current-season game coverage is incomplete')
        else:
            try:
                recent = max(dt.date.fromisoformat(x) for x in covered)
                if (now.date() - recent).days > 2:
                    errors.append('Current-season game coverage is stale')
            except (ValueError, TypeError):
                errors.append('Invalid current-season coverage metadata')
    errors.extend(history_problems(data))
    errors.extend(season_stats_problems(data, ids))
    errors.extend(record_reconciliation_problems(data))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='?', default=str(Path(__file__).resolve().parents[1] / 'data/nba.json'))
    args = parser.parse_args()
    data = json.loads(Path(args.file).read_text(encoding='utf-8'))
    problems = validate(data)
    if problems:
        for problem in problems:
            print('FAIL:', problem)
        raise SystemExit(1)
    print(f"PASS: {len(data['teams'])} teams, {len(data['games'])} games; fresh and structurally valid")


if __name__ == '__main__':
    main()
