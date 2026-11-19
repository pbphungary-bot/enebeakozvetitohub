import datetime as dt
import importlib.util
import pathlib
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts'/'update_nba.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class CoverageIntegrity(unittest.TestCase):
    def test_month_without_events_is_not_marked_fetched(self):
        with patch.object(mod,'get',return_value={}):
            games,failures=mod.historical_games(dt.date(2026,11,19),years=1)
        self.assertEqual(games,[])
        self.assertGreater(len(failures),0)
        self.assertEqual(mod.historical_games.last_fetched_months,[])
        self.assertIn('2026-11',mod.historical_games.last_missing_months)
    def test_complete_empty_month_is_acceptable(self):
        with patch.object(mod,'get',return_value={'events':[]}):
            games,failures=mod.historical_games(dt.date(2026,11,19),years=1)
        self.assertFalse(failures)
        self.assertFalse(mod.historical_games.last_missing_months)
    def test_cached_months_do_not_claim_missing_months(self):
        with patch.object(mod,'get',return_value={'events':[]}):
            mod.historical_games(dt.date(2026,11,19),years=1,cached_months=['2025-07','2025-08'])
        self.assertFalse(mod.historical_games.last_missing_months)
if __name__=='__main__':unittest.main()
