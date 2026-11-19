import unittest, pathlib, importlib.util, datetime as dt
p=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'update_nba.py'
spec=importlib.util.spec_from_file_location('nba',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class HistoryTests(unittest.TestCase):
 def test_month_ranges(self):
  x=list(m.month_ranges(dt.date(2026,1,20),dt.date(2026,3,4)))
  self.assertEqual(x,[(dt.date(2026,1,20),dt.date(2026,1,31)),(dt.date(2026,2,1),dt.date(2026,2,28)),(dt.date(2026,3,1),dt.date(2026,3,4))])
 def test_history_failures_are_visible(self):
  old=m.get
  try:
   m.get=lambda url: (_ for _ in ()).throw(RuntimeError('blocked'))
   games,failures=m.historical_games(dt.date(2026,7,2),1)
   self.assertEqual(games,[])
   self.assertEqual(len(failures),13)
  finally:m.get=old
 def test_rss(self):
  from unittest.mock import patch
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return b'<rss><channel><item><title>Knicks news</title><link>https://www.nba.com/news/x</link><pubDate>Thu</pubDate></item></channel></rss>'
  with patch.object(m.urllib.request,'urlopen',return_value=Response()):
   self.assertEqual(m.rss_news('https://www.nba.com/rss/nba_rss.xml','NBA.com')[0]['source'],'NBA.com')
if __name__=='__main__':unittest.main()
