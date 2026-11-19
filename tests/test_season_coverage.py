import pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class SeasonCoverageTests(unittest.TestCase):
 def test_season_history_merged_into_form_games(self):
  s=(ROOT/'scripts'/'update_nba.py').read_text()
  self.assertIn("for g in season_games:games[g['id']]=g",s)
  self.assertIn("'seasonComplete':not any(m >= season_start.strftime",s)
 def test_conference_rank_display(self):
  s=(ROOT/'index.html').read_text()
  self.assertIn("stat(id,'conferenceRank','playoffSeed','seed')",s)
  self.assertIn('Head to head — collected history',s)
if __name__=='__main__':unittest.main()
