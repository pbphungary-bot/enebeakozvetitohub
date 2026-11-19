#!/usr/bin/env python3
"""Fail release checks when NBA collection is structurally inconsistent."""
import argparse
import datetime as dt
import json
from pathlib import Path


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
            errors.append(f'Unknown or identical competitors for game {gid}')
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
