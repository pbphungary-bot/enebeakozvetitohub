import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m

TEAMS = [{'id': '20', 'name': 'Philadelphia 76ers'}, {'id': '15', 'name': 'Milwaukee Bucks'}]


def article(cats, title='Headline', desc='Body'):
    return {'headline': title, 'description': desc, 'published': '2026-11-21T00:00:00Z',
            'links': {'web': {'href': 'https://www.espn.com/nba/story/x'}}, 'categories': cats}


# Shape observed live: the category `id` is an ESPN category id; the NBA team id is `teamId`.
TEAM_CAT = lambda cat_id, team_id: {'id': cat_id, 'type': 'team', 'teamId': team_id, 'team': {'id': team_id}}


class NewsTaggingTests(unittest.TestCase):
    def test_team_tag_uses_team_id_not_category_id(self):
        with patch.object(m, 'get', return_value={'articles': [article([{'id': 9577, 'type': 'league'}, TEAM_CAT(4323, 20), TEAM_CAT(4453, 15)])]}):
            result = m.news()
        self.assertEqual(result[0]['teamIds'], ['20', '15'])
    def test_nested_team_id_is_used_when_teamid_missing(self):
        self.assertEqual(m.article_team_ids([{'type': 'team', 'id': 4323, 'team': {'id': 20}}]), ['20'])
    def test_non_team_categories_are_ignored(self):
        self.assertEqual(m.article_team_ids([{'type': 'topic', 'id': 1, 'topicId': 5}, {'type': 'league', 'id': 2}, 'junk', None]), [])
    def test_non_nba_team_tags_are_dropped(self):
        a = [{'title': 'College game', 'description': '', 'teamIds': ['20', '2509']}]  # 2509 = a college team
        m.tag_articles(a, TEAMS)
        self.assertEqual(a[0]['teamIds'], ['20'])
    def test_every_published_tag_is_a_real_team(self):
        with patch.object(m, 'get', return_value={'articles': [article([TEAM_CAT(4323, 20), TEAM_CAT(99, 2509)])]}):
            tagged = m.tag_articles(m.news(), TEAMS)
        self.assertTrue(set(tagged[0]['teamIds']) <= {t['id'] for t in TEAMS})
    def test_name_matching_still_tags_untagged_feed_articles(self):
        a = [{'title': 'Bucks fall to the Philadelphia 76ers', 'description': '', 'teamIds': []}]
        m.tag_articles(a, TEAMS)
        self.assertEqual(a[0]['teamIds'], ['15', '20'])


class FeedTests(unittest.TestCase):
    RSS = (b'<rss><channel><item><title>\n   Tyler Herro scores 50 in 76ers&amp;#39; win  \n</title>'
           b'<link>https://sports.yahoo.com/nba/article/x.html</link><pubDate>Sat, 21 Nov 2026 21:04:00 GMT</pubDate>'
           b'<description>&lt;p&gt;Herro &lt;b&gt;dropped&lt;/b&gt; 50.&lt;/p&gt;</description></item></channel></rss>')
    def feed(self):
        data = self.RSS
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self, n): return data
        return patch.object(m.urllib.request, 'urlopen', return_value=Response())
    def test_entities_tags_and_whitespace_are_cleaned(self):
        with self.feed():
            item = m.rss_news('https://sports.yahoo.com/nba/rss/', 'Yahoo Sports')[0]
        self.assertEqual(item['title'], "Tyler Herro scores 50 in 76ers' win")
        self.assertEqual(item['description'], 'Herro dropped 50.')
        self.assertEqual(item['source'], 'Yahoo Sports')
    def test_dead_feeds_are_not_configured(self):
        urls = [u for u, _ in m.RSS_FEEDS]
        self.assertFalse(any('nba.com' in u or 'espn.com/espn/rss' in u for u in urls))
        self.assertTrue(all(u.startswith('https://') for u in urls))
    def test_clean_text_handles_none_and_double_encoding(self):
        self.assertEqual(m.clean_text(None), '')
        self.assertEqual(m.clean_text('A &amp;amp; B'), 'A & B')


if __name__ == '__main__': unittest.main()
