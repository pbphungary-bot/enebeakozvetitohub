// Regression tests for the pure front-end logic block in index.html (H2H, preseason, dates, standings).
const fs = require('fs'), vm = require('vm'), assert = require('assert'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = html.match(/\/\*LOGIC-START\*\/([\s\S]*?)\/\*LOGIC-END\*\//);
assert(m, 'LOGIC block markers missing from index.html');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(m[1] + ';this.api={cleanInjury,seasonLabel,buildStorylines,restInfo,nextMeeting,rankOf,leadersBy,streakInfo,ordinal,etDay,boxTeams,parseBoxscore,splitNotices,teamInjuries,injuryState,injuryClass,dateOnly,compareRows,SEASON_TYPE,scoreOf,seasonTypeLabel,complete,mergeGames,formGames,regularGames,h2hFrom,h2hSplit,historyCoverage,hydrateHistory,date,dateTime,tipoff,officialRecord,confSeed,splitStat,standingsByConference,record,won}', ctx);
const A = ctx.api;
let n = 0;
const test = (name, fn) => { fn(); n++; };
const side = (id, score) => ({ id, score });
const game = (id, date, h, a, hs, as, type = '2') => ({ id, date, seasonType: type, completed: true, home: side(h, hs), away: side(a, as) });

test('H2H falls back to current-season games when history is empty (empty array is truthy in JS)', () => {
  const games = [game('1', '2026-11-01T00:00Z', 'A', 'B', 100, 90)];
  assert.deepStrictEqual(Array.from(A.h2hFrom([], games, 'A', 'B'), g => g.id), ['1']);
  assert.deepStrictEqual(Array.from(A.h2hFrom(undefined, games, 'B', 'A'), g => g.id), ['1']);
});

test('H2H merges history with current season and counts each game once (current row wins)', () => {
  const old = game('1', '2025-01-01T00:00Z', 'A', 'B', 100, 90);
  const stale = game('2', '2026-11-01T00:00Z', 'A', 'B', 1, 0);
  const fresh = game('2', '2026-11-01T00:00Z', 'A', 'B', 101, 99);
  const out = A.h2hFrom([old, stale], [fresh], 'A', 'B');
  assert.strictEqual(out.length, 2);
  assert.strictEqual(out[0].home.score, 101); // newest first, fresh row replaced the stale duplicate
});

test('preseason games never count as head-to-head meetings', () => {
  const pre = game('9', '2026-10-05T00:00Z', 'A', 'B', 100, 90, '1');
  assert.strictEqual(A.h2hFrom([pre], [pre], 'A', 'B').length, 0);
});

test('preseason is excluded from form and from regular-season records', () => {
  const games = [
    game('1', '2026-10-05T00:00Z', 'A', 'B', 100, 90, '1'),
    game('2', '2026-10-25T00:00Z', 'A', 'B', 100, 90, '2'),
    game('3', '2026-10-27T00:00Z', 'C', 'A', 100, 90, '2'),
  ];
  assert.deepStrictEqual(Array.from(A.formGames(games, 'A', '2026-07-01'), g => g.id), ['3', '2']);
  assert.strictEqual(A.record(A.regularGames(games, 'A', '2026-07-01'), 'A'), '1–1');
});

test('playoff games count toward form but not the regular-season record', () => {
  const games = [game('1', '2026-10-25T00:00Z', 'A', 'B', 100, 90, '2'), game('2', '2027-04-25T00:00Z', 'A', 'B', 100, 90, '3')];
  assert.strictEqual(A.formGames(games, 'A', '2026-07-01').length, 2);
  assert.strictEqual(A.regularGames(games, 'A', '2026-07-01').length, 1);
});

test('games before the season start are excluded from form', () => {
  assert.strictEqual(A.formGames([game('1', '2026-06-20T00:00Z', 'A', 'B', 1, 0, '3')], 'A', '2026-07-01').length, 0);
});

test('incomplete or unscored games are not completed results', () => {
  assert.strictEqual(A.complete({ completed: true, home: side('A', null), away: side('B', 3) }), false);
  assert.strictEqual(A.complete({ completed: false, home: side('A', 1), away: side('B', 3) }), false);
});

test('H2H split by season type and unclassified', () => {
  const g = [game('1', '2026-01-01T00:00Z', 'A', 'B', 100, 90, '2'), game('2', '2026-01-02T00:00Z', 'B', 'A', 100, 90, '3'), game('3', '2026-01-03T00:00Z', 'A', 'B', 100, 90, '5'), game('4', '2026-01-04T00:00Z', 'A', 'B', 100, 90, '')];
  const s = A.h2hSplit(g, 'A', 'B');
  assert.deepStrictEqual([s.total.a, s.total.b], [3, 1]);
  assert.deepStrictEqual([s.byType['2'].a, s.byType['3'].b, s.byType['5'].a, s.byType.other.n], [1, 1, 1, 1]);
});

test('history coverage never claims completeness unless the collector says so', () => {
  assert.strictEqual(A.historyCoverage({ historyComplete: false, historyDaysFetched: ['2025-01-01'], historyTotalDays: 10 }).complete, false);
  assert.strictEqual(A.historyCoverage({}).complete, false);
  assert.strictEqual(A.historyCoverage({ historyComplete: true, historyDaysFetched: ['x'], historyTotalDays: 1 }).complete, true);
});

test('compact history is hydrated with team names and abbreviations', () => {
  const h = A.hydrateHistory([{ id: '1', date: '2025-01-01T00:00Z', seasonType: '2', home: { id: '10', score: 100 }, away: { id: '11', score: 90 } }], [{ id: '10', name: 'Ten', abbr: 'TEN' }, { id: '11', name: 'Eleven', abbr: 'ELE' }]);
  assert.strictEqual(h[0].home.abbr, 'TEN');
  assert.strictEqual(h[0].away.name, 'Eleven');
  assert.strictEqual(A.complete(h[0]), true);
  assert.deepStrictEqual(Array.from(A.hydrateHistory(undefined, [])), []);
});

test('dates use US Eastern time, not UTC (7 PM ET tip-off belongs to the previous UTC day)', () => {
  assert.strictEqual(A.date('2026-11-21T00:00Z'), 'Nov 20, 2026');
  assert.strictEqual(A.date('2026-07-01T03:30Z'), 'Jun 30, 2026'); // EDT
  assert.strictEqual(A.date('not a date'), '');
});

test('tip-off shows ET and CET with explicit zone labels', () => {
  const t = A.tipoff('2026-11-21T00:00Z');
  assert(/7:00\s?PM EST/.test(t), t);
  assert(/CET/.test(t) && /01:00/.test(t), t);
  assert.strictEqual(A.tipoff(''), '');
});

test('official record is derived from wins/losses when ESPN omits "overall"', () => {
  assert.strictEqual(A.officialRecord({ wins: '13', losses: '3' }), '13–3');
  assert.strictEqual(A.officialRecord({ overall: '9-6' }), '9–6');
  assert.strictEqual(A.officialRecord({}), null);
  assert.strictEqual(A.officialRecord(undefined), null);
});

test('conference seed prefers ESPN playoffSeed over collector-computed rank', () => {
  assert.strictEqual(A.confSeed({ playoffSeed: '1', conferenceRank: '2' }), '1');
  assert.strictEqual(A.confSeed({ conferenceRank: '2' }), '2');
  assert.strictEqual(A.confSeed({}), null);
});

test('split stats are shown when present and absent otherwise', () => {
  assert.strictEqual(A.splitStat({ Home: '6-2' }, 'Home'), '6–2');
  assert.strictEqual(A.splitStat({}, 'Home'), null);
});

test('standings are grouped by conference and ordered by seed', () => {
  const teams = [{ id: '1', name: 'Zed' }, { id: '2', name: 'Alpha' }, { id: '3', name: 'West One' }];
  const standings = {
    '1': { conference: 'Eastern Conference', stats: { playoffSeed: '2' } },
    '2': { conference: 'Eastern Conference', stats: { playoffSeed: '10' } },
    '3': { conference: 'Western Conference', stats: { playoffSeed: '1' } },
  };
  const g = A.standingsByConference(teams, standings);
  assert.deepStrictEqual(Array.from(g, x => x.conference), ['Eastern Conference', 'Western Conference']);
  assert.deepStrictEqual(Array.from(g[0].rows, r => r.team.id), ['1', '2']); // numeric, not lexical (2 before 10)
});

test('teams without standings land in a visible Unassigned group, last-seeded', () => {
  const g = A.standingsByConference([{ id: '1', name: 'A' }], {});
  assert.strictEqual(g[0].conference, 'Unassigned');
  assert.strictEqual(g[0].rows[0].seed, null);
});

test('season type labels', () => {
  assert.strictEqual(A.seasonTypeLabel('3'), 'Playoffs');
  assert.strictEqual(A.seasonTypeLabel(''), 'Unclassified');
});

test('unplayed games show no score, even when a snapshot stored the placeholder 0', () => {
  const sched = { status: 'STATUS_SCHEDULED', home: side('A', 0), away: side('B', 0) };
  assert.strictEqual(A.scoreOf(sched, 'home'), '');
  assert.strictEqual(A.scoreOf({ status: 'STATUS_SCHEDULED', home: side('A', null), away: side('B', null) }, 'away'), '');
});

test('final and in-progress games keep their scores, including a genuine 0', () => {
  assert.strictEqual(A.scoreOf({ status: 'STATUS_FINAL', home: side('A', 101), away: side('B', 99) }, 'home'), 101);
  assert.strictEqual(A.scoreOf({ status: 'STATUS_IN_PROGRESS', home: side('A', 0), away: side('B', 2) }, 'home'), 0);
});

// ---- P1: injuries and team comparison
test('injuries list the most severe first, then by name, and unknown statuses last', () => {
  const data = { injuries: { '1': [
    { name: 'Zed', status: 'Day-To-Day' }, { name: 'Amy', status: 'Out' }, { name: 'Bob', status: 'Out' }, { name: 'Cy', status: 'Weird' }, { name: 'Dee', status: 'Questionable' }] } };
  assert.deepStrictEqual(Array.from(A.teamInjuries(data, '1'), r => r.name), ['Amy', 'Bob', 'Dee', 'Zed', 'Cy']);
  assert.deepStrictEqual(Array.from(A.teamInjuries(data, '2')), []);
  assert.deepStrictEqual(Array.from(A.teamInjuries(undefined, '1')), []);
});

test('injury list is not mutated by sorting', () => {
  const rows = [{ name: 'B', status: 'Out' }, { name: 'A', status: 'Out' }];
  A.teamInjuries({ injuries: { '1': rows } }, '1');
  assert.strictEqual(rows[0].name, 'B');
});

test('injury report availability and staleness are explicit', () => {
  assert.strictEqual(A.injuryState({ injuries: {} }).available, false);
  assert.strictEqual(A.injuryState({}).available, false);
  assert.strictEqual(A.injuryState(undefined).available, false);
  const fresh = A.injuryState({ injuries: { '1': [] }, injuriesAsOf: '2026-11-21T20:00:00Z', generatedAt: '2026-11-21T22:00:00Z' });
  assert.deepStrictEqual([fresh.available, fresh.ageHours, fresh.stale], [true, 2, false]);
  const stale = A.injuryState({ injuries: { '1': [] }, injuriesAsOf: '2026-11-21T10:00:00Z', generatedAt: '2026-11-21T22:00:00Z' });
  assert.deepStrictEqual([stale.ageHours, stale.stale], [12, true]);
  const unknown = A.injuryState({ injuries: { '1': [] }, injuriesAsOf: 'garbage', generatedAt: '2026-11-21T22:00:00Z' });
  assert.deepStrictEqual([unknown.ageHours, unknown.stale], [null, false]);
});

test('an empty list for a team is a valid report (available), not a missing one', () => {
  assert.strictEqual(A.injuryState({ injuries: { '1': [], '2': [] } }).available, true);
});

test('injury status styling: Out is severe, everything else a warning', () => {
  assert.strictEqual(A.injuryClass('Out'), 'loss');
  assert.strictEqual(A.injuryClass('Day-To-Day'), 'warn');
});

test('return dates are calendar dates and never shift across time zones', () => {
  assert.strictEqual(A.dateOnly('2026-11-22'), 'Nov 22, 2026');
  assert.strictEqual(A.dateOnly('2027-07-01'), 'Jul 1, 2027');
  assert.strictEqual(A.dateOnly(''), '');
  assert.strictEqual(A.dateOnly('2026-11-22T10:00Z'), '');
});

test('comparison highlights the better value per row, in the right direction', () => {
  const rows = A.compareRows({ ppg: 122.1, oppPpg: 111.9, diff: 10.2, pace: 99.5, tov: 15 }, { ppg: 110.0, oppPpg: 105.0, diff: 5.0, pace: 97.0, tov: 12 });
  const by = label => rows.flatMap(s => s.rows).find(r => r.label === label);
  assert.deepStrictEqual([by('Points per game').aBetter, by('Points per game').bBetter], [true, false]);
  assert.deepStrictEqual([by('Opponent points per game').aBetter, by('Opponent points per game').bBetter], [false, true]); // lower is better
  assert.deepStrictEqual([by('Turnovers').aBetter, by('Turnovers').bBetter], [false, true]);
  assert.deepStrictEqual([by('Pace (est.)').aBetter, by('Pace (est.)').bBetter], [false, false]); // pace is neutral
});

test('comparison shows signed differentials and dashes for missing values, with no highlight', () => {
  const rows = A.compareRows({ diff: 10.2, net: -3.1 }, { diff: -4.0, ppg: 100 });
  const by = label => rows.flatMap(s => s.rows).find(r => r.label === label);
  assert.deepStrictEqual([by('Point differential').a, by('Point differential').b], ['+10.2', '-4']);
  assert.strictEqual(by('Net rating (est.)').a, '-3.1');
  assert.deepStrictEqual([by('Points per game').a, by('Points per game').b], ['—', '100']);
  assert.deepStrictEqual([by('Points per game').aBetter, by('Points per game').bBetter], [false, false]);
});

test('equal values highlight neither team and a missing team does not crash', () => {
  const rows = A.compareRows({ ppg: 100 }, { ppg: 100 });
  assert.deepStrictEqual([rows[0].rows[0].aBetter, rows[0].rows[0].bBetter], [false, false]);
  assert.strictEqual(A.compareRows(undefined, undefined).length, 4);
  assert.strictEqual(A.compareRows(undefined, { ppg: 100 })[0].rows[0].a, '—');
});

// ---- box scores and data notes
test('box scores: current shape passes through, legacy flat rows are regrouped per team', () => {
  const current = { teams: [{ team: 'A', labels: ['PTS'], players: [{ id: '1' }] }] };
  assert.strictEqual(A.boxTeams(current), current.teams);
  const legacy = [{ team: 'A', id: '1', name: 'X', stats: ['2'], labels: ['PTS'] }, { team: 'A', id: '2', name: 'Y', stats: ['3'], labels: ['PTS'] }, { team: 'B', id: '3', name: 'Z', stats: ['4'], labels: ['PTS'] }];
  const t = A.boxTeams(legacy);
  assert.deepStrictEqual([t.length, t[0].players.length, t[0].labels[0], t[1].team], [2, 2, 'PTS', 'B']);
  assert.deepStrictEqual(Array.from(A.boxTeams(null)), []);
  assert.deepStrictEqual(Array.from(A.boxTeams(undefined)), []);
  assert.deepStrictEqual(Array.from(A.boxTeams([null])), []);
});

test('browser fallback parsing matches the collector shape and skips id-less rows', () => {
  const raw = { boxscore: { players: [{ team: { displayName: 'Knicks' }, statistics: [{ labels: ['MIN', 'PTS'], athletes: [{ athlete: { id: 7, displayName: 'P' }, stats: ['30', '21'] }, { athlete: { displayName: 'No id' }, stats: ['1', '1'] }] }] }] } };
  const t = A.parseBoxscore(raw);
  assert.deepStrictEqual([t.length, t[0].team, t[0].labels.join(), t[0].players.length, t[0].players[0].id], [1, 'Knicks', 'MIN,PTS', 1, '7']);
  assert.deepStrictEqual(Array.from(A.parseBoxscore({})), []);
});

test('only core-data failures are prominent; everything else is a collapsed data note', () => {
  const n = A.splitNotices(['standings: HTTP 500', 'Historical coverage incomplete: 500 of 1093 days', 'ESPN RSS: empty', 'Current-season days not verified: 2',
    'Upcoming fixture request failures: 3', 'ATL roster unavailable: x', 'Box scores: 20 of 150 recent games cached; 130 more will be added on later refreshes', 'Excluded 4 non-NBA events']);
  assert.deepStrictEqual(Array.from(n.critical), ['standings: HTTP 500', 'Current-season days not verified: 2', 'Upcoming fixture request failures: 3', 'ATL roster unavailable: x']);
  assert.strictEqual(n.info.length, 4);
  assert.deepStrictEqual([A.splitNotices(undefined).critical.length, A.splitNotices([]).info.length, A.splitNotices([null, '']).info.length], [0, 0, 0]);
});

// ---- P2.1 storylines
const TEAMS2 = [{ id: '1', name: 'New York Knicks', abbr: 'NYK' }, { id: '2', name: 'Minnesota Timberwolves', abbr: 'MIN' }];
const mkg = (id, dateIso, h, a, hs, as, type = '2', completed = true, status = completed ? 'STATUS_FINAL' : 'STATUS_SCHEDULED') =>
  ({ id, date: dateIso, seasonType: type, completed, status, home: { id: h, score: completed ? hs : null }, away: { id: a, score: completed ? as : null } });
const baseCtx = (over = {}) => ({
  home: '1', away: '2', teams: TEAMS2, games: [], h2h: [], seasonStart: '2026-07-01', asOf: '2026-11-21T12:00Z', seasonComplete: true,
  standings: { '1': { conference: 'Eastern Conference', division: 'Atlantic', stats: { wins: '9', losses: '6', playoffSeed: '6', streak: 'W2', Home: '4-3' } },
               '2': { conference: 'Western Conference', division: 'Northwest', stats: { wins: '11', losses: '5', playoffSeed: '5', streak: 'L1', Road: '4-2' } } },
  ...over });
const lines = (c, group) => Array.from(A.buildStorylines(c)).filter(x => !group || x.group === group).map(x => x.text);
const has = (arr, re) => arr.some(t => re.test(t));

test('storylines: standings context and relation', () => {
  const t = lines(baseCtx(), 'Matchup');
  assert.strictEqual(t[0], 'NYK 9–6 (6th seed, Eastern Conference) vs MIN 11–5 (5th seed, Western Conference).');
  assert.strictEqual(t[1], 'Interconference matchup.');
  const rivals = baseCtx(); rivals.standings['2'] = { conference: 'Eastern Conference', division: 'Atlantic', stats: { wins: '1', losses: '1' } };
  assert.strictEqual(lines(rivals, 'Matchup')[1], 'Division rivals (Atlantic).');
  rivals.standings['2'].division = 'Central';
  assert.strictEqual(lines(rivals, 'Matchup')[1], 'Conference matchup.');
});

test('storylines: nothing is invented when standings are missing', () => {
  assert.deepStrictEqual(lines(baseCtx({ standings: {} }), 'Matchup'), []);
});

test('storylines: season series, last meeting with ET date, winner, score and venue', () => {
  const h2h = [mkg('b', '2026-11-21T00:30Z', '2', '1', 108, 99), mkg('a', '2026-11-02T01:00Z', '1', '2', 112, 100)]; // newest first
  const t = lines(baseCtx({ h2h }), 'Head to head');
  assert.strictEqual(t[0], 'Season series tied 1–1.');
  assert.strictEqual(t[1], 'Last meeting Nov 20, 2026: MIN won 108–99 at MIN.'); // 00:30Z is still Nov 20 in New York
  const lead = lines(baseCtx({ h2h: [h2h[1]] }), 'Head to head');
  assert.strictEqual(lead[0], 'Season series: NYK lead 1–0.');
});

test('storylines: "no meetings yet" only when the current season is fully collected', () => {
  assert.ok(has(lines(baseCtx(), 'Head to head'), /No meetings yet this season/));
  assert.ok(!has(lines(baseCtx({ seasonComplete: false }), 'Head to head'), /No meetings yet/));
});

test('storylines: previous seasons are not mistaken for this season\'s series', () => {
  const old = [mkg('x', '2025-01-10T00:00Z', '1', '2', 100, 90)];
  const t = lines(baseCtx({ h2h: old }), 'Head to head');
  assert.ok(has(t, /No meetings yet this season/)); assert.ok(!has(t, /Season series/));
});

test('storylines: next meeting appears only for a scheduled game between the two teams', () => {
  const sched = mkg('n', '2026-11-29T01:00Z', '2', '1', 0, 0, '2', false);
  assert.ok(has(lines(baseCtx({ games: [sched] }), 'Head to head'), /^Next meeting: Nov 28, 2026, 8:00 PM EST, NYK at MIN\.$/));
  assert.ok(!has(lines(baseCtx({ games: [mkg('o', '2026-11-29T01:00Z', '2', '3', 0, 0, '2', false)] }), 'Head to head'), /Next meeting/));
  assert.ok(!has(lines(baseCtx({ games: [mkg('p', '2026-11-01T01:00Z', '2', '1', 0, 0, '2', false)] }), 'Head to head'), /Next meeting/)); // in the past
});

test('storylines: multi-season record needs a verified-complete history', () => {
  const h2h = [mkg('1', '2025-12-01T00:00Z', '1', '2', 120, 90), mkg('2', '2025-05-01T00:00Z', '2', '1', 100, 99, '3'), mkg('3', '2024-12-01T00:00Z', '1', '2', 100, 101)];
  assert.ok(!has(lines(baseCtx({ h2h }), 'Head to head'), /Since/));
  assert.ok(!has(lines(baseCtx({ h2h, historyComplete: false }), 'Head to head'), /Since/));
  const t = lines(baseCtx({ h2h, historyComplete: true, historyStart: '2022-10-01' }), 'Head to head');
  assert.ok(t.includes('Since the 2022–23 season: NYK 1–2 in 3 meetings, including 1 playoff game (NYK 0–1).'), t.join(' | '));
  assert.ok(has(t, /^Largest margin in the window: NYK by 30 on Nov 30, 2025\.$/));
});

test('storylines: streaks only from three games', () => {
  const t = c => lines(c, 'Form').filter(x => /straight/.test(x));
  assert.deepStrictEqual(t(baseCtx()), []);
  const c = baseCtx(); c.standings['1'].stats.streak = 'W4'; c.standings['2'].stats.streak = 'L5';
  assert.deepStrictEqual(t(c), ['NYK have won 4 straight.', 'MIN have lost 5 straight.']);
});

test('storylines: last-10 line needs five games and reports record, points and margin', () => {
  const g = [];
  for (let i = 0; i < 6; i++) g.push(mkg('g' + i, `2026-11-${String(10 + i).padStart(2, '0')}T01:00Z`, '1', '9', i < 4 ? 110 : 100, i < 4 ? 100 : 105));
  const t = lines(baseCtx({ games: g }), 'Form');
  assert.ok(t.includes('NYK are 4–2 in their last 6, averaging 106.7 points (+5.0 per game).'), t.join(' | '));
  assert.ok(!has(lines(baseCtx({ games: g.slice(0, 4) }), 'Form'), /last/));
});

test('storylines: preseason games never feed form lines', () => {
  const g = []; for (let i = 0; i < 6; i++) g.push(mkg('p' + i, `2026-10-0${i + 1}T01:00Z`, '1', '9', 100, 90, '1'));
  assert.ok(!has(lines(baseCtx({ games: g }), 'Form'), /last/));
});

test('storylines: home and road records need both official splits', () => {
  assert.ok(has(lines(baseCtx(), 'Form'), /^NYK are 4–3 at home; MIN are 4–2 on the road\.$/));
  const c = baseCtx(); delete c.standings['2'].stats.Road;
  assert.ok(!has(lines(c, 'Form'), /at home/));
});

test('rest: back-to-back and rest days are counted in New York days', () => {
  const games = [mkg('r1', '2026-11-21T00:30Z', '1', '9', 100, 90)]; // played Nov 20 ET
  assert.deepStrictEqual(Object.assign({}, A.restInfo(games, '1', '2026-11-22T01:00Z')), { restDays: 0, lastDay: '2026-11-20', last7: 1 });
  assert.strictEqual(A.restInfo(games, '1', '2026-11-22T01:00Z').restDays, 0);   // plays Nov 21 ET: back-to-back
  assert.strictEqual(A.restInfo(games, '1', '2026-11-24T01:00Z').restDays, 2);   // plays Nov 23 ET: the 21st and 22nd are free
  assert.strictEqual(A.restInfo(games, '2', '2026-11-24T01:00Z'), null);          // never played
});

test('rest: games after the reference or in preseason do not count', () => {
  const games = [mkg('a', '2026-11-30T01:00Z', '1', '9', 1, 0), mkg('b', '2026-10-05T01:00Z', '1', '9', 1, 0, '1')];
  assert.strictEqual(A.restInfo(games, '1', '2026-11-22T01:00Z'), null);
});

test('storylines: rest lines appear only when a meeting is scheduled', () => {
  const sched = mkg('n', '2026-11-22T01:00Z', '2', '1', 0, 0, '2', false);
  const prior = [mkg('p1', '2026-11-21T00:30Z', '1', '9', 100, 90), mkg('p2', '2026-11-17T01:00Z', '2', '8', 100, 90)];
  const t = lines(baseCtx({ games: [sched, ...prior] }), 'Rest & schedule');
  assert.deepStrictEqual(t, ['NYK will be on a back-to-back.', 'MIN will have 4 days of rest.']);
  assert.deepStrictEqual(lines(baseCtx({ games: prior }), 'Rest & schedule'), []);
});

const league = (fn) => Object.fromEntries(Array.from({ length: 30 }, (_, i) => [String(i + 1), fn(i + 1)]));
test('rank: 1 is best, direction respected, and needs a (nearly) full league', () => {
  const ts = league(i => ({ ppg: 100 + i, oppPpg: 100 + i }));
  assert.strictEqual(A.rankOf(ts, 'ppg', '30', 'high'), 1);
  assert.strictEqual(A.rankOf(ts, 'oppPpg', '1', 'low'), 1);
  assert.strictEqual(A.rankOf(ts, 'ppg', '1', 'high'), 30);
  assert.strictEqual(A.rankOf({ '1': { ppg: 1 } }, 'ppg', '1', 'high'), null);
  assert.strictEqual(A.rankOf(ts, 'missing', '1', 'high'), null);
});

test('storylines: strengths and pace clash are shown only when notable', () => {
  const ts = league(i => ({ ppg: 100 + i, oppPpg: 100 + i, pace: 90 + i }));
  const t = lines(baseCtx({ teamStats: ts }), 'Team strengths');
  // team 1 is the worst offence (30th) and best defence (1st); team 2 is 29th offence / 2nd defence
  assert.ok(has(t, /^NYK: offense 30th \(101 ppg\), defense 1st \(101 allowed\)\.$/), t.join(' | '));
  assert.ok(has(t, /^MIN: offense 29th \(102 ppg\), defense 2nd \(102 allowed\)\.$/), t.join(' | '));
  assert.ok(!has(lines(baseCtx({ teamStats: league(i => ({ ppg: 100 + i, oppPpg: 100 + (i % 15) + 7, pace: 100 })) }), 'Team strengths'), /Pace clash/));
  const clash = lines(baseCtx({ teamStats: league(i => ({ ppg: 110, oppPpg: 110, pace: i === 1 ? 105 : i === 2 ? 95 : 100 })) }), 'Team strengths');
  assert.ok(has(clash, /^Pace clash: NYK 1st in pace \(105\) vs MIN 30th \(95\), estimated\.$/), clash.join(' | '));
});

test('storylines: mid-table teams generate no strength lines', () => {
  const ts = league(i => ({ ppg: 100 + i, oppPpg: 100 + i, pace: 100 }));
  ts['1'] = { ppg: 115, oppPpg: 115, pace: 100 }; ts['2'] = { ppg: 114, oppPpg: 114, pace: 100 };
  assert.deepStrictEqual(lines(baseCtx({ teamStats: ts }), 'Team strengths'), []);
});

test('leaders: ranked per stat, ignoring players with too few games or missing values', () => {
  const roster = [{ id: 'a', name: 'Ann' }, { id: 'b', name: 'Bo' }, { id: 'c', name: 'Cy' }, { id: 'd', name: 'Di' }];
  const ps = { a: { gp: 10, pts: 20 }, b: { gp: 10, pts: 25 }, c: { gp: 2, pts: 40 }, d: { gp: 9 } };
  assert.deepStrictEqual(Array.from(A.leadersBy(ps, roster, 'pts'), r => r.name), ['Bo', 'Ann']);
  assert.deepStrictEqual(Array.from(A.leadersBy(undefined, roster, 'pts')), []);
});

const roster1 = [{ id: 'p1', name: 'Jalen Brunson' }, { id: 'p2', name: 'Karl-Anthony Towns' }, { id: 'p3', name: 'Josh Hart' }, { id: 'p4', name: 'Bench Guy' }];
const ps1 = { p1: { gp: 15, pts: 27.3, reb: 3.1, ast: 7.4 }, p2: { gp: 15, pts: 21.0, reb: 12.2, ast: 3.0 }, p3: { gp: 15, pts: 11.0, reb: 8.1, ast: 4.2 }, p4: { gp: 15, pts: 2.0, reb: 1.0, ast: 0.5 } };

test('storylines: team leaders by points, rebounds and assists', () => {
  const t = lines(baseCtx({ rosters: { '1': roster1 }, playerSeason: ps1 }), 'Players');
  assert.deepStrictEqual(t, ['NYK leaders: Jalen Brunson 27.3 pts, Karl-Anthony Towns 12.2 reb, Jalen Brunson 7.4 ast.']);
});

test('storylines: availability names a top-3 scorer who is out, doubtful or day-to-day', () => {
  const c = baseCtx({ rosters: { '1': roster1 }, playerSeason: ps1, injuries: { '1': [
    { playerId: 'p1', name: 'Jalen Brunson', status: 'Out', injury: 'Right Ankle Sprain' },
    { name: 'Karl-Anthony Towns', status: 'Day-To-Day', injury: 'Knee' },       // matched by name
    { playerId: 'p4', name: 'Bench Guy', status: 'Out', injury: 'Back' }] } });  // not a top-3 scorer
  const t = lines(c, 'Availability');
  assert.deepStrictEqual(t, ["NYK's leading scorer Jalen Brunson (27.3 ppg) is out (right ankle sprain).", "NYK's 2nd-leading scorer Karl-Anthony Towns (21.0 ppg) is day-to-day (knee)."]);
});

test('storylines: three or more players out is called out; two is not', () => {
  const mk = n => baseCtx({ injuries: { '2': Array.from({ length: n }, (_, i) => ({ name: 'P' + i, status: 'Out' })) } });
  assert.deepStrictEqual(lines(mk(3), 'Availability'), ['MIN have 3 players listed out.']);
  assert.deepStrictEqual(lines(mk(2), 'Availability'), []);
});

test('storylines: no injury line for a healthy or questionable-only roster', () => {
  const c = baseCtx({ rosters: { '1': roster1 }, playerSeason: ps1, injuries: { '1': [{ playerId: 'p1', name: 'Jalen Brunson', status: 'Questionable' }] } });
  assert.deepStrictEqual(lines(c, 'Availability'), []);
});

test('storylines: degenerate input yields no lines and never throws', () => {
  assert.deepStrictEqual(Array.from(A.buildStorylines({})), []);
  assert.deepStrictEqual(Array.from(A.buildStorylines({ home: '1', away: '1', teams: TEAMS2 })), []);
  assert.doesNotThrow(() => A.buildStorylines({ home: '1', away: '2' }));
  assert.doesNotThrow(() => A.buildStorylines(baseCtx({ standings: undefined, teamStats: null, playerSeason: null, rosters: null, injuries: null })));
});

test('storylines: no line ever contains undefined, NaN or null', () => {
  const g = []; for (let i = 0; i < 8; i++) g.push(mkg('s' + i, `2026-11-${String(5 + i).padStart(2, '0')}T01:00Z`, '1', '2', 100 + i, 99));
  const c = baseCtx({ games: [...g, mkg('n', '2026-11-29T01:00Z', '2', '1', 0, 0, '2', false)], h2h: g.slice().reverse(), historyComplete: true, historyStart: '2022-10-01',
    teamStats: league(i => ({ ppg: 100 + i, oppPpg: 100 + i, pace: 100 + i })), rosters: { '1': roster1 }, playerSeason: ps1, injuries: { '1': [{ playerId: 'p1', name: 'Jalen Brunson', status: 'Out' }] } });
  const all = lines(c);
  assert.ok(all.length >= 8, all.length);
  for (const line of all) assert.ok(typeof line === 'string' && line.length > 5 && !/undefined|NaN|null|\[object/.test(line), line);
});

test('helpers: ordinals, streak parsing and New York calendar days', () => {
  assert.deepStrictEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 30].map(A.ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '30th']);
  assert.deepStrictEqual([A.streakInfo({ streak: 'W4' }).n, A.streakInfo({ streak: 'L12' }).type, A.streakInfo({ streak: '' }), A.streakInfo(undefined)], [4, 'L', null, null]);
  assert.strictEqual(A.etDay('2026-11-21T00:30Z'), '2026-11-20');
  assert.strictEqual(A.etDay('garbage'), '');
});

test('numbers keep one decimal, so whole values do not lose their .0', () => {
  const roster = [{ id: 'a', name: 'Ann' }];
  const t = lines(baseCtx({ rosters: { '1': roster }, playerSeason: { a: { gp: 9, pts: 20, reb: 7, ast: 5.5 } } }), 'Players');
  assert.deepStrictEqual(t, ['NYK leaders: Ann 20.0 pts, Ann 7.0 reb, Ann 5.5 ast.']);
});

test('ESPN\'s "Not Specified" injury placeholder is never shown', () => {
  assert.strictEqual(A.cleanInjury('Left Hamstring Not Specified'), 'Left Hamstring');
  assert.strictEqual(A.cleanInjury('Not Specified'), '');
  assert.strictEqual(A.cleanInjury('Right Knee Surgery'), 'Right Knee Surgery');
  assert.strictEqual(A.cleanInjury(undefined), '');
  const c = baseCtx({ rosters: { '1': roster1 }, playerSeason: ps1, injuries: { '1': [{ playerId: 'p2', name: 'Karl-Anthony Towns', status: 'Out', injury: 'Left Hamstring Not Specified' }] } });
  assert.deepStrictEqual(lines(c, 'Availability'), ["NYK's 2nd-leading scorer Karl-Anthony Towns (21.0 ppg) is out (left hamstring)."]);
  const bare = baseCtx({ rosters: { '1': roster1 }, playerSeason: ps1, injuries: { '1': [{ playerId: 'p2', name: 'Karl-Anthony Towns', status: 'Out', injury: 'Not Specified' }] } });
  assert.deepStrictEqual(lines(bare, 'Availability'), ["NYK's 2nd-leading scorer Karl-Anthony Towns (21.0 ppg) is out."]);
});

test('season labels', () => {
  assert.strictEqual(A.seasonLabel('2022-10-01'), 'the 2022–23 season');
  assert.strictEqual(A.seasonLabel('1999-10-01'), 'the 1999–00 season');
  assert.strictEqual(A.seasonLabel(''), 'the start of the window');
  assert.strictEqual(A.seasonLabel(undefined), 'the start of the window');
});

console.log(`${n} front-end logic tests passed`);
