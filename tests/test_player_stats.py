import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_nba import aggregate_player_stats

class PlayerStatsTests(unittest.TestCase):
    def test_only_current_season_and_team_matched(self):
        games=[{'id':'a','completed':True,'date':'2026-11-01T00:00Z','home':{'id':'1','name':'Alpha'},'away':{'id':'2','name':'Beta'}},
               {'id':'b','completed':True,'date':'2025-01-01T00:00Z','home':{'id':'1','name':'Alpha'},'away':{'id':'2','name':'Beta'}}]
        rows={'a':[{'team':'Alpha','id':'77','labels':['PTS','REB','AST'],'stats':['20','10','5']},
                   {'team':'Beta','id':'88','labels':['PTS','REB','AST'],'stats':['8','2','3']}],
              'b':[{'team':'Alpha','id':'77','labels':['PTS','REB','AST'],'stats':['100','20','15']}]}
        result=aggregate_player_stats(rows,games,dt.date(2026,7,1))
        self.assertEqual(result['1']['77'],{'games':1,'pts':20.0,'reb':10.0,'ast':5.0})
        self.assertEqual(result['2']['88']['pts'],8.0)
    def test_missing_stats_never_fabricated(self):
        games=[{'id':'a','completed':True,'date':'2026-11-01','home':{'id':'1','name':'Alpha'},'away':{'id':'2','name':'Beta'}}]
        rows={'a':[{'team':'Alpha','id':'77','labels':['PTS'],'stats':['12']}]}
        result=aggregate_player_stats(rows,games,dt.date(2026,7,1))
        self.assertIsNone(result['1']['77']['reb'])
        self.assertIsNone(result['1']['77']['ast'])

if __name__=='__main__':unittest.main()
