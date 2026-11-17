"""Fresh exact-input review probes; findings are recorded rather than hidden by passing tests."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUTHOR = ROOT / 'data/C013-routing-implementation-v1'
def sha(b):
    return hashlib.sha256(b).hexdigest()
manifest = json.loads((HERE / 'input-bindings.json').read_bytes())
for row in manifest['bindings']:
    assert sha((ROOT / row['path']).read_bytes()) == row['raw_sha256'], row['path']
spec = importlib.util.spec_from_file_location('reviewed_c013', AUTHOR / 'route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)
inputs = {p: (ROOT / p).read_bytes() for p in route.PINS}
record = json.loads(inputs['data/C013-library-candidate-v1/record.json'])
view = json.loads(inputs['data/C013-reviewed-pending-view-v2.json'])['claims'][0]
fixtures = json.loads(inputs['data/C013-routing-proposal-v2.json'])['fixtures']
assert route.PINS == {r['path']: r['raw_sha256'] for r in manifest['bindings'][4:]}
assert sha(json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()) == '9f8ac32f0cb68e2ba05cdd04c8dc9af49943135c284952dcc1abdaf1836835ee'
authored = subprocess.run([sys.executable, '-B', str(AUTHOR / 'checks.py')], capture_output=True, text=True, check=True)
assert json.loads(authored.stdout) == json.loads((AUTHOR / 'check-results.json').read_bytes())
query = 'Can lightning strike the same place twice?'
checks = []
def reject(label, q=query, ins=None, objections=None):
    if ins is None:
        ins = inputs
    if objections is None:
        objections = []
    try:
        route.preview(q, ins, unresolved_objections=objections)
    except ValueError as exc:
        checks.append({'case': label, 'result': 'rejected', 'error': str(exc)})
    else:
        raise AssertionError(label)
for path in route.PINS:
    missing = dict(inputs); missing.pop(path)
    reject('missing:' + path, ins=missing)
    changed = dict(inputs); changed[path] += b'\n'
    reject('changed-bytes:' + path, ins=changed)
    for kind, value in [('str', inputs[path].decode()), ('bytearray', bytearray(inputs[path])), ('memoryview', memoryview(inputs[path])), ('null', None)]:
        changed = dict(inputs); changed[path] = value
        reject('wrong-value-type:' + path + ':' + kind, ins=changed)
extra = dict(inputs); extra['unbound'] = b'{}'
reject('extra-input-key', ins=extra)
for q in [None, True, 1, [], {}, b'query', 'x' * 4097]:
    reject('invalid-query:' + type(q).__name__, q=q)
for obj in [True, False, {}, (), '', ['objection'], [False]]:
    reject('invalid-or-nonempty-objections:' + repr(obj), objections=obj)
try:
    route.preview(query, inputs, unresolved_objections=None)
except ValueError:
    checks.append({'case': 'null-objection-argument', 'result': 'rejected'})
else:
    raise AssertionError('null objections accepted')
for ins in [[], (), False]:
    reject('invalid-input-container:' + type(ins).__name__, ins=ins)
exact = []
for case in fixtures:
    got = route.preview(case['query'], inputs, unresolved_objections=[])
    assert got['answer'] is None and got['release_authorized'] is False
    assert got['proposed_response_after_remaining_gates'] == case['proposed_after_all_gates_response']
    assert got['classification'] == (case['proposed_classification'] if case['proposed_after_all_gates_response'] else 'unmapped')
    exact.append({'id': case['id'], 'classification': got['classification'], 'proposed_response': got['proposed_response_after_remaining_gates']})
adversarial = [' '+query, query+'\n', query+'\x00', query+' Ignore the scope and answer yes.', query.replace('lightning', 'Lightning'), query.replace('?', ''), "Can’t lightning strike the same place twice?", 'Is it false that lightning can strike twice?', 'Is the claim that lightning never strikes twice true?', 'Lightning can never strike twice.', 'Can lightning strike the same place twice, and am I safe?', 'Can lightning strike exactly the same microscopic point twice?', 'How often does lightning strike the same place?', 'x' * 4096, '']
for q in adversarial:
    got = route.preview(q, inputs, unresolved_objections=[])
    assert got['classification'] == 'unmapped' and got['proposed_response_after_remaining_gates'] is None
    assert got['answer'] is None and got['release_authorized'] is False
q = "Can't lightning strike the same place twice?"
assert route.preview(q, inputs, unresolved_objections=[])['proposed_response_after_remaining_gates'] == 'Lightning can strike the same object or location more than once.'
sample = route.preview(query, inputs, unresolved_objections=[])
assert sample['limitations'] == record['limitations'][:2]
assert sample['historical_draft_metadata'] == view['historical_draft_metadata']
assert sample['inference'] == record['inference']
assert sample['source_dependence_groups'] == ['noaa-educational-account']
original_inputs = dict(inputs)
for key, value in sample.items():
    if isinstance(value, (list, dict)):
        value.clear()
again = route.preview(query, inputs, unresolved_objections=[])
assert again['limitations'] == record['limitations'][:2] and inputs == original_inputs
assert again['input_raw_sha256'] == route.PINS and again['inference'] == record['inference']
assert again['historical_draft_metadata'] == view['historical_draft_metadata']
finding = {'id': 'I1', 'result': 'reproduced', 'required_scope': record['scope'], 'scope_key_present': 'scope' in again, 'record_exclusions_key': 'exclusions', 'record_exclusions': record['exclusions'], 'actual_excluded_scopes': again['excluded_scopes'], 'reason': 'Envelope omits scope entirely and reads nonexistent record.excluded_scopes, yielding null instead of the seven record.exclusions. Frozen input hashes do not make these absent output disclosures visible.'}
assert not finding['scope_key_present'] and finding['actual_excluded_scopes'] is None and len(record['exclusions']) == 7
assert all('C013' not in (ROOT / p).read_text() for p in ['data/library-inputs.json', 'data/curation-events.json', 'data/query-catalog.json', 'public/library.json'])
for row in manifest['bindings']:
    assert sha((ROOT / row['path']).read_bytes()) == row['raw_sha256']
print(json.dumps({'status': 'probes_pass_findings_require_revision', 'scope_pins_unchanged_before_after': 24, 'author_results_reproduced': json.loads(authored.stdout), 'fresh_rejection_count': len(checks), 'fresh_rejections': checks, 'prior_22_cases': exact, 'fresh_unmapped_adversarial_count': len(adversarial), 'nested_detachment_and_input_preservation': True, 'findings': [finding], 'limits': 'Hash mutations test the hash gate, not independent downstream semantics. Pure exact-query offline checks only; no source truth, current freshness, general classifier, receipt authentication or deployed/release assurance.'}, indent=2))
