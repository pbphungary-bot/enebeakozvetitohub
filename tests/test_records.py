import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_nba import parse_record,rank_standings
class RecordTests(unittest.TestCase):
 def test_variants(self):
  self.assertEqual(parse_record({'overall':'12-6'}),(12,6))
  self.assertEqual(parse_record({'overall':'12–6'}),(12,6))
  self.assertEqual(parse_record({'wins':'12','losses':'6'}),(12,6))
  self.assertIsNone(parse_record({'overall':'—'}))
 def test_rank_without_overall(self):
  data={'1':{'conference':'East','division':'Atlantic','stats':{'wins':'12','losses':'6'}},'2':{'conference':'East','division':'Atlantic','stats':{'wins':'10','losses':'8'}}}
  result=rank_standings(data)
  self.assertEqual(result['1']['stats']['divisionRank'],'1')
  self.assertEqual(result['2']['stats']['conferenceRank'],'2')
if __name__=='__main__':unittest.main()
