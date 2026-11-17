"""Authored offline checks; fixtures are prior reviewed examples, not held out."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('c013_route', HERE / 'route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)
inputs = {p: (ROOT / p).read_bytes() for p in route.PINS}
fixtures = json.loads(inputs['data/C013-routing-proposal-v2.json'])['fixtures']
eligible, withheld = 0, 0
for case in fixtures:
    result = route.preview(case['query'], inputs, unresolved_objections=[])
    assert result['answer'] is None and result['release_authorized'] is False
    assert result['proposed_response_after_remaining_gates'] == case['proposed_after_all_gates_response'], case['id']
    if case['proposed_after_all_gates_response'] is not None:
        assert result['classification'] == case['proposed_classification']
        eligible += 1
    else:
        assert result['classification'] == 'unmapped'
        withheld += 1
negative = 0
for path in route.PINS:
    changed = dict(inputs); changed[path] += b' '
    try:
        route.preview(fixtures[0]['query'], changed, unresolved_objections=[])
    except ValueError:
        negative += 1
    else:
        raise AssertionError('changed bytes accepted: ' + path)
for objections in [['unresolved correction'], None, False]:
    try:
        route.preview(fixtures[0]['query'], inputs, unresolved_objections=objections)
    except ValueError:
        negative += 1
    else:
        raise AssertionError('objection gate bypassed')
unknown = ['Can lightning strike the same place twice? And is it safe?',
           'It is not false that lightning never strikes twice.',
           'Can lightning strike the same place twice? ',
           "Can’t lightning strike the same place twice?", '', 'CAN LIGHTNING STRIKE THE SAME PLACE TWICE?']
for query in unknown:
    result = route.preview(query, inputs, unresolved_objections=[])
    assert result['classification'] == 'unmapped'
    assert result['proposed_response_after_remaining_gates'] is None
result = route.preview(fixtures[0]['query'], inputs, unresolved_objections=[])
result['limitations'].clear(); result['input_raw_sha256'].clear()
again = route.preview(fixtures[0]['query'], inputs, unresolved_objections=[])
assert len(again['limitations']) == 2 and again['input_raw_sha256'] == route.PINS
# Compare every disclosure value, not merely key presence or list length.
record = json.loads(inputs['data/C013-library-candidate-v1/record.json'])
assert len(record['exclusions']) == 7
old_path = ROOT / 'data/C013-routing-implementation-v1/route.py'
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == 'cac566973b730dfb76a56f64becd681886ccd7560bce30146730f7d126c107d0'
old_spec = importlib.util.spec_from_file_location('c013_original', old_path)
old = importlib.util.module_from_spec(old_spec)
old_spec.loader.exec_module(old)
new_source = (HERE / 'route.py').read_text()
assert new_source.replace("'scope': record['scope'],\n        'excluded_scopes': record['exclusions'],", "'excluded_scopes': record.get('excluded_scopes'),") == old_path.read_text()
assert route.PINS == old.PINS and route.ROUTES == old.ROUTES
cases = [c['query'] for c in fixtures] + unknown
for query in cases:
    current = route.preview(query, inputs, unresolved_objections=[])
    previous = old.preview(query, inputs, unresolved_objections=[])
    assert current['scope'] == record['scope']
    assert current['excluded_scopes'] == record['exclusions']
    assert previous.get('scope') is None and previous['excluded_scopes'] is None
    # Every other value is unchanged from the preserved implementation.
    current_without_fix = {k: v for k, v in current.items() if k not in ('scope', 'excluded_scopes')}
    previous_without_fix = {k: v for k, v in previous.items() if k != 'excluded_scopes'}
    assert current_without_fix == previous_without_fix
    # Mutating each newly disclosed field, then nested existing metadata, must
    # not affect subsequent calls or source input bytes.
    current['scope'] = 'mutated'
    current['excluded_scopes'][0] = 'mutated'
    current['excluded_scopes'].append('added')
    current['limitations'].clear()
    current['historical_draft_metadata'].clear()
    current['inference'].clear()
    again = route.preview(query, inputs, unresolved_objections=[])
    assert again['scope'] == record['scope']
    assert again['excluded_scopes'] == record['exclusions']
    assert again['limitations'] == record['limitations'][:2]
    assert again['inference'] == record['inference']
    assert again['historical_draft_metadata'] == json.loads(inputs['data/C013-reviewed-pending-view-v2.json'])['claims'][0]['historical_draft_metadata']
    assert json.loads(inputs['data/C013-library-candidate-v1/record.json']) == record

print(json.dumps({'status': 'pass', 'prior_design_cases': len(fixtures),
                  'eligible_exact_queries': eligible, 'noneligible_withheld': withheld,
                  'byte_and_objection_rejections': negative,
                  'unmapped_adversarial_queries': len(unknown), 'detached_return': True,
                  'full_scope_seven_exclusions_and_detachment_cases': len(cases),
                  'v1_I1_reproduced_and_only_disclosures_changed': True,
                  'limits': 'Authored exact-query offline checks only; no general language classification, factual proof, receipt authentication, live routing or release.'}, indent=2))
