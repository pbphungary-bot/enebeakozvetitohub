import datetime as dt
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import update_nba as u
from validate_data import validate

class ResilienceTests(unittest.TestCase):
    def test_partial_coverage_with_recent_verified_days_is_publishable(self):
        now=dt.datetime(2026,11,19,12,tzinfo=dt.timezone.utc)
        teams=[{'id':str(i)} for i in range(1,31)]
        games=[{'id':str(i),'date':'2026-11-18T20:00:00Z','completed':True,'home':{'id':str(i%30+1),'score':100},'away':{'id':str((i+1)%30+1),'score':90}} for i in range(30)]
        covered=[(now.date()-dt.timedelta(days=i)).isoformat() for i in range(30)]
        data={'teams':teams,'games':games,'standings':{'1':{}},'rosters':{str(i):[{'id':'p'}] for i in range(1,31)},'seasonComplete':False,'seasonDaysFetched':covered,'seasonMissingDays':['2026-11-05'],'generatedAt':now.isoformat()}
        self.assertEqual(validate(data,now),[])
        data['seasonMissingDays']=['2026-11-%02d'%i for i in range(1,11)]
        self.assertTrue(any('coverage' in x for x in validate(data,now)))
    def test_future_scoreboard_failure_does_not_abort_collection(self):
        today=dt.date(2026,11,19)
        teams=[{'id':str(i),'name':f'Team {i}','abbr':f'T{i}'} for i in range(1,31)]
        game={'id':'g','date':'2026-11-18T20:00:00Z','completed':True,'home':{'id':'1','name':'Team 1','score':90},'away':{'id':'2','name':'Team 2','score':80}}
        cached={'games':[game],'standings':{'1':{'stats':{}}},'rosters':{str(i):[{'id':str(i)}] for i in range(1,31)}}
        with patch.object(u,'team_list',return_value=teams),patch.object(u,'scoreboard',side_effect=RuntimeError('timeout')),patch.object(u,'standings',return_value={'1':{}}),patch.object(u,'news',return_value=[]),patch.object(u,'historical_games',return_value=([],[])),patch.object(u,'current_season_games',return_value=([game],['2026-11-18'],[],[])),patch.object(u,'collect_rosters',return_value=(cached['rosters'],[])),patch.object(u,'collect_boxscores',return_value=({},[])),patch.object(u,'rss_news',return_value=[]):
            # At least 30 games required, so cached schedule fills the threshold.
            cached['games']=[dict(game,id=str(i)) for i in range(30)]
            result=u.collect(today,days_forward=2,cached=cached)
        self.assertGreaterEqual(len(result['games']),30)
        self.assertTrue(any('Upcoming fixture' in x for x in result['warnings']))
if __name__=='__main__':unittest.main()
