import unittest,sys,pathlib,datetime as dt
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import update_nba as m

class CacheSafetyTests(unittest.TestCase):
    def test_coverage_not_trusted_when_cached_games_absent(self):
        with patch.object(m,'get',side_effect=RuntimeError('offline')):
            games, failures=m.historical_games(dt.date(2026,11,19),years=1,cached=[],cached_months=['2025-07','2025-08'],refresh_months=2)
        self.assertEqual(games,[])
        self.assertIn('2025-07',m.historical_games.last_missing_months)
        self.assertTrue(failures)
    def test_current_month_failed_refresh_not_marked_complete(self):
        with patch.object(m,'get',side_effect=RuntimeError('offline')):
            m.historical_games(dt.date(2026,11,19),years=1,cached=[],cached_months=['2026-11'],refresh_months=2)
        self.assertIn('2026-11',m.historical_games.last_missing_months)
    def test_cached_boxscores_are_retained(self):
        old={'oldgame':[{'id':'p1','name':'Player'}]}
        games=[{'id':'newgame','date':'2026-11-19','completed':True}]
        with patch.object(m,'get',side_effect=RuntimeError('offline')):
            result,errors=m.collect_boxscores(games,old,max_games=25)
        self.assertIn('oldgame',result)
        self.assertTrue(errors)

if __name__=='__main__':unittest.main()
