import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate_data import validate
from fixtures import valid_data, full_history

NOW = dt.datetime(2026, 11, 19, 10, tzinfo=dt.timezone.utc)
sample = lambda: valid_data(NOW)


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

    # --- P0.6: standings completeness
    def test_standings_must_cover_every_team(self):
        data = sample(); del data['standings']['7']
        self.assertTrue(any('Team 7 missing from standings' in e for e in validate(data, NOW)))
    def test_missing_division_is_rejected(self):
        data = sample(); data['standings']['3']['division'] = ''
        self.assertTrue(any('Team 3 has no division' in e for e in validate(data, NOW)))
    def test_missing_conference_is_rejected(self):
        data = sample(); data['standings']['3']['conference'] = ''
        self.assertTrue(any('Team 3 has no conference' in e for e in validate(data, NOW)))
    def test_missing_official_record_is_rejected(self):
        data = sample(); data['standings']['4']['stats'] = {}
        self.assertTrue(any('Team 4 has no official wins/losses' in e for e in validate(data, NOW)))
    def test_division_cannot_span_conferences(self):
        data = sample(); data['standings']['1']['conference'] = 'Western Conference'
        self.assertTrue(any('spans several conferences' in e for e in validate(data, NOW)))

    # --- P0.6: collected results must reconcile with official records
    def test_missing_regular_season_games_are_detected(self):
        data = sample(); data['games'] = data['games'][:20]  # teams now lack results
        data['standings']['1']['stats'].update(wins='5', losses='5')
        self.assertTrue(any('Team 1: collected' in e and 'does not match official' in e for e in validate(data, NOW)))
    def test_one_in_flight_game_is_tolerated(self):
        data = sample(); data['standings']['1']['stats'].update(wins='2', losses='1')
        self.assertFalse(any('does not match official' in e for e in validate(data, NOW)))
    def test_preseason_games_do_not_count_toward_reconciliation(self):
        data = sample()
        data['games'].append({'id': 'pre', 'date': '2026-10-05T00:00Z', 'completed': True, 'seasonType': '1',
                              'home': {'id': '1', 'score': 100}, 'away': {'id': '2', 'score': 90}})
        self.assertEqual(validate(data, NOW), [])

    # --- P0.6 / P0.1: history may be partial but never falsely complete
    def test_partial_history_is_allowed_when_flagged(self):
        self.assertEqual(validate(sample(), NOW), [])
    def test_history_flag_is_required(self):
        data = sample(); del data['historyComplete']
        self.assertTrue(any('historyComplete flag missing' in e for e in validate(data, NOW)))
    def test_complete_claim_with_missing_days_is_rejected(self):
        data = sample(); data.update(historyComplete=True, history=full_history(), historyMissingCount=3)
        self.assertTrue(any('days are missing' in e for e in validate(data, NOW)))
    def test_complete_claim_with_implausible_season_is_rejected(self):
        data = sample(); data.update(historyComplete=True, historyMissingCount=0, history=full_history(per_season=900))
        self.assertTrue(any('only 900 regular-season games' in e for e in validate(data, NOW)))
    def test_genuinely_complete_history_passes(self):
        data = sample(); data.update(historyComplete=True, historyMissingCount=0, history=full_history())
        self.assertEqual(validate(data, NOW), [])
    def test_partial_history_requires_coverage_metadata(self):
        data = sample(); data['historyTotalDays'] = 0
        self.assertTrue(any('coverage metadata missing' in e for e in validate(data, NOW)))


if __name__ == '__main__': unittest.main()
