import importlib.util, pathlib, unittest
from unittest.mock import patch
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('parallel_collector',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ParallelFetchTests(unittest.TestCase):
    def test_parallel_roster_success_and_cached_fallback(self):
        teams=[{'id':'1','abbr':'ONE'},{'id':'2','abbr':'TWO'},{'id':'3','abbr':'THR'}]
        def fetch(tid):
            if tid=='2':raise RuntimeError('offline')
            return [{'id':'p'+tid}]
        with patch.object(m,'roster',side_effect=fetch):
            result,warnings=m.collect_rosters(teams,{'2':[{'id':'cached'}]})
        self.assertEqual(result['1'][0]['id'],'p1')
        self.assertEqual(result['2'][0]['id'],'cached')
        self.assertEqual(result['3'][0]['id'],'p3')
        self.assertEqual(len(warnings),1)
    def test_parallel_roster_missing_without_cache(self):
        with patch.object(m,'roster',side_effect=RuntimeError('offline')):
            result,warnings=m.collect_rosters([{'id':'1','abbr':'ONE'}])
        self.assertEqual(result,{})
        self.assertEqual(len(warnings),1)
