import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'exact-source'
sys.path.insert(0, str(root / 'scripts'))
from export_api_seed import build_snapshot, require_api_claim_id
from export_public_snapshot import export_public
from library_view import load_view

results = []
def record(name, passed, detail=None):
    assert passed, (name, detail)
    results.append({'name': name, 'pass': passed, 'detail': detail})

valid = ['C0', 'C004', 'C007a', 'C13', 'C0001z']
invalid = ['W026-A', '', 'C', 'c004', 'C004AA', 'C004A', 'C004aa',
           'C004\n', 'C004\r', 'C004\r\n', 'C004\u2028', 'C004\u2029',
           ' C004', 'C004 ', 'C٤', 'C４', 'Ｃ004', 'C-1', 'C+1', 'C1.0',
           'C1/a', 'C1%0A', 'C1\x00', None, 1, True, [], {}]
for value in valid + invalid:
    try:
        require_api_claim_id(value)
        accepted = True
    except ValueError:
        accepted = False
    record('identifier:' + repr(value), accepted == (value in valid), {'accepted': accepted})

# Compare actual URL pathname handling; encoded controls are not decoded by route.
ids = [x for x in valid + invalid if isinstance(x, str)]
js = '''const ids=JSON.parse(process.argv[1]);
console.log(JSON.stringify(ids.map(id=>({id,raw:/^C[0-9]+[a-z]?$/.test(id),
path:/^C[0-9]+[a-z]?$/.test(new URL('https://example.invalid/v1/records/'+encodeURIComponent(id)).pathname.slice('/v1/records/'.length))}))));'''
node = subprocess.run(['node', '-e', js, json.dumps(ids)], capture_output=True, text=True, check=True)
url_results = json.loads(node.stdout)
record('http-path-domain', all(x['path'] == (x['id'] in valid) for x in url_results), url_results)
record('raw-http-regex-domain', all(x['raw'] == (x['id'] in valid) for x in url_results))

with tempfile.TemporaryDirectory() as td:
    p=Path(td); d=p/'data'; d.mkdir()
    def write(records, routes):
        (d/'library-inputs.json').write_text(json.dumps({'bundles':['test.json']}))
        (d/'test.json').write_text(json.dumps({'records':records,'reviews':[]}))
        (d/'query-catalog.json').write_text(json.dumps({'routing_review_status':'reviewed','routes':routes}))
        (d/'curation-events.json').write_text(json.dumps({'curation_events':[]}))
    for kind in ['unselected-record','historical-record','claim-route']:
        for export in [build_snapshot, export_public]:
            records = [{'id':'C007a','version':1}] if kind=='historical-record' else []
            routes=[]
            if kind=='claim-route': routes=[{'kind':'claim','claim_id':'W026-A','questions':[]}]
            else: records.append({'id':'W026-A','version':2})
            write(records,routes)
            with patch('export_api_seed.load_view', return_value={'claims':[]}):
                try: export(p); rejected=False
                except ValueError as e: rejected='C-number' in str(e)
            record(kind+':'+export.__name__,rejected)
    for label, records, routes in [
        ('empty',[],[]),
        ('clarification',[],[{'kind':'clarify','questions':['Ambiguous?'],'clarification':'Specify scope.'}]),
        ('suffix-history',[{'id':'C007a','version':1}],[])]:
        write(records,routes)
        with patch('export_api_seed.load_view',return_value={'claims':[]}):
            seed=build_snapshot(p); public=export_public(p)
        record(label+':both-exports',len(seed['versions'])==len(records) and len(public['exact_mappings'])==len(routes))

# Real validated fixture: append an unselected task-local record and its post revision.
with tempfile.TemporaryDirectory() as td:
    p=Path(td);d=p/'data';d.mkdir()
    for name in ['pilot-001.json','C002-v2-review.json','pilot-001-v1-public-snapshot.json']:
        (d/name).write_bytes((root/'data'/name).read_bytes())
    bundle=json.loads((d/'pilot-001.json').read_text())
    candidate=copy.deepcopy(bundle['records'][0]);candidate.update(id='W026-A',tilori_post_id='77777777-7777-4777-8777-777777777777')
    bundle['records'].append(candidate);(d/'pilot-001.json').write_text(json.dumps(bundle))
    posts=json.loads((d/'pilot-001-v1-public-snapshot.json').read_text());posts['posts'].append({'post_id':candidate['tilori_post_id'],'post_revision':1});(d/'pilot-001-v1-public-snapshot.json').write_text(json.dumps(posts))
    v2=json.loads((d/'C002-v2-review.json').read_text())['records'][0]
    (d/'v2.json').write_text(json.dumps(v2))
    (d/'library-inputs.json').write_text(json.dumps({'schema_version':1,'bundles':['pilot-001.json','C002-v2-review.json'],'post_snapshots':['pilot-001-v1-public-snapshot.json'],'record_snapshots':['v2.json']}))
    (d/'curation-events.json').write_text(json.dumps({'schema_version':1,'curation_events':[]}))
    (d/'query-catalog.json').write_text(json.dumps({'routing_review_status':'reviewed','routes':[]}))
    view=load_view(p)
    record('real-unselected-task-local-passes-lower-level',any(x['claim_id']=='W026-A' and x['selected_version'] is None for x in view['claims']))
    for export in [build_snapshot,export_public]:
        try: export(p);rejected=False
        except ValueError as e: rejected='C-number' in str(e)
        record('real-unselected-task-local-rejected:'+export.__name__,rejected)

snapshot=export_public(root)
expected=(root/'public/library.json').read_bytes()
encoded=(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n').encode()
record('checked-in-public-snapshot-serialization-observed',True,{'cli_serialization_byte_equal':encoded==expected,'cli_bytes_sha256':hashlib.sha256(encoded).hexdigest(),'checked_in_sha256':hashlib.sha256(expected).hexdigest(),'ascii_escaped_indented_equal':(json.dumps(snapshot,indent=2,ensure_ascii=True)+'\n').encode()==expected})
record('public-snapshot-object-reproduction',snapshot==json.loads(expected))
print(json.dumps({'reviewed_commit':'8d0600725a25626012f17d6fa5324a8b904ddfe5','checks_passed':len(results),'results':results},indent=2,ensure_ascii=True))
