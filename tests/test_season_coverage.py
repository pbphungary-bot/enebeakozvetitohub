import pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class SeasonCoverageTests(unittest.TestCase):
 def test_season_history_merged_into_form_games(self):
  s=(ROOT/'scripts'/'update_nba.py').read_text()
  self.assertIn("for g in season_games:games[g['id']]=g",s)
  self.assertIn("'seasonComplete':not season_missing",s)
 def test_ui_uses_tested_logic_helpers(self):
  # Behaviour is verified in tests/test_front_logic.js; this only guards against
  # the UI bypassing those helpers (e.g. reading raw history or conferenceRank first).
  s=(ROOT/'index.html').read_text()
  self.assertIn('h2hFrom(state.data.history,allGames()',s)
  self.assertIn('confSeed(s)',s)
  self.assertIn('standingsByConference(',s)
  self.assertNotIn('state.data.history||allGames()',s)
  self.assertNotIn('Párharcelemző',s)
if __name__=='__main__':unittest.main()
