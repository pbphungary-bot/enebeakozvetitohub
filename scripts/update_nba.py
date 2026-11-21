#!/usr/bin/env python3
"""Free ESPN public-data collector. No credentials. Fails closed on network errors."""
import argparse, datetime as dt, gzip, html, json, os, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
CORE='https://site.web.api.espn.com/apis/v2/sports/basketball/nba'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; NBACommentatorCenter/1.0)','Accept':'application/json'}
def describe_http_error(e):
    """HTTP status plus the (possibly gzip-compressed) response body, so logs show why ESPN refused."""
    body=b''
    try:body=e.read(1000)
    except Exception:pass
    if body[:2]==b'\x1f\x8b':
        try:body=gzip.decompress(body)
        except Exception:pass
    return f"HTTP {e.code} {e.reason}: {body.decode('utf-8','replace').strip()[:200]!r}"
def get(url):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=18) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            last=describe_http_error(e)
            # A client error (e.g. 400 for an unsupported date range) is deterministic: retrying cannot help.
            if 400<=e.code<500 and e.code not in (408,429):break
        except Exception as e:
            last=f'{type(e).__name__}: {e}'
        if attempt<2: time.sleep(1+attempt)
    raise RuntimeError(f'Could not fetch {url}: {last}')
def as_list(x): return x if isinstance(x,list) else []
def obj(x): return x if isinstance(x,dict) else {}
def competitors(event):
    c=as_list(obj(as_list(event.get('competitions'))[0] if event.get('competitions') else {}).get('competitors'))
    return {x.get('homeAway'):x for x in c}
def normalize_event(e):
    cs=competitors(e)
    if not all(k in cs for k in ('home','away')): return None
    def team(x):
        t=obj(x.get('team'));return {'id':str(t.get('id','')),'name':t.get('displayName',''),'abbr':t.get('abbreviation',''),'logo':t.get('logo',''),'score':int(x['score']) if str(x.get('score','')).isdigit() else None,'record':obj(as_list(x.get('records'))[0] if x.get('records') else {}).get('summary','')}
    status=obj(e.get('status'));typ=obj(status.get('type'))
    game={'id':str(e.get('id','')),'date':e.get('date',''),'status':typ.get('name',''),'completed':bool(typ.get('completed')),'detail':typ.get('shortDetail',''),'seasonType':str(obj(e.get('season')).get('type') or obj(e.get('seasonType')).get('type') or obj(obj(as_list(e.get('competitions'))[0] if e.get('competitions') else {}).get('type')).get('id') or ''), 'home':team(cs['home']),'away':team(cs['away'])}
    if game['status']=='STATUS_SCHEDULED':
        # ESPN reports "0" for games not yet played; that is not a score.
        game['home']['score']=game['away']['score']=None
    return game
def filter_nba_games(games, teams):
    """Exclude ESPN exhibition/placeholder opponents not in the NBA team list.

    Scoreboard feeds sometimes include non-NBA teams, including preseason
    exhibitions. Such games must not invalidate an otherwise valid NBA feed.
    """
    valid_ids={str(t['id']) for t in teams if t.get('id')}
    accepted=[];rejected=[]
    for game in games:
        if not isinstance(game,dict):
            rejected.append('<invalid event>');continue
        home=str(obj(game.get('home')).get('id',''))
        away=str(obj(game.get('away')).get('id',''))
        if home in valid_ids and away in valid_ids and home!=away:
            accepted.append(game)
        else:
            rejected.append(str(game.get('id','<missing id>')))
    return accepted,rejected

def scoreboard(day):
    data=get(BASE+'/scoreboard?'+urllib.parse.urlencode({'dates':day.strftime('%Y%m%d'),'limit':100}))
    return [v for e in as_list(data.get('events')) if (v:=normalize_event(e))]
