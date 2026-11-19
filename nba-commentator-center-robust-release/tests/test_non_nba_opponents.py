import datetime as dt
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import update_nba as u

class NonNbaOpponents(unittest.TestCase):
    def test_exhibition_and_placeholder_excluded(self):
        teams=[{'id':'1'},{'id':'2'}]
        games=[{'id':'nba','home':{'id':'1'},'away':{'id':'2'}},
               {'id':'exhibition','home':{'id':'1'},'away':{'id':'999'}},
               {'id':'placeholder','home':{'id':'1'},'away':{'id':'1'}},
               {'id':'missing','home':{'id':'1'},'away':{'id':''}}]
        kept,skipped=u.filter_nba_games(games,teams)
        self.assertEqual([g['id'] for g in kept],['nba'])
        self.assertEqual(skipped,['exhibition','placeholder','missing'])
    def test_normalized_non_nba_event_is_filtered(self):
        event={'id':'401914130','date':'2026-11-19T00:00:00Z',
          'competitions':[{'competitors':[
            {'homeAway':'home','team':{'id':'1','displayName':'NBA Team'}},
            {'homeAway':'away','team':{'id':'999','displayName':'Exhibition Team'}}]}]}
        game=u.normalize_event(event)
        kept,skipped=u.filter_nba_games([game],[{'id':'1'},{'id':'2'}])
        self.assertEqual(kept,[])
        self.assertEqual(skipped,['401914130'])
    def test_valid_games_preserved(self):
        game={'id':'real','home':{'id':'1'},'away':{'id':'2'}}
        kept,skipped=u.filter_nba_games([game],[{'id':'1'},{'id':'2'}])
        self.assertEqual(kept,[game]);self.assertEqual(skipped,[])

if __name__=='__main__':unittest.main()
