import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m


def summary(label_set=('MIN', 'PTS')):
    team = lambda name, pid: {'team': {'displayName': name}, 'statistics': [{'labels': list(label_set), 'athletes': [
        {'athlete': {'id': pid, 'displayName': 'P' + pid}, 'stats': ['30', '21']}, {'athlete': {'displayName': 'No id'}, 'stats': ['1', '1']}]}]}
    return {'boxscore': {'players': [team('Knicks', '7'), team('Wolves', '8')]}}


def game(gid, date, home, away, type_='2', completed=True):
    return {'id': gid, 'date': date, 'seasonType': type_, 'completed': completed, 'home': {'id': home}, 'away': {'id': away}}


class ParseTests(unittest.TestCase):
    def test_labels_are_stored_once_per_team_and_idless_rows_dropped(self):
        box = m.parse_boxscore(summary())
        self.assertEqual([t['team'] for t in box['teams']], ['Knicks', 'Wolves'])
        self.assertEqual(box['teams'][0], {'team': 'Knicks', 'labels': ['MIN', 'PTS'], 'players': [{'id': '7', 'name': 'P7', 'stats': ['30', '21']}]})
    def test_empty_summary_has_no_teams(self):
        self.assertEqual(m.parse_boxscore({}), {'teams': []})
    def test_legacy_flat_rows_are_converted_without_refetching(self):
        legacy = [{'team': 'Knicks', 'id': '7', 'name': 'A', 'stats': ['1'], 'labels': ['PTS']}, {'team': 'Knicks', 'id': '9', 'name': 'B', 'stats': ['2'], 'labels': ['PTS']},
                  {'team': 'Wolves', 'id': '8', 'name': 'C', 'stats': ['3'], 'labels': ['PTS']}]
        box = m.normalize_boxscore(legacy)
        self.assertEqual([(t['team'], [p['id'] for p in t['players']]) for t in box['teams']], [('Knicks', ['7', '9']), ('Wolves', ['8'])])
        self.assertEqual(box['teams'][0]['labels'], ['PTS'])
    def test_normalize_rejects_empty_and_keeps_current_shape(self):
        self.assertIsNone(m.normalize_boxscore([])); self.assertIsNone(m.normalize_boxscore(None)); self.assertIsNone(m.normalize_boxscore({'teams': []}))
        current = {'teams': [{'team': 'A', 'labels': [], 'players': [{'id': '1'}]}]}
        self.assertEqual(m.normalize_boxscore(current), current)


class WantedTests(unittest.TestCase):
    def test_each_team_keeps_only_its_most_recent_games(self):
        games = [game(str(d), f'2026-11-{d:02d}T00:00Z', 'A', 'B') for d in range(1, 6)] + [game('c1', '2026-11-06T00:00Z', 'C', 'D')]
        self.assertEqual(m.wanted_boxscore_ids(games, per_team=2), ['c1', '5', '4'])
    def test_a_game_is_kept_if_either_team_still_needs_it(self):
        games = [game('old', '2026-11-01T00:00Z', 'A', 'B'), game('mid', '2026-11-02T00:00Z', 'A', 'C'), game('new', '2026-11-03T00:00Z', 'A', 'C')]
        # A and C are full after new+mid; B only has 'old', so 'old' is still wanted for B.
        self.assertEqual(m.wanted_boxscore_ids(games, per_team=2), ['new', 'mid', 'old'])
    def test_preseason_unfinished_and_pre_season_start_games_are_excluded(self):
        games = [game('pre', '2026-10-05T00:00Z', 'A', 'B', type_='1'), game('live', '2026-11-05T00:00Z', 'A', 'B', completed=False),
                 game('june', '2026-06-20T00:00Z', 'A', 'B', type_='3'), game('ok', '2026-11-04T00:00Z', 'A', 'B')]
        self.assertEqual(m.wanted_boxscore_ids(games, per_team=10, season_start='2026-07-01'), ['ok'])
    def test_size_is_bounded_by_teams_times_per_team(self):
        games = [game(f'g{i}', f'2026-11-{i % 28 + 1:02d}T{i // 28:02d}:00Z', str(i % 30), str((i + 7) % 30)) for i in range(600)]
        self.assertLessEqual(len(m.wanted_boxscore_ids(games, per_team=10)), 30 * 10)


class CollectTests(unittest.TestCase):
    GAMES = [game('1', '2026-11-18T00:00Z', 'A', 'B'), game('2', '2026-11-19T00:00Z', 'A', 'B')]
    def test_cached_games_need_no_network_even_in_the_legacy_format(self):
        legacy = {'1': [{'team': 'A', 'id': '7', 'name': 'X', 'stats': ['2'], 'labels': ['PTS']}], '2': {'teams': [{'team': 'B', 'labels': ['PTS'], 'players': [{'id': '8'}]}]}}
        with patch.object(m, 'get', side_effect=AssertionError('network called')):
            data, errors = m.collect_boxscores(self.GAMES, legacy)
        self.assertEqual(errors, []); self.assertEqual(sorted(data), ['1', '2'])
        self.assertEqual(data['1']['teams'][0]['players'][0]['id'], '7')
    def test_games_outside_the_per_team_window_are_dropped_from_the_cache(self):
        cached = {'1': {'teams': [{'team': 'A', 'labels': [], 'players': [{'id': '1'}]}]}, '2': {'teams': [{'team': 'A', 'labels': [], 'players': [{'id': '2'}]}]}, 'ancient': {'teams': [{'team': 'A', 'labels': [], 'players': [{'id': '3'}]}]}}
        with patch.object(m, 'get', side_effect=AssertionError('network called')):
            data, _ = m.collect_boxscores(self.GAMES, cached, per_team=1)
        self.assertEqual(sorted(data), ['2'])
    def test_missing_games_are_fetched_newest_first_and_batched(self):
        urls = []
        with patch.object(m, 'get', side_effect=lambda u: urls.append(u) or summary()):
            data, errors = m.collect_boxscores(self.GAMES, None, batch=1)
        self.assertEqual(len(urls), 1); self.assertIn('event=2', urls[0])
        self.assertEqual(sorted(data), ['2'])
        self.assertTrue(any('1 more will be added on later refreshes' in e for e in errors))
    def test_failure_is_visible_and_nothing_is_invented(self):
        with patch.object(m, 'get', side_effect=RuntimeError('offline')):
            data, errors = m.collect_boxscores(self.GAMES, None)
        self.assertEqual(data, {}); self.assertIn('offline', errors[0])
    def test_empty_summary_is_not_cached(self):
        with patch.object(m, 'get', return_value={'boxscore': {'players': []}}):
            data, errors = m.collect_boxscores(self.GAMES[:1], None)
        self.assertEqual(data, {}); self.assertIn('no player box-score rows', errors[0])


if __name__ == '__main__': unittest.main()
