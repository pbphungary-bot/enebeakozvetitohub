import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as u
from validate_data import validate

class PublishFilterTests(unittest.TestCase):
    def test_reported_bad_id_is_filtered_before_validation(self):
        teams=[{'id':'1'}, {'id':'2'}]
        games=[{'id':'401914130','home':{'id':'1'},'away':{'id':'999'}},
               {'id':'good','home':{'id':'1'},'away':{'id':'2'}}]
        cleaned, rejected=u.filter_nba_games(games,teams)
        self.assertEqual([g['id'] for g in cleaned], ['good'])
        self.assertEqual(rejected,['401914130'])
    def test_strict_validator_still_rejects_bad_game(self):
        data={'teams':[{'id':str(i)} for i in range(30)],
              'games':[{'id':'401914130','home':{'id':'1'},'away':{'id':'999'},'date':'2026-11-19T00:00:00Z'}],
              'generatedAt':'2026-11-19T00:00:00+00:00','standings':{'1':{}},'rosters':{str(i):[] for i in range(30)},'seasonComplete':True}
        errors=validate(data)
        self.assertTrue(any('401914130' in e for e in errors))

if __name__=='__main__':unittest.main()