def current_season_games(today, season_start, cached=None, cached_days=None):
    """Fetch every calendar day of the current season, not ESPN's truncated monthly windows.

    A successful empty scoreboard is valid; a missing events array or HTTP failure
    is not. Older successful days are cached, and the last three days refresh.
    """
    existing={str(g['id']):g for g in as_list(cached) if isinstance(g,dict)
              and g.get('id') and season_start.isoformat()<=str(g.get('date',''))[:10]<=today.isoformat()}
    covered=set(cached_days or []) if existing else set()
    days=[season_start+dt.timedelta(days=i) for i in range((today-season_start).days+1)]
    required={day.isoformat() for day in days}
    covered.intersection_update(required)
    refresh_from=today-dt.timedelta(days=2)
    needed=[day for day in days if day>=refresh_from or day.isoformat() not in covered]
    failures=[]
    def fetch(day):
        raw=get(BASE+'/scoreboard?'+urllib.parse.urlencode({'dates':day.strftime('%Y%m%d'),'limit':100}))
        if not isinstance(raw.get('events'),list):
            raise ValueError('scoreboard response missing events list')
        return [v for e in raw['events'] if (v:=normalize_event(e))]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(fetch,day):day for day in needed}
        for future in as_completed(futures):
            day=futures[future]
            try:
                rows=future.result()
                covered.add(day.isoformat())
                for g in rows: existing[g['id']]=g
            except Exception as exc:
                # Keep the old verified day when a refresh fails; do not falsely
                # mark an unfetched day complete.
                if day.isoformat() not in covered:
                    failures.append(f'{day.isoformat()}: {exc}')
    return list(existing.values()), sorted(covered), failures, sorted(required-covered)

def team_list():
    raw=get(BASE+'/teams?limit=100')
    leagues=as_list(obj(raw.get('sports') and raw['sports'][0]).get('leagues'))
    entries=as_list(obj(leagues[0] if leagues else {}).get('teams'))
    return [{'id':str(t.get('id')),'name':t.get('displayName',''),'abbr':t.get('abbreviation',''),'logo':t.get('logos',[{}])[0].get('href','') if t.get('logos') else t.get('logo',''),'division':obj(t.get('groups')).get('name','')} for entry in entries if (t:=obj(entry.get('team'))).get('id')]
def standings():
    raw=get(CORE+'/standings?level=3&sort=playoffseed%3Aasc')
    out={}
    def walk(n,division='',conference=''):
        if isinstance(n,list):
            for x in n: walk(x,division,conference)
            return
        if not isinstance(n,dict): return
        name=n.get('name','')
        entries_here=as_list(obj(n.get('standings')).get('entries'))
        if 'Conference' in name: conference=name
        elif 'Division' in name: division=name
        elif entries_here and conference: division=name  # level=3: the group that lists teams under a conference is a division
        for entry in as_list(obj(n.get('standings')).get('entries')):
            t=obj(entry.get('team'));tid=str(t.get('id',''))
            if not tid:continue
            stats={s.get('name',''):s.get('displayValue','') for s in as_list(entry.get('stats'))}
            out[tid]={'conference':conference,'division':division,'stats':stats}
        for child in as_list(n.get('children')):walk(child,division,conference)
    walk(raw)
    return rank_standings(out)
def parse_record(stats):
    """Read ESPN records from several published key conventions."""
    for key in ('overall','record','overallRecord'):
        value=str(stats.get(key,'')).strip()
        import re
        match=re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)',value)
        if match:return int(match.group(1)),int(match.group(2))
    try:return int(stats['wins']),int(stats['losses'])
    except (ValueError,TypeError,KeyError):return None

def rank_standings(entries):
    """Derive conference/division positions from actual wins and losses.

    ESPN's standings stat names vary; never fabricate ranks without a record.
    Equal win percentages share a rank and are marked tied ("T-2"). These are
    NOT official tiebreaker-aware seeds; the UI prefers ESPN's playoffSeed.
    """
    by_conf={};by_div={}
    for tid,entry in entries.items():
        record=parse_record(entry.get('stats',{}))
        if record is None:continue
        w,l=record
        if w+l==0: continue
        item=(tid,Fraction(w,w+l))
        if entry.get('conference'):by_conf.setdefault(entry['conference'],[]).append(item)
        if entry.get('division'):by_div.setdefault(entry['division'],[]).append(item)
    for field,groups in [('conferenceRank',by_conf),('divisionRank',by_div)]:
        for group in groups.values():
            for tid,pct in group:
                rank=1+sum(1 for _,other in group if other>pct)
                tied=sum(1 for _,other in group if other==pct)>1
                entries[tid]['stats'][field]=f'T-{rank}' if tied else str(rank)
    return entries

