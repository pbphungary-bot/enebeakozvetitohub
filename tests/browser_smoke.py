"""Run a real Chromium UI smoke test against an isolated synthetic fixture.
The fixture is NEVER packaged as NBA production data.
"""
import contextlib, http.server, json, pathlib, tempfile, threading, datetime as dt
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]

def fixture():
    teams=[{'id':str(i),'name':f'Test Team {i}','abbr':f'T{i}','logo':''} for i in range(1,31)]
    games=[]
    for i in range(1,51):
        h=teams[(i-1)%30];a=teams[i%30]
        games.append({'id':str(i),'date':f'2026-11-{(i%18)+1:02d}T01:00:00Z','completed':True,'seasonType':'2','status':'STATUS_FINAL','detail':'Final','home':{**h,'score':101},'away':{**a,'score':98}})
    return {'teams':teams,'games':games,'history':games,'seasonStart':'2026-07-01','generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'standings':{t['id']:{'stats':{'overall':'5-2'}} for t in teams},'rosters':{t['id']:[] for t in teams},'news':[],'warnings':[]}

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        data=json.dumps(fixture())
        
        html=(ROOT/'index.html').read_text().replace('<script src="config.js"></script>','')
        stub = """<script>
window.NBA_SHARED_NOTES={};
const _notes={};
Object.defineProperty(window,'localStorage',{value:{
  getItem:k=>_notes[k]||null,setItem:(k,v)=>_notes[k]=v,
  key:i=>Object.keys(_notes)[i],get length(){return Object.keys(_notes).length}
}});
window.fetch=async()=>({ok:true,json:async()=>JSON.parse(DATA_JSON)});
</script>""".replace('DATA_JSON',json.dumps(data))
        html=html.replace("<script>\n'use strict';",stub+"<script>\n'use strict';",1)
        page.set_content(html,wait_until='domcontentloaded',timeout=15000)
        page.locator('#home-select').wait_for(timeout=5000)
        assert page.locator('.logo').count()==30
        assert 'Head to head' in page.locator('#app').inner_text()
        page.locator('[data-page="schedule"]').click()
        assert page.locator('#schedule-team').count()==1
        page.locator('#schedule-status').select_option('completed')
        assert page.locator('tbody tr').count()==50
        page.locator('[data-page="standings"]').click()
        assert page.locator('tbody tr').count()==30
        page.locator('[data-page="matchup"]').click()
        page.locator('textarea[data-note="home"]').fill('Test note saved')
        assert page.evaluate("localStorage.getItem('nba-notes:1:2')") is not None
        assert not errors,errors
        print('PASS: Chromium: 30 teams, matchup, schedule, standings, notes persistence; no JS errors')
        browser.close()
if __name__=='__main__':main()
