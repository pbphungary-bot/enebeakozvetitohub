# NBA Commentator Center — consolidated release candidate

**Not production-verified.** Automated tests pass locally, but this environment cannot resolve ESPN hosts; a live GitHub Actions refresh and published-site browser test are still required. No fabricated NBA dataset is bundled.

## One-time deployment

Upload the **contents** of this folder to a separate GitHub repository. Include the hidden `.github` directory. Set Settings → Actions → General → Workflow permissions to **Read and write permissions**. Enable Pages on `main` `/ (root)`. The workflow runs automatically on pushes to `main` that change code/tests, on schedule, or manually. It commits `data/nba.json` only when the collector and validator pass.

The first data run can take substantially longer than subsequent runs. Open Actions → Update NBA data to inspect the collector's stage logs. If it fails, download the complete run log; do not repeatedly replace isolated files.

## Known limitations

- ESPN APIs are unofficial and may rate-limit or change.
- Four-year H2H collection uses monthly windows and may be incomplete; the dashboard labels coverage.
- Shared notes require optional Supabase configuration and are not automatically provisioned.
- Official team-site news coverage is incomplete.
- No verified live snapshot is included; the UI cannot display real scores before the first successful refresh.

## Tests

`python -m unittest discover -s tests -v` and `node tests/test_notes_import.js` and `node tests/test_schedule_filter.js`.

---

# NBA Commentator Center — development build

A standalone NBA dashboard retaining the Hungarian dashboard's light cards, dark header, grey team-logo strip, navigation and matchup-oriented workflow.

## Status (important)

**Not production-ready and not feature-complete.** The collector has not been tested against live ESPN responses in this environment because outbound network access is blocked. No NBA data is bundled or fabricated. The UI will show a setup message until data collection succeeds. This is a development build, not the fully verified final product requested.

### Implemented

- 30-team logo strip and navigation (after a successful data refresh)
- Schedule and results from ESPN public feeds
- Matchup selection, recent games, home/away filter, clickable ESPN game links
- Standings fields when the upstream response supplies them
- Recent matchup history **within the downloaded window**, not historical all-time H2H
- Team page with recent-game player box-score drilldown (requires ESPN browser access)
- ESPN news tagged with team IDs
- Two-column notes saved locally per matchup, **not** shared across devices
- GitHub Actions 30-minute scheduled data refresh

### Still required before release

- Verified historical all-time H2H across seasons and playoff splits
- Full-season home/away standings, division rank and robust standings parser verification
- Advanced team and player season statistics and statistical comparison
- NBA.com and official team site news feeds
- Shared notes backend (Supabase or alternative)
- Live integration and browser acceptance testing on the deployed site
- Source availability and licensing review

## Local use

Python 3.12+ and internet access required. No paid API key.

```bash
python scripts/update_nba.py
python -m http.server 8000
```

Open http://localhost:8000. Do not open `index.html` directly as a file because it fetches `data/nba.json`.

## Automated tests

```bash
python -m unittest discover -s tests -v
node --check /tmp/nba_app.js # first extract inline JS to this file
```

## GitHub Pages

Use a **separate** public repository; enable Pages from `main` root, and enable Actions workflow permissions to write repository contents. Manually run `Update NBA data` once before opening the site. GitHub's free scheduled Actions are not guaranteed to run at the exact minute specified.

## Reliability

ESPN endpoints are publicly accessible but unofficial/undocumented for this purpose. They may change, rate-limit, or deny automated requests. The collector writes atomically and will not overwrite the last good dataset if the critical team or game fetch fails. There is no claim of guaranteed uninterrupted free access.

## November 19 development update

- Added historical game collection using monthly ESPN scoreboard windows (default: four years). The UI explicitly labels this as a *limited historical window*, never all-time.
- Added RSS attempts for NBA.com and ESPN, with explicit warnings when unavailable. Official team site coverage is still outstanding.
- Added a statistical comparison for fields supplied by ESPN standings, displaying missing fields as unavailable rather than fabricating numbers.
- Added automated tests for historical month boundaries, failures, and RSS parsing.
- **Live end-to-end verification remains blocked:** this execution environment cannot resolve the ESPN API hosts. This package is not a verified final release.

## Next-stage verification (2026-11-19)

- Hardened W–L record parsing for alternate ESPN standings field names and dash formats.
- Added regression tests for division and conference rank fallback calculation.
- Form and home/away displays now explicitly warn if current-season collection is incomplete.
- **Still not deployment-ready:** live ESPN connectivity, historical completeness, official team news, advanced statistics, and shared notes remain unverified or incomplete.

## Build 6: incremental historical cache

- Historical scoreboard months are now tracked in `historicalMonthsFetched`; completed months are reused on subsequent refreshes, while the current and previous month are refreshed to capture corrections.
- Months are skipped only if a successful prior fetch was explicitly recorded. A month containing zero games is still considered successfully fetched; a failed month is retried.
- The first successful run still requires a complete initial history download. No live-source integration claim is made.
- Regression tests cover historical cache reuse and recent-month refresh.

### Build 7 changes
- Collects player rosters for all 30 teams via ESPN team roster feeds and stores them in `data/nba.json`.
- Team page includes a clickable roster with position, jersey, age and height, linked to player profiles.
- Missing roster feeds produce explicit warnings; previously cached rosters are reused rather than fabricated.
- Live API collection remains unverified in this offline environment; deploy only after an internet-connected GitHub Actions run and live browser QA.

### Build 9: verified corrections
- Classify historical H2H games by source season type (regular season / playoffs / unknown) instead of silently combining categories.
- Keep matchup notes tied to team IDs even if home/away selectors are reversed. Notes remain local to this browser; cross-device sharing is NOT implemented.
- Added three regression tests for season-type classification.
- 24 unit tests and JavaScript syntax check pass locally. Live ESPN integration remains unverified because DNS access is unavailable here.

