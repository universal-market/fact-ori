"""Detached design oracle, not a collector, runtime validator or authority gate.

Implements only the JSON Schema keywords used in the companion design schema.
Inputs are synthetic declarations, not authenticated observations or semantic proof.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def conforms(v,s):
    if 'anyOf' in s:
        for option in s['anyOf']:
            try:conforms(v,option);return
            except ValueError:pass
        raise ValueError('anyOf')
    if 'type' in s:
        types=s['type'] if isinstance(s['type'],list) else [s['type']]
        actual='null' if v is None else 'boolean' if type(v) is bool else 'integer' if type(v) is int else 'string' if type(v) is str else 'array' if type(v) is list else 'object' if type(v) is dict else 'other'
        require(actual in types,'type')
    if 'const' in s:require(v==s['const'],'const')
    if 'enum' in s:require(v in s['enum'],'enum')
    if type(v) is dict:
        for key in s.get('required',[]):require(key in v,'missing field '+key)
        if s.get('additionalProperties') is False:require(set(v)<=set(s['properties']),'unknown field')
        for key,value in v.items():
            if key in s.get('properties',{}):conforms(value,s['properties'][key])
    if type(v) is list:
        require(len(v)>=s.get('minItems',0) and len(v)<=s.get('maxItems',10**9),'array bounds')
        for item in v:
            if 'items' in s:conforms(item,s['items'])
    if type(v) is str:
        require(len(v)>=s.get('minLength',0) and len(v)<=s.get('maxLength',10**9),'string bounds')
        if 'pattern' in s:require(re.fullmatch(s['pattern'],v) is not None,'pattern')
    if type(v) is int:require(v>=s.get('minimum',v) and v<=s.get('maximum',v),'integer bounds')

def evaluate(d,o,schema):
    result={'outcome':'invalidated','authentication':'unverified_import','recipient_decision':'not_evaluated','implementation_review':'pending','runtime_review':'pending','overall_status':'pending','collector_diagnostics':copy.deepcopy(o.get('collector_diagnostics',[])),'unmet_gates':read('example.synthetic.json')['coverage']['unchecked'],'same_owner':None,'decision_actor_is_reply_author':[],'recorder_is_decision_actor':[],'author_withdrawal_established':False}
    try:
        conforms(d,schema)
        for field in ['frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied']:require(o.get(field) is True,field)
        require(d['bindings']==o['bindings'],'input binding mismatch')
        require(d['parent']==o['parent'],'parent snapshot mismatch')
        require(d['implementation_author']==o['implementation_author'] and d['reviewer']==o['reviewer'],'role identity drift')
        entries=d['entries'];replies=o['replies']
        require(len({x['reply']['post_id'] for x in entries})==len(entries),'duplicate entries')
        require(len({x['post_id'] for x in replies})==len(replies),'duplicate observed replies')
        key=lambda x:x['post_id']
        require(sorted([x['reply'] for x in entries],key=key)==sorted(replies,key=key),'changed/new/uncovered reply')
        require(d['coverage']['reply_set_sha256']==digest(sorted(replies,key=key)),'reply set hash')
        corrections=o['corrections'];require(len({x['post_id'] for x in corrections})==len(corrections),'duplicate corrections')
        declared_corrections=[x for entry in entries for x in entry['correction_chain']]
        require(len({x['post_id'] for x in declared_corrections})==len(declared_corrections),'duplicate declared corrections')
        require(sorted(declared_corrections,key=key)==sorted(corrections,key=key),'correction chain omission/drift')
        require(d['coverage']['correction_set_sha256']==digest(sorted(corrections,key=key)),'correction set hash')
        require(d['collector_diagnostics']==o['collector_diagnostics'],'collector diagnostics changed')
        actors=o['known_actors']
        for actor in [d['implementation_author'],d['reviewer'],d['parent']['author']]+[x['author'] for x in replies+corrections]+[x for entry in entries for x in [entry['decision_actor'],entry['recorder']]]:
            require(actor in actors,'actor/owner unresolved')
        for snapshot in [d['parent']]+replies+corrections:
            if snapshot['edited_by'] is not None:require(snapshot['edited_by'] in actors,'editor/owner unresolved')
        targets=[{k:x[k] for k in ['post_id','revision','body_sha256']} for x in [d['parent']]+replies+corrections]
        classes=[]
        for entry in entries:
            require(entry['reply']['parent_post_id']==d['parent']['post_id'],'reply parent mismatch')
            require(entry['rationale'].strip(),'blank rationale')
            classification=entry['classification'];classes.append(classification)
            affected=entry['affected_targets']
            require(len({digest(x) for x in affected})==len(affected),'duplicate affected targets')
            if classification in ['material_objection','correction','withdrawal']:require(affected,'missing affected target')
            if classification=='nonblocking_context':require(not affected,'nonblocking hides affected targets')
            require(all(x in targets for x in affected),'unbound affected target')
        require(not corrections or any(x!='nonblocking_context' for x in classes),'correction chain cannot be silently dismissed')
        result['outcome']='reopen_required' if any(x in ['material_objection','correction','withdrawal'] for x in classes) else 'hold_unresolved' if 'unresolved' in classes else 'corresponding_nonblocking_declaration'
        result['same_owner']=len({x['owner_id'] for x in [d['implementation_author'],d['reviewer']]+[e['decision_actor'] for e in entries]+[e['recorder'] for e in entries]})==1
        result['decision_actor_is_reply_author']=[e['decision_actor']==e['reply']['author'] for e in entries]
        result['recorder_is_decision_actor']=[e['recorder']==e['decision_actor'] for e in entries]
        # Even an internally matching author/target is an unverified declaration.
        # No factual/review withdrawal or collector/runtime state is applied.
    except (ValueError,KeyError,TypeError):pass
    return result

def run():
    schema=read('disposition.schema.json');base=read('example.synthetic.json');observed=read('observations.synthetic.json');fixtures=read('fixtures.json');rows=[]
    for case in fixtures['cases']:
        d=copy.deepcopy(base);o=copy.deepcopy(observed)
        for operation in case['operations']:
            node=d if operation['side']=='disposition' else o
            for key in operation['path'][:-1]:node=node[key]
            key=operation['path'][-1]
            if operation.get('delete'):del node[key]
            else:node[key]=copy.deepcopy(operation['value'])
        before=digest({'d':d,'o':o});result=evaluate(d,o,schema)
        assert result['outcome']==case['expected'],(case['id'],result)
        assert result['authentication']=='unverified_import' and result['recipient_decision']=='not_evaluated'
        assert all(result[k]=='pending' for k in ['implementation_review','runtime_review','overall_status'])
        assert result['collector_diagnostics']==o['collector_diagnostics'] and result['unmet_gates']==base['coverage']['unchecked']
        assert not result['author_withdrawal_established'] and before==digest({'d':d,'o':o})
        rows.append({'id':case['id'],'expected':case['expected'],'actual':result['outcome'],'pass':True})
    first=evaluate(base,observed,schema)
    assert first['same_owner'] is True and first['decision_actor_is_reply_author']==[True] and first['recorder_is_decision_actor']==[False]
    print(json.dumps({'schema_version':1,'kind':'synthetic_design_fixture_results','cases':len(rows),'per_case_guarantees':['expected outcome','fixed pending gates and unverified authentication','collector diagnostics retained','no automatic author withdrawal','unchanged fixture inputs'],'schema_validation':'detached subset interpreter for companion schema keywords only; not independent standards conformance','rows':rows,'live_disposition_issued':False,'collector_diagnostics_cleared':False,'authority_or_runtime_promoted':False},indent=2))

if __name__=='__main__':run()
