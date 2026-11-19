import unittest, pathlib, importlib.util
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('nba',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RankTests(unittest.TestCase):
 def test_rankings(self):
  rows={'1':{'conference':'East','division':'Atlantic','stats':{'overall':'8-2'}},'2':{'conference':'East','division':'Atlantic','stats':{'overall':'7-3'}},'3':{'conference':'East','division':'Central','stats':{'overall':'9-1'}},'4':{'conference':'West','division':'Pacific','stats':{'overall':'4-6'}}}
  m.rank_standings(rows)
  self.assertEqual(rows['3']['stats']['conferenceRank'],'1')
  self.assertEqual(rows['1']['stats']['conferenceRank'],'2')
  self.assertEqual(rows['2']['stats']['divisionRank'],'2')
  self.assertEqual(rows['4']['stats']['divisionRank'],'1')
 def test_article_team_tags(self):
  a=[{'title':'Knicks trade report','description':'','teamIds':[]}]
  m.tag_articles(a,[{'id':'1','name':'New York Knicks'},{'id':'2','name':'Boston Celtics'}])
  self.assertEqual(a[0]['teamIds'],['1'])
if __name__=='__main__':unittest.main()