### Build 10 — cached player box scores
- The collector now caches the 25 most recent completed-game player box scores, allowing those clickable game details to work on GitHub Pages without cross-origin browser calls to ESPN.
- Cached rows are reused on refresh, and failed fetches produce explicit warnings; older games retain an on-demand fallback.
- Three new regression tests cover parsing, caching and failures. 27 unit tests and JavaScript syntax check passed offline.
- **Still not deployment-ready:** live ESPN connectivity, official team news, advanced player season statistics and cross-device shared notes remain unverified/incomplete.


### Build 11 verification (2026-11-19)
- Fixed historical-month coverage flags: failed refreshes are not marked complete.
- Fixed cache retention: previously fetched player box scores survive refreshes.
- GitHub workflow now runs regression tests before updating data.
- 30 offline unit tests passed. Live ESPN collection **could not be tested** because this environment has no DNS/network access.
- The application is **not yet deployment-ready**: live source verification, official-team feeds, advanced player statistics and cross-device notes remain incomplete.

### Build 12 — publication safety gate
- Added `scripts/validate_data.py`: checks unique 30-team coverage, game IDs, valid opponents and scores, date formats, data freshness (36 hours), standings, roster coverage, and current-season completeness.
- GitHub Actions now runs the validation **after collection and before committing**. Invalid or partial data will not replace the last published dataset.
- 36 offline tests passed; JavaScript syntax check passed. Live API and browser integration remain unverified. The validator is intentionally strict: if ESPN omits a critical field, the workflow fails rather than publishing potentially misleading statistics.

### Current development pass — player statistics and season boundaries
- Recent form and team records are restricted to `seasonStart`; historical seasons remain available for H2H.
- Team roster shows PTS/REB/AST averages derived **only from cached current-season box scores**, explicitly marked as partial, not official full-season figures.
- Schedule sorting no longer mutates the source data array.
- No claim of live integration or shared-note completion. Do not publish as verified production without the live acceptance gate.

### Build 15 — portable commentator notes
- Export all matchup notes to a JSON file; import on another browser/device with validation and overwrite confirmation. This is manual transfer, **not live shared notes**.
- Reject invalid note keys, non-text values, oversized notes, and malformed files.
- Node regression tests added to CI; 40 Python unit tests and six notes validation assertions pass.
- Headless Chromium browser smoke test could not complete in this environment (timed out). Live NBA data remains unverified. **Not deployment-ready.**

## Build 17 — release-candidate preparation (2026-11-19)

- Optional cross-device shared notes via Supabase REST, with debounced autosave, explicit reload, local fallback, and visible sync status. To enable, create a Supabase free project, run `scripts/shared_notes.sql` in its SQL editor, then edit `config.js` with the project URL and **publishable/anon** key (never a service-role key). This is a **public editable notes workspace without authentication**: anyone able to access the site can read and overwrite notes. Avoid confidential material. Free-tier quotas and project suspension policies apply. If not configured, browser-local notes and JSON export/import still work.
- HTML news links now accept only http(s) destinations.
- `tests/browser_smoke.py` exercises the actual Chromium UI with synthetic fixture data (30 teams, matchup, schedule, standings, local notes). The fixture is temporary and is **not included as real NBA results**. Run with `python tests/browser_smoke.py` where `playwright` and Chromium are installed.
- Still **NOT verified production-ready**: network isolation prevents a successful live ESPN collector run, and no deployed GitHub Pages URL was provided for end-to-end testing. Advanced official season player statistics, official team feeds and truly all-time H2H are still not implemented/verified. The public Supabase backend cannot be validated until the user creates a project and configures its URL/key.

### Release acceptance checklist

1. In a fresh, separate GitHub repository, upload these files and enable Actions write permission and GitHub Pages.
2. Run `Update NBA data` manually. Confirm the workflow is green, including `Validate refreshed data before publication`, and `data/nba.json` is committed. A failed workflow means **do not release**.
3. Open the published Pages URL and verify all 30 teams, current standings, schedule, one completed game box score, recent H2H, player roster, news links and browser console without errors. Verify dates and totals against ESPN/NBA official pages.
4. If shared notes are needed, configure Supabase as above; test write on one device and reload on another. Do not use private notes with public policies.
5. Check GitHub Actions on the next scheduled run and confirm no feed regression.

The dashboard should not be represented as live-verified or feature-complete until these acceptance steps pass.


## Release audit (Build 18)

**Status: NOT production-verified.** Build 18 adds validation *before* replacing the local data file, so a bad refresh cannot overwrite the last good dataset even if the GitHub workflow later fails. This is a correctness safeguard, not proof that the ESPN endpoints work.

**Required deployment gates:** Run GitHub Actions with live internet access; confirm `data/nba.json` is committed and contains 30 distinct teams, current standings, rosters and current-season completed games; visit the deployed Pages URL and test schedule, matchup, H2H, roster, player drilldown and notes; configure Supabase for shared notes and verify two-device synchronization. No credentials or service role keys should be committed. Historical H2H covers a limited collection window and must not be described as all-time.

## Live collector fix — 2026-11-19
The ESPN scoreboard may include preseason exhibition opponents or placeholder
teams outside the 30 NBA franchises. These are now excluded from the main
schedule and historical matchups before structural validation, and their IDs
are reported in `warnings`. Valid NBA-vs-NBA games are retained. This fix
addresses the GitHub Actions error `Unknown or identical competitors for game
401914130`. Live GitHub Actions execution remains the acceptance test.
