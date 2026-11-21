import importlib.util, pathlib, unittest
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('collector',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CollectorTests(unittest.TestCase):
 def test_normalize(self):
  e={'id':'123','date':'2026-11-19T01:00Z','status':{'type':{'name':'STATUS_FINAL','completed':True}},'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'1','displayName':'A','abbreviation':'AAA'},'score':'108'},{'homeAway':'away','team':{'id':'2','displayName':'B','abbreviation':'BBB'},'score':'105'}]}]}
  x=m.normalize_event(e);self.assertEqual(x['home']['score'],108);self.assertEqual(x['away']['id'],'2');self.assertTrue(x['completed'])
 def _event(self,status,completed,hs,as_):
  return {'id':'9','date':'2026-11-21T00:00Z','status':{'type':{'name':status,'completed':completed}},'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'1','displayName':'A','abbreviation':'AAA'},'score':hs},{'homeAway':'away','team':{'id':'2','displayName':'B','abbreviation':'BBB'},'score':as_}]}]}
 def test_scheduled_game_has_no_score_not_zero(self):
  # ESPN sends "0" for games not yet played; storing it showed 0-0 on the live schedule.
  x=m.normalize_event(self._event('STATUS_SCHEDULED',False,'0','0'))
  self.assertIsNone(x['home']['score']);self.assertIsNone(x['away']['score']);self.assertFalse(x['completed'])
 def test_live_game_keeps_its_score_including_zero(self):
  x=m.normalize_event(self._event('STATUS_IN_PROGRESS',False,'0','2'))
  self.assertEqual((x['home']['score'],x['away']['score']),(0,2))
 def test_final_game_keeps_its_score(self):
  x=m.normalize_event(self._event('STATUS_FINAL',True,'101','99'))
  self.assertEqual((x['home']['score'],x['away']['score']),(101,99))
 def test_incomplete(self):
  self.assertIsNone(m.normalize_event({'competitions':[]}))
 def test_teams(self):
  old=m.get
  try:
   m.get=lambda _: {'sports':[{'leagues':[{'teams':[{'team':{'id':'1','displayName':'A','abbreviation':'A','logos':[{'href':'https://example.com/logo.png'}]}}]}]}]}
   self.assertEqual(m.team_list()[0]['logo'],'https://example.com/logo.png')
  finally:m.get=old
if __name__=='__main__':unittest.main()
