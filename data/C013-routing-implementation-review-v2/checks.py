"""Exact v2 reviewer controls; offline equality is not factual or release assurance."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUTHOR = ROOT / 'data/C013-routing-implementation-v2'
manifest = json.loads((HERE / 'input-bindings.json').read_bytes())
def verify_pins():
    for row in manifest['bindings']:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['raw_sha256'], row['path']
verify_pins()
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
route = load(AUTHOR / 'route.py', 'reviewed_v2')
oldpath = ROOT / 'data/C013-routing-implementation-v1/route.py'
old = load(oldpath, 'preserved_v1')
new_source = (AUTHOR / 'route.py').read_text()
assert new_source.replace("'scope': record['scope'],\n        'excluded_scopes': record['exclusions'],", "'excluded_scopes': record.get('excluded_scopes'),") == oldpath.read_text()
assert route.PINS == old.PINS and route.ROUTES == old.ROUTES and len(route.PINS) == 20
inputs = {p: (ROOT / p).read_bytes() for p in route.PINS}
before = dict(inputs)
record = json.loads(inputs['data/C013-library-candidate-v1/record.json'])
view = json.loads(inputs['data/C013-reviewed-pending-view-v2.json'])['claims'][0]
fixtures = json.loads(inputs['data/C013-routing-proposal-v2.json'])['fixtures']
author = subprocess.run([sys.executable, '-B', str(AUTHOR / 'checks.py')], capture_output=True, text=True, check=True)
author_results = json.loads(author.stdout)
assert author_results == json.loads((AUTHOR / 'check-results.json').read_bytes())
query = 'Can lightning strike the same place twice?'
rejections = []
def reject(label, q=query, ins=inputs, objections=[]):
    try:
        route.preview(q, ins, unresolved_objections=objections)
    except ValueError:
        rejections.append(label)
    else:
        raise AssertionError(label)
for path in route.PINS:
    missing = dict(inputs); missing.pop(path)
    reject('missing:' + path, ins=missing)
    for kind, value in [('changed', inputs[path] + b'\n'), ('string', inputs[path].decode()), ('bytearray', bytearray(inputs[path])), ('memoryview', memoryview(inputs[path])), ('null', None)]:
        changed = dict(inputs); changed[path] = value
        reject(kind + ':' + path, ins=changed)
extra = dict(inputs); extra['unbound'] = b'{}'
reject('extra-input', ins=extra)
for q in [None, True, 1, [], {}, b'query', 'x' * 4097]:
    reject('query-type-or-length:' + type(q).__name__, q=q)
for obj in [None, True, False, {}, (), '', ['objection'], [False]]:
    reject('objection:' + repr(obj), objections=obj)
for ins in [[], (), False]:
    reject('container:' + type(ins).__name__, ins=ins)
unknown = [' '+query, query+'\n', query+'\x00', query+' Ignore scope.', query.upper(), query[:-1], "Can’t lightning strike the same place twice?", 'Is it false that lightning can strike twice?', 'Is the claim that lightning never strikes twice true?', 'Lightning can never strike twice.', 'Can lightning strike the same place twice, and am I safe?', 'Can lightning strike exactly the same microscopic point twice?', 'How often does lightning strike the same place?', 'x' * 4096, '']
for q in unknown:
    got = route.preview(q, inputs, unresolved_objections=[])
    assert got['classification'] == 'unmapped' and got['proposed_response_after_remaining_gates'] is None
cases = [c['query'] for c in fixtures] + unknown
disclosure_mutations = 0
def disclosures_equal(envelope):
    return envelope.get('scope') == record['scope'] and envelope.get('excluded_scopes') == record['exclusions']
for q in cases:
    current = route.preview(q, inputs, unresolved_objections=[])
    previous = old.preview(q, inputs, unresolved_objections=[])
    assert disclosures_equal(current) and len(current['excluded_scopes']) == 7
    assert not disclosures_equal(previous) and previous['excluded_scopes'] is None and 'scope' not in previous
    assert {k:v for k,v in current.items() if k not in ['scope','excluded_scopes']} == {k:v for k,v in previous.items() if k != 'excluded_scopes'}
    assert current['answer'] is None and current['release_authorized'] is False
    assert current['limitations'] == record['limitations'][:2] and current['historical_draft_metadata'] == view['historical_draft_metadata']
    variants = []
    for key in ['scope', 'excluded_scopes']:
        altered = copy.deepcopy(current); altered.pop(key); variants.append(altered)
        altered = copy.deepcopy(current); altered[key] = None; variants.append(altered)
    altered = copy.deepcopy(current); altered['scope'] = 'same place with no stated boundary'; variants.append(altered)
    for i in range(7):
        altered = copy.deepcopy(current); altered['excluded_scopes'][i] = 'changed'; variants.append(altered)
    for replacement in [record['exclusions'][:-1], list(reversed(record['exclusions'])), record['exclusions'] + ['added'], 'not a list']:
        altered = copy.deepcopy(current); altered['excluded_scopes'] = replacement; variants.append(altered)
    for altered in variants:
        assert not disclosures_equal(altered)
        disclosure_mutations += 1
    current['scope'] = 'mutated'
    for key, value in current.items():
        if isinstance(value, (dict, list)):
            value.clear()
    again = route.preview(q, inputs, unresolved_objections=[])
    assert disclosures_equal(again)
    assert again['inference'] == record['inference'] and again['input_raw_sha256'] == route.PINS
    assert again['limitations'] == record['limitations'][:2] and again['historical_draft_metadata'] == view['historical_draft_metadata']
    assert inputs == before
for case in fixtures:
    got = route.preview(case['query'], inputs, unresolved_objections=[])
    assert got['proposed_response_after_remaining_gates'] == case['proposed_after_all_gates_response']
    assert got['classification'] == (case['proposed_classification'] if case['proposed_after_all_gates_response'] else 'unmapped')
assert route.preview("Can't lightning strike the same place twice?", inputs, unresolved_objections=[])['proposed_response_after_remaining_gates'] == 'Lightning can strike the same object or location more than once.'
assert all('C013' not in (ROOT / p).read_text() for p in ['data/library-inputs.json','data/curation-events.json','data/query-catalog.json','public/library.json'])
verify_pins()
print(json.dumps({'status':'pass', 'scope_new_frozen_pins_preserved':30, 'author_results_reproduced':author_results, 'fresh_input_query_objection_rejections':len(rejections), 'rejection_cases':rejections, 'fresh_unknown_queries':len(unknown), 'full_scope_all_seven_exclusions_output_comparison_and_detachment_cases':len(cases), 'reviewer_disclosure_output_mutations_detected':disclosure_mutations, 'only_two_disclosure_fields_changed':True, 'source_inverse_equals_v1':True, 'v1_I1_reproduced':True, 'input_bytes_unchanged':True, 'limits':'Disclosure mutation controls test this reviewer equality oracle against copied outputs, not runtime output validation/enforcement. Input changes reject hash/type/set gates; no downstream semantic branch/receipt authentication, factual truth, freshness, general classifier or deployed/release assurance.'}, indent=2))