def tag_articles(articles, teams):
    """Tag unlabelled RSS articles using exact team names and distinctive nicknames."""
    valid={str(t['id']) for t in teams}
    nicknames={}
    for t in teams:
        nick=t['name'].split()[-1].lower()
        nicknames.setdefault(nick,[]).append(t['id'])
    for a in articles:
        text=(a.get('title','')+' '+a.get('description','')).lower()
        ids=set(map(str,a.get('teamIds',[])))
        for t in teams:
            if t['name'].lower() in text:ids.add(t['id'])
            nick=t['name'].split()[-1].lower()
            if len(nicknames[nick])==1 and len(nick)>3:
                import re
                if re.search(r'(?<![a-z])'+re.escape(nick)+r'(?![a-z])',text):ids.add(t['id'])
        a['teamIds']=sorted(i for i in ids if i in valid)  # drop non-NBA (college/WNBA) team tags
    return articles

def roster(team_id):
    """Return ESPN roster athletes with stable IDs; unavailable fields stay blank."""
    raw=get(BASE+'/teams/'+urllib.parse.quote(str(team_id),safe='')+'/roster')
    result=[]
    for group in as_list(raw.get('athletes')):
        if isinstance(group,dict) and 'items' in group:
            athletes=as_list(group.get('items'))
        elif isinstance(group,dict) and group.get('id'):
            athletes=[group]
        else:
            continue
        for a in athletes:
            if not a.get('id'):continue
            result.append({'id':str(a['id']),'name':a.get('displayName',''),
                'number':a.get('jersey',''),'position':obj(a.get('position')).get('abbreviation',''),
                'age':a.get('age'),'height':a.get('displayHeight',''),
                'weight':a.get('displayWeight',''),'headshot':obj(a.get('headshot')).get('href','')})
    return result

def collect_rosters(teams, previous=None):
    """Fetch rosters with bounded concurrency; preserve cached rows on failure."""
    rosters={};errors=[]
    old=obj(previous)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(roster,t['id']):t for t in teams}
        for future in as_completed(futures):
            t=futures[future]
            try:
                players=future.result()
                if not players:raise ValueError('no players returned')
                rosters[t['id']]=players
            except Exception as exc:
                if as_list(old.get(t['id'])):
                    rosters[t['id']]=old[t['id']]
                    errors.append(f"{t['abbr']} roster: cached after fetch failure")
                else:
                    errors.append(f"{t['abbr']} roster unavailable: {exc}")
    return rosters,errors

def parse_boxscore(raw):
    """Normalize ESPN summary player box scores into cacheable rows."""
    out=[]
    for block in as_list(obj(raw.get('boxscore')).get('players')):
        club=obj(block.get('team')).get('displayName','')
        for group in as_list(block.get('statistics')):
            labels=as_list(group.get('labels'))
            for item in as_list(group.get('athletes')):
                athlete=obj(item.get('athlete'))
                if not athlete.get('id'):continue
                out.append({'team':club,'id':str(athlete['id']),
                    'name':athlete.get('displayName',''),
                    'stats':as_list(item.get('stats')),'labels':labels})
    return out

def collect_boxscores(games, cached=None, max_games=25):
    """Precache recent completed games so the browser need not call ESPN directly."""
    old=obj(cached);result={k:v for k,v in old.items() if as_list(v)};errors=[]
    recent=sorted((g for g in games if g.get('completed')),key=lambda g:g.get('date',''),reverse=True)[:max_games]
    for game in recent:
        gid=str(game['id'])
        if as_list(old.get(gid)):
            result[gid]=old[gid];continue
        try:
            rows=parse_boxscore(get(BASE+'/summary?event='+urllib.parse.quote(gid,safe='')))
            if not rows:raise ValueError('no player box-score rows')
            result[gid]=rows
        except Exception as exc:
            errors.append(f'Box score {gid} unavailable: {exc}')
    return result,errors

def aggregate_player_stats(boxscores, games, season_start):
    """Summarize only actually cached current-season box-score rows.

    This is explicitly not an official full-season average: coverage can be sparse.
    """
    eligible={str(g['id']):g for g in games if g.get('completed') and str(g.get('date',''))[:10]>=season_start.isoformat()}
    accum={}
    for gid,rows in obj(boxscores).items():
        game=eligible.get(str(gid))
        if not game:continue
        for row in as_list(rows):
            labels=[str(x).upper() for x in as_list(row.get('labels'))]
            values=as_list(row.get('stats'))
            if not row.get('id') or not labels or not values:continue
            team_name=row.get('team','')
            side=next((x for x in ('home','away') if game[x].get('name')==team_name),None)
            if side is None:continue
            tid=str(game[side]['id']); pid=str(row['id'])
            extracted={}
            for field,aliases in [('pts',('PTS','POINTS')),('reb',('REB','REBOUNDS')),('ast',('AST','ASSISTS'))]:
                idx=next((labels.index(a) for a in aliases if a in labels),None)
                if idx is not None and idx<len(values):
                    try:extracted[field]=float(values[idx])
                    except (TypeError,ValueError):pass
            if not extracted:continue
            item=accum.setdefault(tid,{}).setdefault(pid,{'games':0,'totals':{'pts':0.,'reb':0.,'ast':0.},'counts':{'pts':0,'reb':0,'ast':0}})
            item['games']+=1
            for k,v in extracted.items():item['totals'][k]+=v;item['counts'][k]+=1
    return {tid:{pid:{'games':v['games'],**{k:round(v['totals'][k]/v['counts'][k],1) if v['counts'][k] else None for k in ('pts','reb','ast')}} for pid,v in players.items()} for tid,players in accum.items()}

