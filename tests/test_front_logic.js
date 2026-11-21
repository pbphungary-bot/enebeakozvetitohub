// Regression tests for the pure front-end logic block in index.html (H2H, preseason, dates, standings).
const fs = require('fs'), vm = require('vm'), assert = require('assert'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = html.match(/\/\*LOGIC-START\*\/([\s\S]*?)\/\*LOGIC-END\*\//);
assert(m, 'LOGIC block markers missing from index.html');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(m[1] + ';this.api={teamInjuries,injuryState,injuryClass,dateOnly,compareRows,SEASON_TYPE,scoreOf,seasonTypeLabel,complete,mergeGames,formGames,regularGames,h2hFrom,h2hSplit,historyCoverage,hydrateHistory,date,dateTime,tipoff,officialRecord,confSeed,splitStat,standingsByConference,record,won}', ctx);
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

console.log(`${n} front-end logic tests passed`);
