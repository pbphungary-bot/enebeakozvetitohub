const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const js=html.split('<script>')[1].split('</script>')[0];
const fn=js.match(/function validateNotesImport\(raw\)\{.*?return entries\}/s);
assert.ok(fn,'notes import validator must exist');
const validate=vm.runInNewContext('('+fn[0]+')');
assert.equal(validate({format:'nba-commentator-notes-v1',notes:{'nba-notes:1:2':{'1':'Home','2':'Away'}}}).length,1);
for(const input of [
  {format:'wrong',notes:{}},
  {format:'nba-commentator-notes-v1',notes:JSON.parse('{"__proto__":{}}')},
  {format:'nba-commentator-notes-v1',notes:{'nba-notes:1:2':{'1':5}}},
  {format:'nba-commentator-notes-v1',notes:{'nba-notes:1:2':{'1':'x'.repeat(100001)}}},
  {format:'nba-commentator-notes-v1',notes:{'nba-notes:1:2':[]}},
])assert.throws(()=>validate(input));
console.log('Notes import validation: 6 assertions passed');