def clean_text(value):
    """Decode HTML entities (feeds sometimes double-encode), drop tags and collapse whitespace."""
    text=html.unescape(html.unescape(str(value or '')))
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',text)).strip()

def article_team_ids(categories):
    """Team tags carry the NBA team id in `teamId` (their own `id` is an ESPN category id, not a team id)."""
    ids=[]
    for c in as_list(categories):
        if not isinstance(c,dict) or c.get('type')!='team':continue
        tid=c.get('teamId') or obj(c.get('team')).get('id')
        if tid:ids.append(str(tid))
    return ids

def news():
    raw=get(BASE+'/news?limit=100')
    result=[]
    for a in as_list(raw.get('articles')):
        links=obj(a.get('links'));web=obj(links.get('web'))
        url=web.get('href','')
        if not url:continue
        result.append({'title':clean_text(a.get('headline','')),'url':url,'published':a.get('published',''),'source':'ESPN','description':clean_text(a.get('description','')),'teamIds':article_team_ids(a.get('categories'))})
    return result
def history_days(today, seasons=4):
    """Game days (Oct 1 - Jun 30) of the last `seasons` completed seasons before the current one."""
    season_year=today.year if today.month>=7 else today.year-1
    days=[]
    for year in range(season_year-seasons,season_year):
        first,last=dt.date(year,10,1),dt.date(year+1,6,30)
        days.extend(first+dt.timedelta(days=i) for i in range((last-first).days+1))
    return days

def compact_game(g):
    """Minimal stored form of a historical result; names/abbreviations are restored from the team list in the UI."""
    return {'id':g['id'],'date':g['date'],'seasonType':g.get('seasonType',''),
            'home':{'id':g['home']['id'],'score':g['home']['score']},'away':{'id':g['away']['id'],'score':g['away']['score']}}

def history_event(event):
    """Completed, scored, non-preseason event in compact form, or None."""
    g=normalize_event(event)
    if not g or not g['completed'] or g['seasonType']=='1':return None
    if g['home']['score'] is None or g['away']['score'] is None:return None
    return compact_game(g)

def collect_history(today, seasons=4, cached=None, cached_days=None, batch=250, chunk=50, workers=5):
    """Fetch completed games one ESPN day at a time, `batch` days per run, newest first.

    ESPN rejects date-range scoreboard requests with HTTP 400, so ranges are never used.
    A day counts as verified only after a successful response with an events list (an
    empty list is valid). Failed days stay missing and are retried on the next run.
    """
    if seasons<=0:
        return {'games':[],'daysFetched':[],'totalDays':0,'missing':[],'failures':[],'attempted':0,'start':'','end':''}
    days=history_days(today,seasons)
    required={d.isoformat() for d in days}
    first=days[0].isoformat()
    games={str(g['id']):g for g in as_list(cached) if isinstance(g,dict) and g.get('id') and str(g.get('date',''))[:10]>=first}
    # Coverage metadata alone is not proof of cached results: without cached games, trust nothing.
    covered=(set(cached_days or []) if games else set())&required
    todo=sorted(required-covered,reverse=True)
    if batch and batch>0:todo=todo[:batch]
    def fetch(iso):
        raw=get(BASE+'/scoreboard?'+urllib.parse.urlencode({'dates':iso.replace('-',''),'limit':100}))
        if not isinstance(raw.get('events'),list):raise ValueError('scoreboard response missing events list')
        return [c for e in raw['events'] if (c:=history_event(e))]
    failures=[]
    for i in range(0,len(todo),chunk):
        ok=0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(fetch,iso):iso for iso in todo[i:i+chunk]}
            for future in as_completed(futures):
                iso=futures[future]
                try:rows=future.result()
                except Exception as exc:
                    failures.append(f'{iso}: {exc}');continue
                ok+=1;covered.add(iso)
                for c in rows:games[c['id']]=c
        print(f'[NBA] history: {len(covered)}/{len(required)} days verified',flush=True)
        if ok==0:
            failures.append(f'stopped early: all {len(todo[i:i+chunk])} requests in a chunk failed');break
    missing=sorted(required-covered)
    return {'games':sorted(games.values(),key=lambda g:g['date']),'daysFetched':sorted(covered),'totalDays':len(required),
            'missing':missing,'failures':failures,'attempted':len(todo),'start':first,'end':days[-1].isoformat()}

