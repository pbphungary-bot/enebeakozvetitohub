import datetime as dt
import gzip
import io
import pathlib
import sys
import unittest
import urllib.error
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update_nba as m

TODAY = dt.date(2026, 11, 20)


def event(eid, home='1', away='2', hs='100', as_='90', type_=2, completed=True, date='2025-01-16T01:00Z'):
    return {'id': eid, 'date': date, 'season': {'type': type_},
            'status': {'type': {'name': 'STATUS_FINAL' if completed else 'STATUS_SCHEDULED', 'completed': completed}},
            'competitions': [{'competitors': [
                {'homeAway': 'home', 'score': hs, 'team': {'id': home, 'displayName': 'H', 'abbreviation': 'H'}},
                {'homeAway': 'away', 'score': as_, 'team': {'id': away, 'displayName': 'A', 'abbreviation': 'A'}}]}]}


def day_of(url):
    return url.split('dates=')[1].split('&')[0]


class HistoryWindowTests(unittest.TestCase):
    def test_window_is_four_completed_seasons_game_months_only(self):
        days = m.history_days(TODAY, 4)
        self.assertEqual(days[0], dt.date(2022, 10, 1))
        self.assertEqual(days[-1], dt.date(2026, 6, 30))
        self.assertEqual(len(days), 273 + 274 + 273 + 273)  # 2023-24 contains Feb 29
        self.assertTrue(all(d.month in (10, 11, 12, 1, 2, 3, 4, 5, 6) for d in days))
    def test_window_is_stable_within_a_season_and_rolls_in_july(self):
        self.assertEqual(m.history_days(dt.date(2027, 3, 1), 4), m.history_days(TODAY, 4))
        self.assertEqual(m.history_days(dt.date(2027, 7, 1), 4)[-1], dt.date(2027, 6, 30))
    def test_zero_seasons_disables_history(self):
        self.assertEqual(m.collect_history(TODAY, 0)['totalDays'], 0)


