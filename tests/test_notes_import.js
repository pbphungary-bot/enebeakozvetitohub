// Notes: import safety, v1 -> v2 migration, per-field merge. Uses the shared logic block of index.html.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = html.match(/\/\*LOGIC-START\*\/([\s\S]*?)\/\*LOGIC-END\*\//);
assert.ok(m, 'logic block must exist');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(m[1] + ';this.api={validateNotesImport,normalizeNotes,mergeNotes,setNote,noteText,noteStamp,appendNote,nonEmptyNotes,NOTE_TEMPLATES,NOTE_MAX}', ctx);
const A = ctx.api;
let n = 0;
const test = (name, fn) => { fn(); n++; };
const plain = x => JSON.parse(JSON.stringify(x));
const V1 = 'nba-commentator-notes-v1', V2 = 'nba-commentator-notes-v2';
const f = (t, u) => ({ t, u });

test('v1 export still imports (original safety assertions)', () => {
  const entries = A.validateNotesImport({ format: V1, notes: { 'nba-notes:1:2': { '1': 'Home', '2': 'Away' } } });
  assert.equal(entries.length, 1);
  assert.equal(entries[0][0], 'nba-notes:1:2');
  assert.deepEqual(plain(entries[0][1]), { v: 2, fields: { '1': f('Home', 0), '2': f('Away', 0) } });
});

test('malformed or hostile imports are rejected', () => {
  for (const input of [
    { format: 'wrong', notes: {} },
    { format: V1, notes: JSON.parse('{"__proto__":{}}') },
    { format: V1, notes: { 'nba-notes:1:2': { '1': 5 } } },
    { format: V1, notes: { 'nba-notes:1:2': { '1': 'x'.repeat(100001) } } },
    { format: V1, notes: { 'nba-notes:1:2': [] } },
    { format: V2, notes: JSON.parse('{"__proto__":{}}') },
    { format: V2, notes: { 'nba-notes:1:2': { v: 2, fields: { matchup: { t: 5, u: 1 } } } } },
    { format: V2, notes: { 'nba-notes:1:2': { v: 2, fields: { matchup: { t: 'x'.repeat(A.NOTE_MAX + 1), u: 1 } } } } },
    { format: V2, notes: { 'nba-notes:1:2': { v: 2, fields: { matchup: { t: 'ok', u: 'later' } } } } },
    { format: V2, notes: { 'nba-notes:1:2': { v: 2, fields: { 'bad key': { t: 'ok', u: 1 } } } } },
    { format: V2, notes: { 'nba-notes:1:2': { v: 1, fields: {} } } },
    { format: V2, notes: { 'nba-notes:1:2': { v: 2, fields: [] } } },
    { format: V2, notes: { 'not-a-key': { v: 2, fields: {} } } },
    { format: V2, notes: [] },
    null, undefined, 'text',
  ]) assert.throws(() => A.validateNotesImport(input), undefined, JSON.stringify(input)?.slice(0, 80));
});

test('a v2 export round-trips and keeps timestamps', () => {
  const entry = { v: 2, fields: { matchup: f('Storyline', 1700000000000), '1': f('Knicks', 5), 'p:42': f('Player', 9) } };
  const out = A.validateNotesImport({ format: V2, notes: { 'nba-notes:1:2': entry } });
  assert.deepEqual(plain(out[0][1]), entry);
});

test('too many matchups or fields are rejected', () => {
  const many = {}; for (let i = 0; i < 501; i++) many[`nba-notes:${i}:${i + 1}`] = { '1': 'x' };
  assert.throws(() => A.validateNotesImport({ format: V1, notes: many }), /Too many/);
  const fields = {}; for (let i = 0; i < 101; i++) fields['p:' + i] = f('x', 1);
  assert.throws(() => A.validateNotesImport({ format: V2, notes: { 'nba-notes:1:2': { v: 2, fields } } }));
});

test('normalize: legacy flat notes migrate with timestamp 0; garbage becomes empty', () => {
  assert.deepEqual(plain(A.normalizeNotes({ '1': 'a', '2': 'b' })), { v: 2, fields: { '1': f('a', 0), '2': f('b', 0) } });
  for (const bad of [null, undefined, 'x', 5, [], { v: 3 }]) assert.deepEqual(plain(A.normalizeNotes(bad)), { v: 2, fields: {} });
});

test('normalize: drops unknown keys and non-text values, and truncates oversized text', () => {
  const out = plain(A.normalizeNotes({ v: 2, fields: { matchup: f('ok', 3), evil: f('no', 1), '1': f(5, 1), 'p:7': f('x'.repeat(A.NOTE_MAX + 50), 2) } }));
  assert.deepEqual(Object.keys(out.fields).sort(), ['matchup', 'p:7']);
  assert.equal(out.fields['p:7'].t.length, A.NOTE_MAX);
});

test('normalize: the legacy home/away keys of very old builds are ignored, not misfiled', () => {
  assert.deepEqual(plain(A.normalizeNotes({ home: 'x', away: 'y' })), { v: 2, fields: {} });
});

