import unittest, pathlib, importlib.util
from unittest.mock import patch
import datetime as dt
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('nba_incremental',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class IncrementalTests(unittest.TestCase):
 def test_cached_old_month_skips_fetch(self):
  game={'id':'123','date':'2025-11-03T00:00:00Z','completed':True}
  with patch.object(m,'get',return_value={'events':[]}) as fetch:
   games,errors=m.historical_games(dt.date(2026,11,19),years=1,cached=[game],cached_months=["2025-11"])
  self.assertEqual(errors,[])
  self.assertIn('123',[g['id'] for g in games])
  self.assertFalse(any('202511' in call.args[0] for call in fetch.call_args_list))
 def test_recent_month_refetched(self):
  with patch.object(m,'get',return_value={'events':[]}) as fetch:
   m.historical_games(dt.date(2026,11,19),years=1,cached=[])
  self.assertGreaterEqual(fetch.call_count,1)
if __name__=='__main__':unittest.main()
