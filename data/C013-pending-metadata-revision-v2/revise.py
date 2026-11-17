"""Exact C013 A1 artifact revision only; not a general projection or classifier."""
import copy
import hashlib
import json
from pathlib import Path
import sys

VIEW_SHA256 = 'a05a21601e291bb982288c8fc5b8a41da9b09ec0aa101dae9fe0d046b15df733'
RECORD_SHA256 = '99d4409023fb0206a4df89fd0e37b2d8aa0fad7e64d18a1463862bd9da8aa06c'
NOTE = 'Prior source review binds the original three-post package. This new candidate has zero attached reviews.'


def revise(view_bytes, record_bytes):
    if hashlib.sha256(view_bytes).hexdigest() != VIEW_SHA256:
        raise ValueError('exact pending-view bytes required')
    if hashlib.sha256(record_bytes).hexdigest() != RECORD_SHA256:
        raise ValueError('exact frozen candidate bytes required')
    view = json.loads(view_bytes)
    record = json.loads(record_bytes)
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    claim = view['claims'][0]
    if not (len(view['claims']) == 1 and claim['claim_id'] == 'C013'
            and claim['selected_version'] == 1 and claim['state'] == 'pending'
            and claim['answer_kind'] == 'withheld' and claim['answer'] is None
            and claim['history'][0]['record_sha256'] == digest
            and claim['current_review_state'] == 'accepted' and len(claim['reviews']) == 1
            and claim['limitations'] == record['limitations']
            and claim['limitations'][2] == NOTE
            and claim['historical_draft_metadata']['review_notes'] == []):
        raise ValueError('exact C013 A1 state required')
    result = copy.deepcopy(view)
    target = result['claims'][0]
    target['limitations'] = claim['limitations'][:2]
    target['historical_draft_metadata']['review_notes'] = [NOTE]
    return result


def main():
    view = Path('data/C013-reviewed-pending-view-v1.json').read_bytes()
    record = Path('data/C013-library-candidate-v1/record.json').read_bytes()
    result = revise(view, record)
    if '--check' in sys.argv[1:]:
        original = json.loads(view)
        restored = copy.deepcopy(result)
        restored['claims'][0]['limitations'].append(restored['claims'][0]['historical_draft_metadata']['review_notes'].pop())
        assert restored == original
        assert result['claims'][0]['limitations'] == original['claims'][0]['limitations'][:2]
        rejected = []
        changes = [
            ('view_whitespace', view + b'\n', record),
            ('candidate_whitespace', view, record + b'\n'),
        ]
        for label, mutate in [
            ('substantive_limit', lambda x: x['claims'][0]['limitations'].__setitem__(0, 'changed')),
            ('note', lambda x: x['claims'][0]['limitations'].__setitem__(2, NOTE + ' changed')),
            ('reviewer', lambda x: x['claims'][0]['reviews'][0].__setitem__('reviewer', '@other.agent')),
            ('state', lambda x: x['claims'][0].__setitem__('state', 'approved')),
            ('digest', lambda x: x['claims'][0]['history'][0].__setitem__('record_sha256', '0' * 64)),
        ]:
            changed = copy.deepcopy(original)
            mutate(changed)
            changes.append((label, json.dumps(changed).encode(), record))
        for label, vb, rb in changes:
            try:
                revise(vb, rb)
            except ValueError:
                rejected.append(label)
            else:
                raise AssertionError(label)
        assert len(rejected) == 7
        print(json.dumps({'schema_version': 1, 'positive_exact_input': True,
                          'only_two_leaf_arrays_changed_reversible': True,
                          'both_substantive_limits_preserved': True,
                          'negative_cases_rejected': rejected,
                          'limits': 'Author finite exact-byte transformation checks only; no receipt authentication, new projection, factual review, routing or API acceptance.'}, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
