import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m

# Shapes observed live (probe on the Actions runner): root `categories[].names` label each
# entry's `categories[].values` by position; team entries carry own (splitId 0) and opponent (900) splits.
PLAYER_ROOT = [
    {'name': 'general', 'names': ['gamesPlayed', 'avgMinutes', 'avgRebounds']},
    {'name': 'offensive', 'names': ['avgPoints', 'fieldGoalPct', 'threePointFieldGoalPct', 'freeThrowPct', 'avgAssists', 'avgTurnovers']},
    {'name': 'defensive', 'names': ['avgSteals', 'avgBlocks']},
]


def player(pid, gp=15.0, pts=37.2, team='13', **over):
    gen = [gp, 36.4, 8.7]
    off = [pts, 46.808998107910156, 37.56345212459564, 86.2750015258789, 7.6666665, 5.133333]
    dfn = [1.8666667, 0.6]
    return {'athlete': {'id': pid, 'teamId': team, 'displayName': 'P' + pid},
            'categories': [{'name': 'general', 'values': gen}, {'name': 'offensive', 'values': off}, {'name': 'defensive', 'values': dfn}]}


class PlayerSeasonTests(unittest.TestCase):
    def run_stats(self, athletes, pages=1):
        pages_seen = []
        def fake(url):
            pages_seen.append(url)
            return {'pagination': {'pages': pages}, 'categories': PLAYER_ROOT, 'athletes': athletes}
        with patch.object(m, 'get', side_effect=fake):
            return m.player_season_stats(2027), pages_seen
    def test_values_are_mapped_by_stat_name_and_rounded(self):
        out, _ = self.run_stats([player('3945274')])
        self.assertEqual(out['3945274'], {'teamId': '13', 'gp': 15, 'min': 36.4, 'pts': 37.2, 'reb': 8.7, 'ast': 7.7, 'stl': 1.9, 'blk': 0.6,
                                          'tov': 5.1, 'fgPct': 46.8, 'tpPct': 37.6, 'ftPct': 86.3})
    def test_mapping_follows_names_not_positions(self):
        root = [{'name': 'general', 'names': ['avgRebounds', 'gamesPlayed', 'avgMinutes']}] + PLAYER_ROOT[1:]
        entry = player('1')
        entry['categories'][0]['values'] = [9.5, 20.0, 30.1]
        with patch.object(m, 'get', return_value={'pagination': {'pages': 1}, 'categories': root, 'athletes': [entry]}):
            row = m.player_season_stats(2027)['1']
        self.assertEqual((row['gp'], row['min'], row['reb']), (20, 30.1, 9.5))
    def test_players_without_games_are_omitted_not_zeroed(self):
        out, _ = self.run_stats([player('1', gp=0.0), player('2')])
        self.assertEqual(sorted(out), ['2'])
    def test_missing_stat_is_unavailable_not_zero(self):
        entry = player('1'); entry['categories'][2]['values'] = [1.0]  # blocks missing
        out, _ = self.run_stats([entry])
        self.assertIsNone(out['1']['blk'])
        self.assertEqual(out['1']['stl'], 1.0)
    def test_players_parse_whether_or_not_splitid_is_present(self):
        # Exact live failure: ESPN's first athlete has no splitId, the other 472 have "0".
        first = player('1')
        rest = []
        for pid in ('2', '3'):
            e = player(pid)
            for c in e['categories']:
                c['splitId'] = '0'
            rest.append(e)
        out, _ = self.run_stats([first] + rest)
        self.assertEqual(sorted(out), ['1', '2', '3'])
        self.assertEqual(out['2']['pts'], out['1']['pts'])
    def test_parsing_a_small_fraction_of_listed_players_is_an_error(self):
        broken = [player(str(i)) for i in range(10)]
        for e in broken[1:]:
            e['categories'] = [{'name': 'general', 'splitId': 'unexpected', 'values': [15.0, 36.4, 8.7]}]  # format drift
        with patch.object(m, 'get', return_value={'pagination': {'pages': 1}, 'categories': PLAYER_ROOT, 'athletes': broken}):
            with self.assertRaises(ValueError) as cm:
                m.player_season_stats(2027)
        self.assertIn('parsed only 1 of 10', str(cm.exception))
    def test_a_few_players_without_games_do_not_trip_the_guard(self):
        out, _ = self.run_stats([player(str(i), gp=(0.0 if i < 2 else 5.0)) for i in range(10)])
        self.assertEqual(len(out), 8)
    def test_every_page_is_requested(self):
        with patch.object(m, 'get', side_effect=lambda u: {'pagination': {'pages': 2}, 'categories': PLAYER_ROOT, 'athletes': [player('a' if 'page=1' in u else 'b')]}) as g:
            out = m.player_season_stats(2027)
        self.assertEqual(sorted(out), ['a', 'b'])
        self.assertEqual(g.call_count, 2)
    def test_requests_the_regular_season_of_the_requested_year(self):
        _, urls = self.run_stats([player('1')])
        self.assertIn('season=2027', urls[0]); self.assertIn('seasontype=2', urls[0])
    def test_bad_response_raises(self):
        with patch.object(m, 'get', return_value={'athletes': None}):
            with self.assertRaises(ValueError): m.player_season_stats(2027)
        with patch.object(m, 'get', return_value={'pagination': {'pages': 1}, 'categories': PLAYER_ROOT, 'athletes': []}):
            with self.assertRaises(ValueError): m.player_season_stats(2027)


