import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m


def entry(tid, wins, losses, seed=None):
    stats = [{'name': 'wins', 'displayValue': str(wins)}, {'name': 'losses', 'displayValue': str(losses)}]
    if seed:
        stats.append({'name': 'playoffSeed', 'displayValue': str(seed)})
    return {'team': {'id': tid}, 'stats': stats}


def node(name, entries=None, children=None):
    out = {'name': name}
    if entries is not None:
        out['standings'] = {'entries': entries}
    if children is not None:
        out['children'] = children
    return out


# ESPN level=3 shape observed live: divisions are named 'Atlantic', 'Central', ... (no word "Division").
LEVEL3 = node('National Basketball Association', children=[
    node('Eastern Conference', entries=[], children=[node('Atlantic', entries=[entry('1', 9, 6, 1), entry('2', 5, 10, 3)]), node('Central', entries=[entry('3', 8, 8, 2)])]),
    node('Western Conference', entries=[], children=[node('Pacific', entries=[entry('4', 13, 3, 1)])]),
])
LEVEL2 = node('National Basketball Association', children=[
    node('Eastern Conference', entries=[entry('1', 9, 6, 1)]), node('Western Conference', entries=[entry('4', 13, 3, 1)])])


class StandingsParsingTests(unittest.TestCase):
    def test_divisions_are_read_from_the_level3_tree(self):
        with patch.object(m, 'get', return_value=LEVEL3):
            s = m.standings()
        self.assertEqual((s['1']['conference'], s['1']['division']), ('Eastern Conference', 'Atlantic'))
        self.assertEqual(s['3']['division'], 'Central')
        self.assertEqual((s['4']['conference'], s['4']['division']), ('Western Conference', 'Pacific'))
        self.assertTrue(all(v['division'] for v in s.values()))
    def test_conference_level_entries_are_not_mistaken_for_divisions(self):
        with patch.object(m, 'get', return_value=LEVEL2):
            s = m.standings()
        self.assertEqual(s['1']['division'], '')
        self.assertEqual(s['1']['conference'], 'Eastern Conference')
    def test_playoff_seed_is_preserved(self):
        with patch.object(m, 'get', return_value=LEVEL3):
            self.assertEqual(m.standings()['2']['stats']['playoffSeed'], '3')


class RankTieTests(unittest.TestCase):
    def rows(self, records):
        return {str(i): {'conference': 'E', 'division': 'D', 'stats': {'wins': str(w), 'losses': str(l)}} for i, (w, l) in enumerate(records, 1)}
    def test_equal_records_share_a_tied_rank(self):
        rows = m.rank_standings(self.rows([(8, 2), (8, 2), (7, 3)]))
        self.assertEqual([rows[k]['stats']['divisionRank'] for k in '123'], ['T-1', 'T-1', '3'])
    def test_equal_percentages_with_different_games_are_tied(self):
        rows = m.rank_standings(self.rows([(8, 2), (16, 4), (1, 9)]))
        self.assertEqual([rows[k]['stats']['conferenceRank'] for k in '123'], ['T-1', 'T-1', '3'])
    def test_untied_ranks_are_plain_numbers(self):
        rows = m.rank_standings(self.rows([(9, 1), (8, 2), (7, 3)]))
        self.assertEqual([rows[k]['stats']['divisionRank'] for k in '123'], ['1', '2', '3'])
    def test_no_record_means_no_rank(self):
        rows = m.rank_standings({'1': {'conference': 'E', 'division': 'D', 'stats': {}}})
        self.assertNotIn('divisionRank', rows['1']['stats'])


if __name__ == '__main__': unittest.main()
