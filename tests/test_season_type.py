import unittest
from scripts import update_nba as n

class SeasonTypeTests(unittest.TestCase):
    def event(self,season):
        return {'id':'1','date':'2026-11-01T00:00Z','season':season,'status':{'type':{'completed':True}},'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'1'},'score':'99'},{'homeAway':'away','team':{'id':'2'},'score':'98'}]}]}
    def test_regular_season(self):
        self.assertEqual(n.normalize_event(self.event({'type':2}))['seasonType'],'2')
    def test_playoffs(self):
        self.assertEqual(n.normalize_event(self.event({'type':3}))['seasonType'],'3')
    def test_unknown_not_assumed_regular(self):
        self.assertEqual(n.normalize_event(self.event({}))['seasonType'],'')
if __name__=='__main__':unittest.main()
