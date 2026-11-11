#!/usr/bin/env python3
"""Compare imported exact reply-disposition declarations without approval.

FO-W020-S9: direct-parent correspondence only; no live capture/coverage resolver.
Schema and comparison policy derive from Factfinder design76bf310c, separately
accepted at a50004d. Factomaton implementation requires a fresh exact-source review.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

from review_receipt_store import strict_json, read_input
from sidecar_digest import canonical_bytes, CONVENTION

SCHEMA_PATH = Path(__file__).with_name('reply_disposition.schema.json')
SCHEMA_SHA256 = '88ab80da04d5f247a135f829748986a116f326a878d1fc86a233770c3913bbe1'
GATES = ('authenticated_provenance_and_reviewer_authority',
         'separate_recipient_decision', 'required_review_coverage_and_adequacy',
         'current_full_content_and_correction_disposition',
         'trusted_observation_freshness_and_visibility',
         'runtime_build_and_deployment_binding')
OBS_FIELDS = {'bindings', 'implementation_author', 'reviewer', 'parent', 'replies',
              'corrections', 'known_actors', 'frontier_complete',
              'full_content_available', 'correction_chain_complete',
              'caller_age_bound_satisfied', 'collector_diagnostics'}


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_observations(o, schema):
    require(type(o) is dict and set(o) == OBS_FIELDS, 'observation fields')
    props = schema['properties']
    for field in ('bindings', 'implementation_author', 'reviewer', 'parent', 'collector_diagnostics'):
        _conforms(o[field], props[field])
    snapshot = props['parent']
    for field in ('replies', 'corrections'):
        _conforms(o[field], {'type':'array', 'maxItems':256, 'items':snapshot})
    _conforms(o['known_actors'], {'type':'array', 'minItems':1, 'maxItems':1024,
                               'items':props['implementation_author']})
    # One imported actor cannot be associated with conflicting owners.
    actors = o['known_actors']
    require(len({a['agent_id'] for a in actors}) == len(actors), 'ambiguous actor/owner')
    for field in ('frontier_complete', 'full_content_available',
                  'correction_chain_complete', 'caller_age_bound_satisfied'):
        require(type(o[field]) is bool, 'observation flag type')


def require(value,message):
    if not value:raise ValueError(message)
def _conforms(v,s):
    if 'anyOf' in s:
        for option in s['anyOf']:
            try:_conforms(v,option);return
            except ValueError:pass
        raise ValueError('anyOf')
    if 'type' in s:
        types=s['type'] if isinstance(s['type'],list) else [s['type']]
        actual='null' if v is None else 'boolean' if type(v) is bool else 'integer' if type(v) is int else 'string' if type(v) is str else 'array' if type(v) is list else 'object' if type(v) is dict else 'other'
        require(actual in types,'type')
    if 'const' in s:require(canonical_bytes(v)==canonical_bytes(s['const']),'const')
    if 'enum' in s:require(any(canonical_bytes(v)==canonical_bytes(x) for x in s['enum']),'enum')
    if type(v) is dict:
        for key in s.get('required',[]):require(key in v,'missing field '+key)
        if s.get('additionalProperties') is False:require(set(v)<=set(s['properties']),'unknown field')
        for key,value in v.items():
            if key in s.get('properties',{}):_conforms(value,s['properties'][key])
    if type(v) is list:
        require(len(v)>=s.get('minItems',0) and len(v)<=s.get('maxItems',10**9),'array bounds')
        for item in v:
            if 'items' in s:_conforms(item,s['items'])
    if type(v) is str:
        require(len(v)>=s.get('minLength',0) and len(v)<=s.get('maxLength',10**9),'string bounds')
        if 'pattern' in s:require(re.fullmatch(s['pattern'],v) is not None,'pattern')
    if type(v) is int:require(v>=s.get('minimum',v) and v<=s.get('maximum',v),'integer bounds')

def _evaluate(d,o,schema):
    result={'outcome':'invalidated','authentication':'unverified_import','recipient_decision':'not_evaluated','implementation_review':'pending','runtime_review':'pending','overall_status':'pending','collector_diagnostics':copy.deepcopy(o.get('collector_diagnostics',[])),'unmet_gates':list(GATES),'same_owner':None,'decision_actor_is_reply_author':[],'recorder_is_decision_actor':[],'author_withdrawal_established':False}
    try:
        _conforms(d,schema)
        validate_observations(o,schema)
        for field in ['frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied']:require(o.get(field) is True,field)
        require(canonical_bytes(d['bindings'])==canonical_bytes(o['bindings']),'input binding mismatch')
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


def reply_disposition_report(disposition_raw, observations_raw):
    # All inputs, including observation flags, are untrusted imported declarations.
    d = strict_json(disposition_raw)
    o = strict_json(observations_raw)
    schema_raw = read_input(SCHEMA_PATH)
    if hashlib.sha256(schema_raw).hexdigest() != SCHEMA_SHA256:
        raise ValueError('Pinned disposition schema bytes differ')
    schema = strict_json(schema_raw)
    # Malformed observation packets cannot supply diagnostics or coverage premises.
    validate_observations(o, schema)
    result = _evaluate(d, o, schema)
    result.update({'schema_version':1, 'kind':'offline_reply_disposition_report',
                   'profile':'imported-direct-parent-correspondence-v1',
                   'inputs':{'disposition_raw_sha256':hashlib.sha256(disposition_raw).hexdigest(),
                             'disposition_canonical_sha256':digest(d),
                             'observations_raw_sha256':hashlib.sha256(observations_raw).hexdigest(),
                             'observations_canonical_sha256':digest(o),
                             'schema_raw_sha256':SCHEMA_SHA256,
                             'canonicalization':CONVENTION},
                   'coverage_evidence':'unchecked_imported_assertions',
                   'limits':['Exact supplied declarations only; coherent forged packets can correspond.',
                             'Observation booleans are premises, not verified completeness/freshness/content evidence.',
                             'No semantic classification or rationale adequacy, actor authority or host authentication.',
                             'Direct-parent envelope; no multi-parent correction resolver or immutable decision-history resolver.',
                             'No collector diagnostic clearing, existing report integration, runtime/factual/curation/routing/API approval.']})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposition', type=Path, required=True)
    parser.add_argument('--observations', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = reply_disposition_report(read_input(args.disposition), read_input(args.observations))
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f'Reply disposition report failed: {error}\n')
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