TEAM_ROOT = [
    {'name': 'general', 'names': ['avgRebounds', 'gamesPlayed']}, {'name': 'general'},
    {'name': 'defensive', 'names': ['avgDefensiveRebounds', 'avgSteals', 'avgBlocks']}, {'name': 'defensive'},
    {'name': 'offensive', 'names': ['avgPoints', 'fieldGoalPct', 'threePointFieldGoalPct', 'freeThrowPct', 'avgTurnovers', 'avgFieldGoalsAttempted', 'avgFreeThrowsAttempted', 'avgOffensiveRebounds', 'avgAssists']},
    {'name': 'offensive'},
]


def team_entry(tid, own_off, opp_off, gp=16.0):
    return {'team': {'id': tid}, 'categories': [
        {'name': 'general', 'splitId': '0', 'values': [46.2, gp]}, {'name': 'general', 'splitId': '900', 'values': [41.1, gp]},
        {'name': 'defensive', 'splitId': '0', 'values': [33.8, 6.8, 5.0]}, {'name': 'defensive', 'splitId': '900', 'values': [28.3, 7.9, 6.9]},
        {'name': 'offensive', 'splitId': '0', 'values': own_off}, {'name': 'offensive', 'splitId': '900', 'values': opp_off}]}


#            PTS    FG%   3P%   FT%   TO    FGA   FTA   OREB  AST
OWN = [122.125, 48.35, 39.78, 85.16, 15.0, 89.0625, 24.0, 12.4375, 29.25]
OPP = [111.9375, 45.03, 32.54, 77.36, 13.625, 89.375, 25.125, 12.8125, 24.875]


class TeamSeasonTests(unittest.TestCase):
    def stats(self, *entries):
        with patch.object(m, 'get', return_value={'categories': TEAM_ROOT, 'teams': list(entries)}):
            return m.team_season_stats(2027)
    def test_own_and_opponent_splits_are_separated(self):
        t = self.stats(team_entry('29', OWN, OPP))['29']
        self.assertEqual((t['ppg'], t['oppPpg'], t['diff']), (122.1, 111.9, 10.2))
        self.assertEqual((t['fgPct'], t['oppFgPct'], t['tpPct'], t['oppTpPct']), (48.4, 45.0, 39.8, 32.5))
        self.assertEqual((t['reb'], t['dreb'], t['stl'], t['blk'], t['gp']), (46.2, 33.8, 6.8, 5.0, 16))
    def test_pace_and_ratings_use_the_averaged_possession_estimate(self):
        t = self.stats(team_entry('29', OWN, OPP))['29']
        mine = 89.0625 - 12.4375 + 15.0 + 0.44 * 24.0
        theirs = 89.375 - 12.8125 + 13.625 + 0.44 * 25.125
        poss = (mine + theirs) / 2
        self.assertEqual(t['pace'], round(poss, 1))
        self.assertEqual(t['ortg'], round(100 * 122.125 / poss, 1))
        self.assertEqual(t['drtg'], round(100 * 111.9375 / poss, 1))
        self.assertEqual(t['net'], round(t['ortg'] - t['drtg'], 1))
    def test_missing_inputs_leave_advanced_stats_unavailable(self):
        t = self.stats(team_entry('29', OWN[:5] + [None] + OWN[6:], OPP))['29']  # FGA absent for the team
        self.assertIsNone(t['pace']); self.assertIsNone(t['ortg']); self.assertIsNone(t['net'])
        self.assertEqual(t['ppg'], 122.1)
    def test_empty_response_raises(self):
        with patch.object(m, 'get', return_value={'categories': TEAM_ROOT, 'teams': []}):
            with self.assertRaises(ValueError): m.team_season_stats(2027)


