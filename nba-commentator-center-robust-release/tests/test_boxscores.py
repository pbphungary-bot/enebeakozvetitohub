import unittest
from unittest.mock import patch
from scripts.update_nba import parse_boxscore,collect_boxscores

class TestBoxscores(unittest.TestCase):
    def test_parse(self):
        raw={'boxscore':{'players':[{'team':{'displayName':'Knicks'},'statistics':[{'labels':['PTS'],'athletes':[{'athlete':{'id':'7','displayName':'Test Player'},'stats':['21']}]}]}]}}
        self.assertEqual(parse_boxscore(raw),[{'team':'Knicks','id':'7','name':'Test Player','stats':['21'],'labels':['PTS']}])
    def test_reuses_cache_without_network(self):
        games=[{'id':'1','date':'2026-11-18','completed':True}]
        with patch('scripts.update_nba.get',side_effect=AssertionError('network called')):
            data,errors=collect_boxscores(games,{'1':[{'id':'7'}]})
        self.assertEqual(data['1'],[{'id':'7'}]);self.assertEqual(errors,[])
    def test_failure_is_visible(self):
        with patch('scripts.update_nba.get',side_effect=RuntimeError('offline')):
            data,errors=collect_boxscores([{'id':'2','date':'2026-11-18','completed':True}])
        self.assertFalse(data);self.assertIn('offline',errors[0])
