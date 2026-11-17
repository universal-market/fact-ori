"""Independent exact-artifact probes of C013 A1; no general consumer implementation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import types

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
base=Path('data/C013-pending-metadata-revision-v2')
source=(base/'revise.py').read_bytes()
assert sha(source)=='ec2c7c59c653c840e980ee717932221d66a710466a4c7b54aec5e790c9fc1ca7'
mod=types.ModuleType('exact_a1');exec(compile(source,'exact-pinned-revise.py','exec'),mod.__dict__)
vb=Path('data/C013-reviewed-pending-view-v1.json').read_bytes();rb=Path('data/C013-library-candidate-v1/record.json').read_bytes()
original=json.loads(vb);record=json.loads(rb);expected=read('data/C013-reviewed-pending-view-v2.json')
actual=mod.revise(vb,rb)
assert actual==expected
def diffs(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b):
        return [z for k in sorted(a) for z in diffs(a[k],b[k],path+'/'+k)]
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        return [z for i,(x,y) in enumerate(zip(a,b)) for z in diffs(x,y,path+'/'+str(i))]
    return [] if a==b else [path]
delta=diffs(original,actual)
assert set(delta)=={'/claims/0/limitations','/claims/0/historical_draft_metadata/review_notes'}
c=actual['claims'][0];old=original['claims'][0]
assert c['limitations']==old['limitations'][:2]
assert c['historical_draft_metadata']['review_notes']==[old['limitations'][2]]
assert c['current_review_state']=='accepted' and len(c['reviews'])==1
assert c['state']=='pending' and c['answer_kind']=='withheld' and c['answer'] is None
assert c['source_dependence_groups']==['noaa-educational-account']
restored=copy.deepcopy(actual);restored['claims'][0]['limitations'].append(restored['claims'][0]['historical_draft_metadata']['review_notes'].pop());assert restored==original
# Detached result mutation must not affect subsequent results or immutable inputs.
actual['claims'][0]['sources'][0]['publisher']='reviewer-only synthetic mutation'
assert mod.revise(vb,rb)==expected and json.loads(vb)==original and json.loads(rb)==record

negative=[]
def reject(label,v,r):
    try:mod.revise(v,r)
    except ValueError as e:
        negative.append(dict(case=label,rejected=True,message=str(e)))
    else:raise AssertionError('accepted changed input '+label)
for label,v,r in [('view_LF',vb+b'\n',rb),('record_LF',vb,rb+b'\n'),('view_BOM',b'\xef\xbb\xbf'+vb,rb),('empty_view',b'',rb),('malformed_record',vb,b'{'),('swapped_inputs',rb,vb),('already_revised',Path('data/C013-reviewed-pending-view-v2.json').read_bytes(),rb)]:reject(label,v,r)
mutations={
 'substantive_limit':lambda x:x['claims'][0]['limitations'].__setitem__(0,'changed'),
 'second_limit':lambda x:x['claims'][0]['limitations'].__setitem__(1,'changed'),
 'note_wording':lambda x:x['claims'][0]['limitations'].__setitem__(2,'different'),
 'note_reorder':lambda x:x['claims'][0]['limitations'].reverse(),
 'note_duplicate':lambda x:x['claims'][0]['limitations'].append(x['claims'][0]['limitations'][2]),
 'missing_metadata':lambda x:x['claims'][0].pop('historical_draft_metadata'),
 'historical_notes_nonempty':lambda x:x['claims'][0]['historical_draft_metadata'].update(review_notes=['existing']),
 'claim_id':lambda x:x['claims'][0].update(claim_id='C999'),
 'version':lambda x:x['claims'][0].update(selected_version=2),
 'state':lambda x:x['claims'][0].update(state='approved'),
 'answer':lambda x:x['claims'][0].update(answer='published'),
 'answer_kind':lambda x:x['claims'][0].update(answer_kind='supported_assertion'),
 'digest':lambda x:x['claims'][0]['history'][0].update(record_sha256='0'*64),
 'revision':lambda x:x['claims'][0]['reviews'][0].update(reviewed_post_revision=2),
 'reviewer':lambda x:x['claims'][0]['reviews'][0].update(reviewer='@other.agent'),
 'receipt_missing':lambda x:x['claims'][0].update(reviews=[]),
 'review_not_accepted':lambda x:x['claims'][0].update(current_review_state='revise'),
 'source_group':lambda x:x['claims'][0].update(source_dependence_groups=[]),
 'source_text':lambda x:x['claims'][0]['sources'][0].update(observation='changed'),
 'curation_event':lambda x:x['claims'][0]['curation_event'].update(state='approved'),
 'second_claim':lambda x:x['claims'].append(copy.deepcopy(x['claims'][0])),
}
for name,change in mutations.items():
    v=copy.deepcopy(original);change(v);reject(name,json.dumps(v).encode(),rb)
for field,value in [('claim','changed'),('verdict','contradicted'),('version',2),('scope','changed'),('tilori_post_revision',2)]:
    r=copy.deepcopy(record);r[field]=value;reject('candidate_'+field,vb,json.dumps(r).encode())
assert len(negative)==33
# Replay author CLI selfchecks separately; these are not fresh semantic controls.
cmd=['python','-B',str(base/'revise.py')]
out=subprocess.run(cmd,capture_output=True,check=True,timeout=10)
assert out.stdout==Path('data/C013-reviewed-pending-view-v2.json').read_bytes() and not out.stderr
checks=subprocess.run([*cmd,'--check'],capture_output=True,check=True,timeout=10)
assert json.loads(checks.stdout)==read(str(base/'check-results.json')) and not checks.stderr
print(json.dumps(dict(schema_version=1,positive=dict(exact_published_view_reproduced=True,changed_array_paths=delta,verbatim_note_moved=True,both_substantive_limits_preserved=True,all_other_values_preserved=True,reverse_reconstruction_JSON_equal=True,detached_output_and_unchanged_inputs=True,pending_withheld_and_single_noaa_group=True),fresh_negative_count=len(negative),fresh_negative_cases=negative,author_replay=dict(checks_command='python -B data/C013-pending-metadata-revision-v2/revise.py --check',seven_author_cases_JSON_equal=True,view_command='python -B data/C013-pending-metadata-revision-v2/revise.py',published_view_stdout_bytes_equal=True),limits=['All altered inputs reject at exact SHA256 boundary; this does not independently exercise every downstream semantic guard or prove general review/receipt authentication.','Only exact pinned offline artifact revision accepted for assessment; no live consumer or general historical-note classifier.']),indent=2))
