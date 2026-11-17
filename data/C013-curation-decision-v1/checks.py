"""Offline integrity checks for the exact C013 curation inputs; no factual proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
def read(path):
    return json.loads((ROOT / path).read_bytes())
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
manifest = read('data/C013-curation-decision-v1/input-bindings.json')
for row in manifest['bindings']:
    assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['raw_sha256'], row['path']
record = read('data/C013-library-candidate-v1/record.json')
assert digest(record) == '9f8ac32f0cb68e2ba05cdd04c8dc9af49943135c284952dcc1abdaf1836835ee'
bundle = read('data/C013-exact-review-attached-bundle-v1.json')
assert bundle['records'] == [record] and len(bundle['reviews']) == 1
r = bundle['reviews'][0]
assert r['review_decision'] == 'accept' and r['reviewed_post_revision'] == 1
assert r['input_record_sha256'] == digest(record)
source_review = read('data/C013-v1-factfinder-exact-review-v1.json')
assert r['receipt']['canonical_sha256'] == digest(source_review)
assert r['receipt']['raw_sha256'] == hashlib.sha256((ROOT / 'data/C013-v1-factfinder-exact-review-v1.json').read_bytes()).hexdigest()
view = read('data/C013-reviewed-pending-view-v2.json')['claims'][0]
assert view['limitations'] == record['limitations'][:2]
assert view['historical_draft_metadata']['review_notes'] == record['limitations'][2:]
assert view['current_review_state'] == 'accepted' and len(view['reviews']) == 1
assert view['source_dependence_groups'] == ['noaa-educational-account']
assert view['state'] == 'pending' and view['curation_event']['state'] == 'pending'
assert view['answer'] is None and view['answer_kind'] == 'withheld'
assert read('data/C013-pending-metadata-factfinder-review-v2.json')['decision'] == 'accept_exact_pending_metadata_revision_v2_only'
active_paths = ['data/library-inputs.json', 'data/curation-events.json', 'data/query-catalog.json', 'public/library.json']
for path in active_paths:
    assert 'C013' not in (ROOT / path).read_text(), path
print(json.dumps({'status': 'pass', 'raw_pins': len(manifest['bindings']), 'canonical_record_and_detached_source_receipt': 'pass', 'exact_v2_metadata_and_pending_withheld_state': 'pass', 'active_files_without_C013': active_paths, 'limits': 'Workspace consistency checks only. Git/GitHub publication bindings verified separately. No factual truth, current source freshness, general validator, deployed behavior or routing execution established.'}, indent=2))
