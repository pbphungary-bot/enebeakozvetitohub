"""Run the real collector main() against a synthetic ESPN and check the result passes the validator."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m
from validate_data import validate

TODAY = dt.date(2026, 11, 20)
IDS = [str(i) for i in range(1, 31)]


def event(eid, home, away, day, type_=2, hs=100, as_=90):
    team = lambda t: {'id': t, 'displayName': f'Team {t}', 'abbreviation': f'T{t}', 'logo': ''}
    return {'id': eid, 'date': f'{day}T20:00Z', 'season': {'type': type_},
            'status': {'type': {'name': 'STATUS_FINAL', 'completed': True, 'shortDetail': 'Final'}},
            'competitions': [{'competitors': [{'homeAway': 'home', 'score': str(hs), 'team': team(home)},
                                              {'homeAway': 'away', 'score': str(as_), 'team': team(away)}]}]}


class FakeEspn:
    """Serves single-day scoreboards only; date ranges answer 400 like the real API."""
    def __init__(self):
        self.calls = []
        self.days = {}
        self.wins = {i: 0 for i in IDS}
        self.losses = {i: 0 for i in IDS}
        # Current season: 15 games a day between rotating pairs; three preseason days.
        d = dt.date(2026, 10, 3)
        while d < TODAY:
            k = (d - dt.date(2026, 10, 3)).days
            preseason = d in (dt.date(2026, 10, 3), dt.date(2026, 10, 5), dt.date(2026, 10, 7))
            regular = d >= dt.date(2026, 10, 21)
            if preseason or regular:
                order = IDS[k % 30:] + IDS[:k % 30]
                for j in range(15):
                    h, a = order[j], order[j + 15]
                    self.days.setdefault(d.isoformat(), []).append(event(f'c{d}-{j}', h, a, d.isoformat(), 1 if preseason else 2))
                    if not preseason:
                        self.wins[h] += 1; self.losses[a] += 1
            d += dt.timedelta(days=1)
        # Completed seasons: five games a day, every day of the Oct-Jun window.
        for day in m.history_days(TODAY, 4):
            self.days[day.isoformat()] = [event(f'h{day}-{n}', IDS[2 * n], IDS[2 * n + 1], day.isoformat(), 3 if day.month == 6 else 2) for n in range(5)]

    def __call__(self, url):
        self.calls.append(url)
        if '/scoreboard' in url:
            dates = url.split('dates=')[1].split('&')[0]
            if '-' in dates:
                raise RuntimeError(f'Could not fetch {url}: HTTP 400 Bad Request')
            return {'events': self.days.get(f'{dates[:4]}-{dates[4:6]}-{dates[6:]}', [])}
        if '/teams?limit' in url:
            return {'sports': [{'leagues': [{'teams': [{'team': {'id': i, 'displayName': f'Team {i}', 'abbreviation': f'T{i}', 'logos': [{'href': ''}]}} for i in IDS]}]}]}
        if '/standings' in url:
            def team_entry(i, seed):
                return {'team': {'id': i}, 'stats': [{'name': 'wins', 'displayValue': str(self.wins[i])}, {'name': 'losses', 'displayValue': str(self.losses[i])}, {'name': 'playoffSeed', 'displayValue': str(seed)}]}
            def conference(name, ids):
                divs = [{'name': f'{name[:1]}-Div{n}', 'standings': {'entries': [team_entry(i, ids.index(i) + 1) for i in ids[5 * n:5 * n + 5]]}} for n in range(3)]
                return {'name': f'{name} Conference', 'children': divs}
            return {'name': 'NBA', 'children': [conference('East', IDS[:15]), conference('West', IDS[15:])]}
        if '/roster' in url:
            tid = url.split('/teams/')[1].split('/')[0]
            return {'athletes': [{'id': 'p' + tid, 'displayName': 'Player ' + tid}]}
        if '/summary' in url:
            return {'boxscore': {'players': []}}
        if '/news' in url:
            return {'articles': []}
        raise AssertionError('unexpected url ' + url)


def run(output, fake, *extra):
    argv = ['update_nba.py', '--date', TODAY.isoformat(), '--output', str(output), *extra]
    with patch.object(m, 'get', fake), patch.object(m, 'rss_news', return_value=[]), patch.object(sys, 'argv', argv), patch('builtins.print'):
        m.main()
    return json.loads(pathlib.Path(output).read_text(encoding='utf-8'))


def history_days_fetched(fake):
    window = {d.strftime('%Y%m%d') for d in m.history_days(TODAY, 4)}
    return [u for u in fake.calls if '/scoreboard' in u and u.split('dates=')[1].split('&')[0] in window]


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = pathlib.Path(self.tmp.name) / 'nba.json'

    def test_full_backfill_in_one_run_is_complete_and_valid(self):
        data = run(self.out, FakeEspn(), '--history-batch', '0')
        self.assertTrue(data['historyComplete'])
        self.assertEqual(data['historyMissingCount'], 0)
        self.assertEqual(len(data['history']), 1093 * 5)
        self.assertEqual(validate(data), [])
        self.assertTrue(all(t['division'] for t in data['teams']))
        self.assertEqual({g['seasonType'] for g in data['history']}, {'2', '3'})

    def test_default_batch_publishes_honest_partial_history_then_resumes(self):
        fake = FakeEspn()
        first = run(self.out, fake)
        self.assertFalse(first['historyComplete'])
        self.assertEqual(len(first['historyDaysFetched']), 250)
        self.assertEqual(first['historyMissingCount'], 1093 - 250)
        self.assertEqual(validate(first), [], 'partial history must remain publishable')
        self.assertTrue(any('Historical coverage incomplete' in w for w in first['warnings']))
        fake2 = FakeEspn()
        second = run(self.out, fake2)
        self.assertEqual(len(second['historyDaysFetched']), 500)
        fetched_before = {u for u in history_days_fetched(fake)}
        self.assertFalse(fetched_before & set(history_days_fetched(fake2)), 'verified days were fetched again')
        self.assertEqual(validate(second), [])

    def test_current_season_records_reconcile_with_official_standings(self):
        data = run(self.out, FakeEspn(), '--history-batch', '1')
        self.assertEqual([e for e in validate(data) if 'does not match official' in e], [])
        pre = [g for g in data['games'] if g['seasonType'] == '1']
        self.assertTrue(pre, 'fixture should contain preseason games that must not distort records')

    def test_collector_refuses_to_call_a_thin_history_complete(self):
        fake = FakeEspn()
        for day in m.history_days(TODAY, 4):  # only ~700 regular-season games per season
            fake.days[day.isoformat()] = fake.days[day.isoformat()][:3]
        data = run(self.out, fake, '--history-batch', '0')
        self.assertEqual(data['historyMissingCount'], 0)
        self.assertFalse(data['historyComplete'])
        self.assertTrue(any('History sanity' in w for w in data['warnings']))
        self.assertEqual(validate(data), [])


if __name__ == '__main__': unittest.main()
