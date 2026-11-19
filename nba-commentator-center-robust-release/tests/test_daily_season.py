import datetime as dt
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('nba_daily',ROOT/'scripts'/'update_nba.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DailySeasonTests(unittest.TestCase):
    def test_empty_verified_days_count_as_covered(self):
        with patch.object(mod,'get',return_value={'events':[]}):
            games,covered,errors,missing=mod.current_season_games(dt.date(2026,11,3),dt.date(2026,11,1))
        self.assertEqual(len(covered),3)
        self.assertEqual((games,errors,missing),([],[],[]))

    def test_missing_events_not_accepted(self):
        with patch.object(mod,'get',return_value={}):
            _,covered,errors,missing=mod.current_season_games(dt.date(2026,11,2),dt.date(2026,11,1))
        self.assertEqual(covered,[])
        self.assertEqual(len(errors),2)
        self.assertEqual(len(missing),2)

    def test_old_verified_days_reused_and_recent_days_refreshed(self):
        old={'id':'a','date':'2026-11-01T00:00:00Z','completed':True}
        with patch.object(mod,'get',return_value={'events':[]}) as request:
            games,covered,errors,missing=mod.current_season_games(
                dt.date(2026,11,6),dt.date(2026,11,1),cached=[old],
                cached_days=['2026-11-01','2026-11-02','2026-11-03'])
        self.assertEqual(request.call_count,3)
        self.assertEqual(len(covered),6)
        self.assertEqual(games,[old])
        self.assertFalse(errors or missing)

    def test_failed_recent_refresh_keeps_verified_day(self):
        old={'id':'a','date':'2026-11-01T00:00:00Z','completed':True}
        with patch.object(mod,'get',side_effect=RuntimeError('rate limited')):
            _,covered,errors,missing=mod.current_season_games(
                dt.date(2026,11,1),dt.date(2026,11,1),cached=[old],cached_days=['2026-11-01'])
        self.assertEqual(covered,['2026-11-01'])
        self.assertFalse(errors or missing)

if __name__=='__main__':unittest.main()
