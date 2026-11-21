import unittest,sys,pathlib,datetime as dt
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import update_nba as m

class CacheSafetyTests(unittest.TestCase):
    def test_coverage_not_trusted_when_cached_games_absent(self):
        # Coverage metadata without cached results must not make days look verified.
        with patch.object(m,'get',side_effect=RuntimeError('offline')):
            r=m.collect_history(dt.date(2026,11,19),cached=[],cached_days=['2025-01-15','2025-01-16'],batch=10)
        self.assertEqual(r['games'],[])
        self.assertNotIn('2025-01-15',r['daysFetched'])
        self.assertIn('2025-01-15',r['missing'])
        self.assertTrue(r['failures'])
    def test_cached_boxscores_survive_a_failed_refresh_when_still_wanted(self):
        old={'oldgame':{'teams':[{'team':'A','labels':['PTS'],'players':[{'id':'p1'}]}]},'dropped':{'teams':[{'team':'A','labels':[],'players':[{'id':'p2'}]}]}}
        games=[{'id':'oldgame','date':'2026-11-17','completed':True,'seasonType':'2','home':{'id':'1'},'away':{'id':'2'}},
               {'id':'newgame','date':'2026-11-19','completed':True,'seasonType':'2','home':{'id':'1'},'away':{'id':'2'}}]
        with patch.object(m,'get',side_effect=RuntimeError('offline')):
            result,errors=m.collect_boxscores(games,old,per_team=10)
        self.assertIn('oldgame',result)        # cached, still within the window: kept despite the outage
        self.assertNotIn('dropped',result)     # not one of any team's recent games: no longer retained
        self.assertTrue(errors)

if __name__=='__main__':unittest.main()
