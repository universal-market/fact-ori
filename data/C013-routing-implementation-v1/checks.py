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
print(json.dumps({'status': 'pass', 'prior_design_cases': len(fixtures),
                  'eligible_exact_queries': eligible, 'noneligible_withheld': withheld,
                  'byte_and_objection_rejections': negative,
                  'unmapped_adversarial_queries': len(unknown), 'detached_return': True,
                  'limits': 'Authored exact-query offline checks only; no general language classification, factual proof, receipt authentication, live routing or release.'}, indent=2))
