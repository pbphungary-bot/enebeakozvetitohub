import importlib.util, pathlib, unittest
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('collector',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CollectorTests(unittest.TestCase):
 def test_normalize(self):
  e={'id':'123','date':'2026-11-19T01:00Z','status':{'type':{'name':'STATUS_FINAL','completed':True}},'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'1','displayName':'A','abbreviation':'AAA'},'score':'108'},{'homeAway':'away','team':{'id':'2','displayName':'B','abbreviation':'BBB'},'score':'105'}]}]}
  x=m.normalize_event(e);self.assertEqual(x['home']['score'],108);self.assertEqual(x['away']['id'],'2');self.assertTrue(x['completed'])
 def test_incomplete(self):
  self.assertIsNone(m.normalize_event({'competitions':[]}))
 def test_teams(self):
  old=m.get
  try:
   m.get=lambda _: {'sports':[{'leagues':[{'teams':[{'team':{'id':'1','displayName':'A','abbreviation':'A','logos':[{'href':'https://example.com/logo.png'}]}}]}]}]}
   self.assertEqual(m.team_list()[0]['logo'],'https://example.com/logo.png')
  finally:m.get=old
if __name__=='__main__':unittest.main()
