# NBA Commentator Center

A research dashboard for basketball broadcasters: pick any two teams and get head-to-head history, form, standings context, injuries, player and team statistics, auto-generated storylines, news and shared notes on one page.

It is a static site (GitHub Pages) fed by a scheduled GitHub Action that collects public ESPN data into `data/nba.json`. There is no server and no API key.

## What it shows

| Page | Contents |
| --- | --- |
| **Matchup analysis** | Storylines & talking points · head to head (four completed seasons + current, regular season / play-in / playoffs) · injury report · last-10 form with home/road filter · previous meetings · team comparison · news · commentator notes · printable prep sheet |
| **Schedule** | Every game with ET date and ET · CET tip-off, type (preseason / regular / playoffs), status and scores |
| **Standings** | By conference, ordered by ESPN's playoff seed: record, games behind, division, division rank, home, road, last 10, streak |
| **Team & player stats** | Roster with official per-game season averages, injuries, recent games with labelled player box scores |

All times are shown in US Eastern (the league schedule) with Central European time for tip-off.

### Honesty rules

The site never invents numbers. Missing values are shown as `—`. Anything estimated is labelled: pace and offensive/defensive ratings are estimated from box-score averages (possessions ≈ FGA − OREB + TO + 0.44 × FTA), not official tracking data. A storyline is shown only if the data behind it exists. Head-to-head totals are labelled **Partial** until the history collector has verified every day of the window.

## Data pipeline

`.github/workflows/update.yml` runs on a schedule (`13,43 * * * *`; GitHub runs it roughly hourly), on pushes to `main` that change `scripts/`, `tests/` or the workflow, and manually. Steps: run all tests → `scripts/update_nba.py` → `scripts/validate_data.py` → commit `data/nba.json` only if validation passed. A failed collection or validation never replaces the last good snapshot.

Sources (all unofficial public endpoints, so they can change or rate-limit):

- **ESPN site API**: teams, scoreboards (one request per day), rosters, injuries, box scores, news
- **ESPN web API**: standings (with divisions), league-wide player and team season statistics
- **CBS Sports and Yahoo Sports RSS**: extra headlines (links only)

Things worth knowing about the collector:

- ESPN rejects date-range scoreboard requests with HTTP 400, so history is collected **one day at a time**, 250 days per run (newest first), until the four-season window (Oct–Jun of each completed season) is fully verified. Each run reports its coverage.
- Each optional stage (player stats, team stats, injuries, news, box scores) fails independently: the last good value is kept and a warning recorded.
- Box scores are kept only for each team's last 10 completed games (bounded size); at most 40 missing ones are fetched per run.
- The validator requires 30 teams with conference, division and record; collected regular-season results must match ESPN's official records; history may be partial but can never be marked complete unless each season has a plausible number of games.

### Running it locally

Python 3.12+; no dependencies.

```bash
python scripts/update_nba.py        # writes data/nba.json (needs internet)
python scripts/validate_data.py     # checks it
python -m http.server 8000          # then open http://localhost:8000
```

Do not open `index.html` as a file: it fetches `data/nba.json`. `python scripts/summarize_data.py data/nba.json` prints a coverage summary.

## Deployment (GitHub Pages)

1. Settings → Pages: deploy from branch `main`, folder `/ (root)`.
2. Settings → Actions → General → Workflow permissions: **Read and write**.
3. Run **Update NBA data** once from the Actions tab, then open the Pages URL.

## Commentator notes

Notes are stored per field (team, matchup, player), each with an edit time, so edits merge field by field and the later edit wins. They are saved in the browser and can be exported/imported as JSON (imports merge, they do not overwrite).

**Shared notes (optional, not yet access-controlled).** Create a Supabase project, run `scripts/shared_notes.sql`, and fill `config.js` with the project URL and the *publishable/anon* key (never a service-role key). With the current policies **anyone who can open the site can read and change the notes**, so do not store confidential material. Restricting this to authorized commentators requires Supabase Auth and row-level policies (planned, not implemented).

## Tests

```bash
python -m unittest discover -s tests -v
node tests/test_front_logic.js
node tests/test_notes_import.js
node tests/test_schedule_filter.js
```

The front-end's pure logic (head to head, form, standings, injuries, comparison, storylines, notes merge) lives in one marked block of `index.html` (`/*LOGIC-START*/ … /*LOGIC-END*/`) that the Node tests load directly. `tests/test_pipeline_end_to_end.py` runs the real collector against a synthetic ESPN and checks the output passes the validator. `tests/browser_smoke.py` is an optional Chromium smoke test (needs Playwright; not run in CI).

`.github/workflows/diagnose-espn.yml` is a **read-only** helper that runs only on `claude/**` branches or manually: it probes ESPN's responses and dry-runs the collector into a temp file (never `data/nba.json`), so collector changes can be checked against live ESPN before merging.

## Known limitations

- ESPN's endpoints are unofficial; a format change can break a stage (each stage reports its failure and keeps the last good data).
- ESPN lists 1,230–1,231 regular-season games per past season; the extra game is likely a cup final that does not count in official records.
- Official team-site news and career statistics are not collected.
- Source availability and licensing have not been reviewed; headlines are linked, never copied in full.
