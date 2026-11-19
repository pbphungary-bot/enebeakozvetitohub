import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from validate_data import validate

NOW = dt.datetime(2026, 11, 19, 10, tzinfo=dt.timezone.utc)

def sample():
    teams = [{'id': str(i)} for i in range(1, 31)]
    games = [{'id': str(i), 'date': '2026-11-18T20:00:00Z', 'completed': True,
              'home': {'id': str(i % 30 + 1), 'score': 100},
              'away': {'id': str((i + 1) % 30 + 1), 'score': 90}} for i in range(30)]
    return {'teams': teams, 'games': games, 'standings': {'1': {}},
            'rosters': {str(i): [{'id': 'p'}] for i in range(1, 31)},
            'seasonComplete': True, 'generatedAt': '2026-11-19T09:00:00Z'}

class DataValidationTests(unittest.TestCase):
    def test_valid_structure(self):
        self.assertEqual(validate(sample(), NOW), [])
    def test_duplicate_team(self):
        data = sample(); data['teams'][1]['id'] = '1'
        self.assertTrue(any('30 uniquely' in e for e in validate(data, NOW)))
    def test_bad_score(self):
        data = sample(); data['games'][0]['home']['score'] = None
        self.assertTrue(any('numeric scores' in e for e in validate(data, NOW)))
    def test_unknown_team(self):
        data = sample(); data['games'][0]['home']['id'] = '999'
        self.assertTrue(any('Unknown' in e for e in validate(data, NOW)))
    def test_stale(self):
        data = sample(); data['generatedAt'] = '2026-11-10T09:00:00Z'
        self.assertTrue(any('stale' in e for e in validate(data, NOW)))
    def test_incomplete_season(self):
        data = sample(); data['seasonComplete'] = False
        self.assertTrue(any('coverage' in e for e in validate(data, NOW)))

if __name__ == '__main__': unittest.main()
