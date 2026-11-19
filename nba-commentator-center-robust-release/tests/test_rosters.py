import unittest
from unittest.mock import patch
from scripts import update_nba as n
class RosterTests(unittest.TestCase):
    def test_flat_roster(self):
        with patch.object(n,'get',return_value={'athletes':[{'id':'7','displayName':'Test Player','jersey':'11','position':{'abbreviation':'PG'}}]}):
            self.assertEqual(n.roster('1')[0]['position'],'PG')
    def test_grouped_roster(self):
        with patch.object(n,'get',return_value={'athletes':[{'items':[{'id':'9','displayName':'Player Two'}]}]}):
            self.assertEqual(n.roster('1')[0]['id'],'9')
    def test_fallback_on_failure(self):
        with patch.object(n,'roster',side_effect=RuntimeError('network unavailable')):
            result,warnings=n.collect_rosters([{'id':'1','abbr':'BOS'}],{'1':[{'id':'8','name':'Cached'}]})
            self.assertEqual(result['1'][0]['name'],'Cached')
            self.assertEqual(len(warnings),1)
    def test_missing_roster_not_fabricated(self):
        with patch.object(n,'roster',side_effect=RuntimeError('network unavailable')):
            result,warnings=n.collect_rosters([{'id':'1','abbr':'BOS'}])
            self.assertNotIn('1',result)
            self.assertEqual(len(warnings),1)
if __name__=='__main__':unittest.main()