class StatValuesTests(unittest.TestCase):
    def test_unnamed_root_entry_reuses_earlier_names(self):
        v = m.stat_values([{'name': 'x', 'names': ['a', 'b']}, {'name': 'x'}], [{'name': 'x', 'splitId': '0', 'values': [1, 2]}, {'name': 'x', 'splitId': '900', 'values': [3, 4]}])
        self.assertEqual(v[('x', '0')], {'a': 1, 'b': 2}); self.assertEqual(v[('x', '900')], {'a': 3, 'b': 4})
    def test_non_numeric_values_are_dropped(self):
        v = m.stat_values([{'name': 'x', 'names': ['a', 'b', 'c']}], [{'name': 'x', 'values': [1, None, True]}])
        self.assertEqual(v[('x', '0')], {'a': 1})
    def test_num_never_turns_missing_into_zero(self):
        self.assertIsNone(m.num(None)); self.assertIsNone(m.num('3')); self.assertIsNone(m.num(True)); self.assertEqual(m.num(0), 0.0)


class InjuryTests(unittest.TestCase):
    ROW = {'id': '540201', 'status': 'Out', 'date': '2026-11-20T22:15Z', 'shortComment': 'Flemings (back) is out &amp; questionable.',
           'athlete': {'displayName': 'Kingston Flemings', 'position': {'abbreviation': 'PG'},
                       'links': [{'href': 'https://www.espn.com/nba/player/_/id/5149077/kingston-flemings'}]},
           'details': {'type': 'Back', 'detail': 'Strain', 'returnDate': '2026-11-22'}}
    def report(self, groups, ts='2026-11-21T22:14:37Z'):
        with patch.object(m, 'get', return_value={'timestamp': ts, 'injuries': groups}):
            return m.injury_report()
    def test_rows_are_normalised(self):
        rep, ts = self.report([{'id': '1', 'displayName': 'Atlanta Hawks', 'injuries': [self.ROW]}])
        r = rep['1'][0]
        self.assertEqual((r['name'], r['position'], r['status'], r['injury'], r['returnDate']), ('Kingston Flemings', 'PG', 'Out', 'Back Strain', '2026-11-22'))
        self.assertEqual(r['playerId'], '5149077')  # athlete id is taken from the profile link
        self.assertEqual(r['comment'], 'Flemings (back) is out & questionable.')
        self.assertEqual(ts, '2026-11-21T22:14:37Z')
    def test_not_specified_placeholder_is_dropped_from_the_injury_text(self):
        row = dict(self.ROW, details={'type': 'Hamstring', 'side': 'Left', 'detail': 'Not Specified', 'returnDate': '2026-12-01'})
        rep, _ = self.report([{'id': '1', 'injuries': [row]}])
        self.assertEqual(rep['1'][0]['injury'], 'Left Hamstring')
    def test_team_without_injuries_is_a_valid_empty_list(self):
        rep, _ = self.report([{'id': '2', 'injuries': []}])
        self.assertEqual(rep, {'2': []})
    def test_comment_is_capped_and_nameless_rows_skipped(self):
        long_row = dict(self.ROW, shortComment='x' * 900)
        rep, _ = self.report([{'id': '1', 'injuries': [long_row, {'athlete': {}, 'status': 'Out'}]}])
        self.assertEqual(len(rep['1']), 1); self.assertEqual(len(rep['1'][0]['comment']), 300)
    def test_explicit_athlete_id_wins_over_link(self):
        self.assertEqual(m.injury_player_id({'id': 77, 'links': [{'href': '/id/5/x'}]}), '77')
        self.assertEqual(m.injury_player_id({}), '')
    def test_bad_response_raises(self):
        with patch.object(m, 'get', return_value={}):
            with self.assertRaises(ValueError): m.injury_report()


class StageFailureTests(unittest.TestCase):
    def test_failed_stage_reports_and_returns_none(self):
        errors = []
        self.assertIsNone(m.refresh_cached('Injury report', lambda: (_ for _ in ()).throw(RuntimeError('boom')), {'1': []}, errors))
        self.assertIn('cached after fetch failure', errors[0]); self.assertIn('boom', errors[0])
    def test_failed_stage_without_cache_says_unavailable(self):
        errors = []
        m.refresh_cached('Team statistics', lambda: (_ for _ in ()).throw(RuntimeError('x')), None, errors)
        self.assertIn('unavailable', errors[0])
    def test_success_returns_value_without_errors(self):
        errors = []
        self.assertEqual(m.refresh_cached('x', lambda: 5, None, errors), 5); self.assertEqual(errors, [])


if __name__ == '__main__': unittest.main()