class HistoryCollectionTests(unittest.TestCase):
    def test_never_uses_date_ranges(self):
        # ESPN answers any YYYYMMDD-YYYYMMDD range with HTTP 400 (diagnosed from a live Actions run).
        urls = []
        with patch.object(m, 'get', side_effect=lambda u: urls.append(u) or {'events': []}):
            m.collect_history(TODAY, batch=20)
        self.assertEqual(len(urls), 20)
        for u in urls:
            self.assertRegex(day_of(u), r'^\d{8}$')
    def test_batches_are_limited_and_newest_first(self):
        urls = []
        with patch.object(m, 'get', side_effect=lambda u: urls.append(u) or {'events': []}):
            r = m.collect_history(TODAY, batch=3)
        self.assertEqual(sorted(day_of(u) for u in urls), ['20260628', '20260629', '20260630'])
        self.assertEqual(r['daysFetched'], ['2026-06-28', '2026-06-29', '2026-06-30'])
        self.assertEqual(len(r['missing']), r['totalDays'] - 3)
    def test_empty_day_is_verified_but_missing_events_list_is_not(self):
        with patch.object(m, 'get', return_value={'events': []}):
            r = m.collect_history(TODAY, batch=2)
        self.assertEqual(r['daysFetched'], ['2026-06-29', '2026-06-30'])  # zero games is a valid, verified day
        self.assertEqual(len(r['missing']), r['totalDays'] - 2)
        with patch.object(m, 'get', return_value={}):
            r = m.collect_history(TODAY, batch=2)
        self.assertEqual(r['daysFetched'], [])
        self.assertTrue(any('missing events list' in f for f in r['failures']))
    def test_failed_days_stay_missing_with_http_detail(self):
        with patch.object(m, 'get', side_effect=RuntimeError("Could not fetch u: HTTP 400 Bad Request: 'bad dates'")):
            r = m.collect_history(TODAY, batch=4)
        self.assertEqual(r['daysFetched'], [])
        self.assertTrue(any('HTTP 400' in f and '2026-06-30' in f for f in r['failures']))
    def test_stops_early_when_a_whole_chunk_fails(self):
        calls = []
        with patch.object(m, 'get', side_effect=lambda u: calls.append(u) or (_ for _ in ()).throw(RuntimeError('blocked'))):
            r = m.collect_history(TODAY, batch=500, chunk=20)
        self.assertEqual(len(calls), 20)  # did not hammer ESPN with the remaining 480
        self.assertTrue(any('stopped early' in f for f in r['failures']))
    def test_only_completed_scored_non_preseason_games_are_stored_compactly(self):
        evs = [event('reg'), event('playoff', type_=3), event('playin', type_=5), event('pre', type_=1),
               event('live', completed=False), event('noscore', hs='', as_='')]
        with patch.object(m, 'get', return_value={'events': evs}):
            r = m.collect_history(TODAY, batch=1)
        ids = {g['id']: g for g in r['games']}
        self.assertEqual(sorted(ids), ['playin', 'playoff', 'reg'])
        self.assertEqual(ids['playoff']['seasonType'], '3')
        self.assertEqual(ids['playin']['seasonType'], '5')
        self.assertEqual(set(ids['reg']), {'id', 'date', 'seasonType', 'home', 'away'})
        self.assertEqual(ids['reg']['home'], {'id': '1', 'score': 100})
    def test_cached_days_are_not_refetched(self):
        cached = [{'id': 'old', 'date': '2026-06-30T01:00Z', 'seasonType': '2', 'home': {'id': '1', 'score': 1}, 'away': {'id': '2', 'score': 0}}]
        urls = []
        with patch.object(m, 'get', side_effect=lambda u: urls.append(u) or {'events': []}):
            r = m.collect_history(TODAY, cached=cached, cached_days=['2026-06-30', '2026-06-29'], batch=2)
        self.assertEqual(sorted(day_of(u) for u in urls), ['20260627', '20260628'])  # next newest uncovered days
        self.assertNotIn('20260630', [day_of(u) for u in urls])
        self.assertNotIn('20260629', [day_of(u) for u in urls])
        self.assertIn('old', [g['id'] for g in r['games']])
    def test_backfill_completes_over_several_runs_without_refetching(self):
        seen = []
        def fake(u):
            seen.append(day_of(u))
            return {'events': [event('g' + day_of(u))]}
        cached, days, runs = None, None, 0
        with patch.object(m, 'get', side_effect=fake):
            while True:
                r = m.collect_history(TODAY, cached=cached, cached_days=days, batch=300)
                cached, days, runs = r['games'], r['daysFetched'], runs + 1
                if not r['missing']:
                    break
                self.assertLess(runs, 10)
        self.assertEqual(runs, 4)  # 1093 days at 300 per run
        self.assertEqual(len(seen), len(set(seen)), 'a verified day was fetched twice')
        self.assertEqual(len(r['games']), r['totalDays'])


class HttpErrorDetailTests(unittest.TestCase):
    def _http_error(self, code, body=b'{"message":"bad dates"}'):
        return urllib.error.HTTPError('https://x', code, 'Bad Request', {}, io.BytesIO(gzip.compress(body)))
    def test_400_reports_decoded_body_and_is_not_retried(self):
        with patch.object(m.urllib.request, 'urlopen', side_effect=self._http_error(400)) as op, patch.object(m.time, 'sleep'):
            with self.assertRaises(RuntimeError) as cm:
                m.get('https://x')
        self.assertEqual(op.call_count, 1)
        self.assertIn('HTTP 400', str(cm.exception))
        self.assertIn('bad dates', str(cm.exception))
    def test_server_errors_are_retried(self):
        with patch.object(m.urllib.request, 'urlopen', side_effect=lambda *a, **k: (_ for _ in ()).throw(self._http_error(503))) as op, patch.object(m.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                m.get('https://x')
        self.assertEqual(op.call_count, 3)
    def test_rate_limit_is_retried(self):
        with patch.object(m.urllib.request, 'urlopen', side_effect=lambda *a, **k: (_ for _ in ()).throw(self._http_error(429))) as op, patch.object(m.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                m.get('https://x')
        self.assertEqual(op.call_count, 3)


class RssTests(unittest.TestCase):
    def test_rss(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): return b'<rss><channel><item><title>Knicks news</title><link>https://www.nba.com/news/x</link><pubDate>Thu</pubDate></item></channel></rss>'
        with patch.object(m.urllib.request, 'urlopen', return_value=Response()):
            self.assertEqual(m.rss_news('https://www.nba.com/rss/nba_rss.xml', 'NBA.com')[0]['source'], 'NBA.com')


if __name__ == '__main__': unittest.main()
