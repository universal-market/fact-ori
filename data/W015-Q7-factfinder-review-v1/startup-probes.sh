#!/usr/bin/env bash
set -eu
root=$(realpath "$1")
scratch=$(realpath "$2")
mkdir -p "$scratch"
python - "$scratch" <<'PY'
import sqlite3,sys,json,hashlib
from pathlib import Path
p=Path(sys.argv[1]);db=sqlite3.connect(p/'existing.sqlite');db.executescript("CREATE TABLE requests(id TEXT PRIMARY KEY,state TEXT,result TEXT); INSERT INTO requests VALUES('old','processing','retained-result');");db.close();(p/'before.json').write_text(json.dumps({x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in p.glob('*.sqlite*')}))
PY
for state in new existing; do
 for fixture in offline-seed offline-export malformed missing; do
  for repeat in 1 2; do
   label="$state-$fixture-$repeat"
   set +e
   env -i PATH="$PATH" STATE_PATH="$scratch/$state.sqlite" LIBRARY_PATH="$scratch/$fixture.json" PORT=0 MODEL_ORIGIN=http://127.0.0.1:1 EVIDENCE_ORIGIN=http://127.0.0.1:1 timeout 5s node "$root/service/server.mjs" > "$scratch/$label.stdout" 2> "$scratch/$label.stderr"
   code=$?
   set -e
   echo "$code" > "$scratch/$label.status"
  done
 done
done
python - "$scratch" <<'PY'
import json,sys,hashlib,sqlite3
from pathlib import Path
p=Path(sys.argv[1]);checks=[]
for state in ['new','existing']:
 for fixture in ['offline-seed','offline-export','malformed','missing']:
  for repeat in [1,2]:
   label=f'{state}-{fixture}-{repeat}';code=int((p/(label+'.status')).read_text());err=(p/(label+'.stderr')).read_text();out=(p/(label+'.stdout')).read_text();assert code==1,(label,code);assert 'INVALID_PUBLIC_SNAPSHOT' in err,label;assert 'UNTRUSTED_REVIEW_PAYLOAD_MARKER' not in err;assert str(p/(fixture+'.json')) not in err;assert 'listening' not in out;assert 'EPERM' not in err;checks.append(label)
assert not (p/'new.sqlite').exists();checks.append('new-state-never-created')
before=json.loads((p/'before.json').read_text());after={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in p.glob('*.sqlite*')};assert after==before;checks.append('existing-state-and-sidecar-bytes-unchanged')
db=sqlite3.connect(p/'existing.sqlite');assert db.execute('SELECT state,result FROM requests').fetchall()==[('processing','retained-result')];assert [x[1] for x in db.execute('PRAGMA table_info(requests)')]==['id','state','result'];assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='vectors'").fetchone()[0]==0;db.close();checks.append('existing-requests-unmigrated-unreset-no-vectors')
print(json.dumps({'schema_version':1,'task':'FO-W015-Q7','passed':len(checks),'failed':0,'checks':checks,'limits':'Direct shell invalid-startup processes only; no valid HTTP startup or production backend/model test.'},indent=2))
PY