# Verified live: ESPN's RSS answers 202 with an empty body, NBA.com's returns 404, HoopsHype blocks bots.
RSS_FEEDS=[('https://www.cbssports.com/rss/headlines/nba/','CBS Sports'),('https://sports.yahoo.com/nba/rss/','Yahoo Sports')]

def rss_news(url, source, limit=40):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=18) as response:root=ET.fromstring(response.read(3_000_000))
    out=[]
    for item in root.findall('.//item')[:limit]:
        val=lambda name:(item.findtext(name) or '').strip()
        link=val('link')
        if link.startswith('https://'):
            out.append({'title':clean_text(val('title')),'url':link,'published':val('pubDate'),'source':source,'description':clean_text(val('description')),'teamIds':[]})
    return out

def collect(today,days_back=35,days_forward=14,history_years=4,cached=None,history_batch=250):
    print("[NBA] Fetching 30 teams",flush=True)
    teams=team_list()
    if len(teams)<28:raise RuntimeError(f'Only {len(teams)} NBA teams returned; refusing incomplete output')
    games={str(g['id']):g for g in as_list(obj(cached).get('games')) if isinstance(g,dict) and g.get('id') and str(g.get('date',''))[:10]>=dt.date(today.year if today.month>=7 else today.year-1,7,1).isoformat()}
    # Daily season fetch below already covers past dates. Only request future
    # fixtures here; do not issue 49 redundant requests on every update.
    dates=[today+dt.timedelta(days=offset) for offset in range(1,days_forward+1)]
    future_errors=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(scoreboard,day):day for day in dates}
        for future in as_completed(futures):
            try:
                for game in future.result():games[game['id']]=game
            except Exception as exc:
                future_errors.append(f'{futures[future]}: {exc}')
    errors=[f"Upcoming fixture request failures: {len(future_errors)}"] if future_errors else []
    try: standing=standings()
    except Exception as e: errors.append('standings: '+str(e));standing=obj(obj(cached).get('standings'))
    try: articles=news()
    except Exception as e: errors.append('news: '+str(e));articles=[]
    print("[NBA] Fetching historical scores",flush=True)
    hist=collect_history(today,history_years,cached=obj(cached).get('history'),cached_days=obj(cached).get('historyDaysFetched'),batch=history_batch)
    history=hist['games']
    # Fetch current-season daily scoreboards, tracking each verified day.
    season_start=dt.date(today.year if today.month>=7 else today.year-1,7,1)
    print("[NBA] Fetching current season day by day",flush=True)
    season_games,season_days,season_failures,season_missing=current_season_games(
        today,season_start,cached=obj(cached).get('games'),
        cached_days=obj(cached).get('seasonDaysFetched'))
    for g in season_games:games[g['id']]=g
    # ESPN includes exhibitions against non-NBA opponents and placeholder
    # fixtures. Keep only genuine NBA-vs-NBA matchups before publishing.
    clean_games, excluded_games=filter_nba_games(games.values(),teams)
    games={str(g['id']):g for g in clean_games}
    history, excluded_history=filter_nba_games(history,teams)
    if excluded_games or excluded_history:
        errors.append(f'Excluded {len(excluded_games)} non-NBA/invalid schedule events and {len(excluded_history)} historical events (IDs: {", ".join((excluded_games+excluded_history)[:8])})')
        print(f'[NBA] Skipped {len(excluded_games)} non-NBA schedule events and {len(excluded_history)} historical events',flush=True)
    if hist['failures']:errors.append(f"Historical fetch failures this run: {len(hist['failures'])} (first: {hist['failures'][0][:240]})")
    if hist['missing']:errors.append(f"Historical coverage incomplete: {len(hist['daysFetched'])} of {hist['totalDays']} days verified; backfilling {len(hist['missing'])} more in later runs")
    if season_failures:errors.append(f'Current-season daily fetch failures: {len(season_failures)}')
    if season_missing:errors.append(f'Current-season days not verified: {len(season_missing)}')
    if len(games)<30:raise RuntimeError('Too few games returned; refusing incomplete output')
    if not any(g.get('completed') for g in season_games):
        errors.append('No current-season completed games in daily collection')
    for feed_url,feed_name in RSS_FEEDS:
        try:
            got=rss_news(feed_url,feed_name)
            if not got:raise ValueError('feed returned no articles')
            articles+=got
        except Exception as exc:errors.append(f'{feed_name} RSS: {exc}')
    print("[NBA] Fetching rosters and player box scores",flush=True)
    rosters,roster_errors=collect_rosters(teams,obj(cached).get('rosters'))
    errors.extend(roster_errors)
    boxscores,box_errors=collect_boxscores(games.values(),obj(cached).get('boxscores'))
    errors.extend(box_errors)
    unique={a['url']:a for a in articles if a.get('url')}
    articles=tag_articles(list(unique.values()),teams)
    for t in teams:t['division']=obj(standing.get(t['id'])).get('division','')
    from validate_data import history_sanity_problems
    history_complete=not hist['missing']
    if history_complete:
        problems=history_sanity_problems(history,hist['start'],hist['end'])
        if problems:
            history_complete=False;errors.extend('History sanity: '+x for x in problems)
    return {'history':history,'historyDaysFetched':hist['daysFetched'],'historyTotalDays':hist['totalDays'],'historyMissingCount':len(hist['missing']),
        'historyStart':hist['start'],'historyEnd':hist['end'],'historyComplete':history_complete,
        'seasonComplete':not season_missing and any(g.get('completed') for g in season_games),'seasonDaysFetched':season_days,'seasonMissingDays':season_missing,'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'seasonStart':season_start.isoformat(),'playerStats':aggregate_player_stats(boxscores,games.values(),season_start),'season':f'{today.year if today.month>=7 else today.year-1}-{str((today.year+1 if today.month>=7 else today.year)%100).zfill(2)}','teams':teams,'rosters':rosters,'boxscores':boxscores,'games':sorted(games.values(),key=lambda g:g['date']),'standings':standing,'news':articles,'warnings':errors,'coverage':{'daysBack':days_back,'daysForward':days_forward}}
def main():
    p=argparse.ArgumentParser();p.add_argument('--date',default=dt.date.today().isoformat());p.add_argument('--days-back',type=int,default=35);p.add_argument('--days-forward',type=int,default=14);p.add_argument('--history-years',type=int,default=4,help='completed seasons of H2H history');p.add_argument('--history-batch',type=int,default=250,help='max historical days fetched per run (0 = all)');p.add_argument('--output',default=str(ROOT/'data'/'nba.json'));a=p.parse_args()
    dest=pathlib.Path(a.output)
    cached=None
    if dest.exists():
        try:
            cached=json.loads(dest.read_text(encoding='utf-8'))
        except (ValueError,OSError):
            pass
    result=collect(dt.date.fromisoformat(a.date),a.days_back,a.days_forward,a.history_years,cached=cached,history_batch=a.history_batch)
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Final boundary: sanitize every game, including cached and merged sources,
    # immediately before validation and publication. ESPN can return exhibition
    # opponents and placeholders with valid-looking event IDs.
    result['games'], rejected = filter_nba_games(result.get('games', []), result['teams'])
    result['history'], rejected_history = filter_nba_games(result.get('history', []), result['teams'])
    if rejected or rejected_history:
        result.setdefault('warnings', []).append(
            f"Final publish filter removed {len(rejected)} schedule and {len(rejected_history)} historical non-NBA games; examples: {', '.join((rejected + rejected_history)[:10])}")
        print(f"[NBA] Final filter: skipped {len(rejected)} invalid schedule events and {len(rejected_history)} invalid history events", flush=True)
    # Validate before replacing the last good local snapshot, not only in CI.
    from validate_data import validate
    problems=validate(result)
    if problems:
        raise RuntimeError('Refusing to replace valid NBA data: '+'; '.join(problems))
    tmp=dest.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        os.replace(tmp,dest)
    finally:
        if tmp.exists(): tmp.unlink()
    print(f"Saved {len(result['teams'])} teams, {len(result['games'])} games, {len(result['news'])} articles; warnings: {result['warnings']}")
if __name__=='__main__':main()