test('merge: the later edit wins per field, so two commentators do not overwrite each other', () => {
  const mine = { v: 2, fields: { '1': f('my knicks note', 200), matchup: f('old matchup', 100) } };
  const theirs = { v: 2, fields: { '2': f('their wolves note', 150), matchup: f('newer matchup', 300), '1': f('stale knicks', 50) } };
  const merged = plain(A.mergeNotes(mine, theirs));
  assert.deepEqual(merged.fields, { '1': f('my knicks note', 200), '2': f('their wolves note', 150), matchup: f('newer matchup', 300) });
});

test('merge: is commutative, idempotent and handles exact ties identically on every device', () => {
  const a = { v: 2, fields: { matchup: f('apple', 10), '1': f('x', 5) } };
  const b = { v: 2, fields: { matchup: f('banana', 10), '2': f('y', 7) } };
  assert.deepEqual(plain(A.mergeNotes(a, b)), plain(A.mergeNotes(b, a)));
  assert.deepEqual(plain(A.mergeNotes(A.mergeNotes(a, b), b)), plain(A.mergeNotes(a, b)));
  assert.equal(A.mergeNotes(a, b).fields.matchup.t, 'banana');
});

test('merge: a deliberate clear is an edit and beats older text', () => {
  const merged = A.mergeNotes({ v: 2, fields: { matchup: f('', 500) } }, { v: 2, fields: { matchup: f('old text', 100) } });
  assert.equal(A.noteText(merged, 'matchup'), '');
});

test('merge: works with legacy or missing sides', () => {
  assert.deepEqual(plain(A.mergeNotes({ '1': 'legacy' }, undefined).fields), { '1': f('legacy', 0) });
  assert.deepEqual(plain(A.mergeNotes(null, { v: 2, fields: { matchup: f('m', 4) } }).fields), { matchup: f('m', 4) });
  assert.deepEqual(plain(A.mergeNotes(undefined, undefined)), { v: 2, fields: {} });
});

test('merge: a timestamped edit beats migrated (timestamp 0) text', () => {
  assert.equal(A.noteText(A.mergeNotes({ '1': 'legacy' }, { v: 2, fields: { '1': f('edited', 5) } }), '1'), 'edited');
});

test('setNote records the edit time, rejects unknown keys and does not mutate its input', () => {
  const base = { v: 2, fields: { '1': f('a', 1) } };
  const out = A.setNote(base, 'p:9', 'hello', 777);
  assert.deepEqual(plain(out.fields['p:9']), f('hello', 777));
  assert.deepEqual(plain(base), { v: 2, fields: { '1': f('a', 1) } });
  assert.deepEqual(Object.keys(A.setNote(base, '__proto__', 'x', 1).fields), ['1']);
  assert.equal(A.setNote(base, '1', 'y'.repeat(A.NOTE_MAX + 9), 2).fields['1'].t.length, A.NOTE_MAX);
});

test('noteText and noteStamp read fields safely', () => {
  const notes = { v: 2, fields: { matchup: f('m', Date.UTC(2026, 10, 21, 22, 0)) } };
  assert.equal(A.noteText(notes, 'matchup'), 'm');
  assert.equal(A.noteText(notes, 'p:1'), '');
  assert.equal(A.noteText(undefined, 'matchup'), '');
  assert.equal(A.noteStamp(notes, 'matchup'), '2026-11-21T22:00:00.000Z');
  assert.equal(A.noteStamp(notes, 'p:1'), '');
  assert.equal(A.noteStamp({ '1': 'legacy' }, '1'), ''); // migrated text has no edit time
});

test('appendNote adds lines without clobbering, including onto empty and newline-terminated notes', () => {
  let n1 = A.appendNote(undefined, 'matchup', '• first', 1);
  n1 = A.appendNote(n1, 'matchup', '• second', 2);
  assert.equal(A.noteText(n1, 'matchup'), '• first\n• second');
  const n2 = A.appendNote({ v: 2, fields: { matchup: f('line\n', 1) } }, 'matchup', '• next', 2);
  assert.equal(A.noteText(n2, 'matchup'), 'line\n• next');
});

test('nonEmptyNotes lists only fields with real text (for the printable prep sheet)', () => {
  const list = A.nonEmptyNotes({ v: 2, fields: { matchup: f('m', 1), '1': f('   ', 2), 'p:3': f('p', 3) } });
  assert.deepEqual(plain(list).map(x => x.key).sort(), ['matchup', 'p:3']);
});

test('templates are named, non-empty and fit the note size limit', () => {
  assert.ok(A.NOTE_TEMPLATES.length >= 4);
  const ids = new Set();
  for (const t of A.NOTE_TEMPLATES) { assert.ok(t.id && t.label && t.text.length > 10 && t.text.length < A.NOTE_MAX); ids.add(t.id); }
  assert.equal(ids.size, A.NOTE_TEMPLATES.length);
});

console.log(`Notes validation and merge: ${n} tests passed`);
