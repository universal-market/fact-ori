"""Read-only local compatibility evaluation; synthetic C007a states never publish."""
import copy
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from ask import lookup
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
from library_view import HISTORICAL_REVIEW_NOTES, derive_view, load_view
from validate_pilot import record_digest, validate

names = ['scripts/library_view.py', 'scripts/validate_pilot.py', 'scripts/ask.py',
         'scripts/export_api_seed.py', 'scripts/export_public_snapshot.py',
         'scripts/c007a_preview.py', 'data/library-inputs.json',
         'data/query-catalog.json', 'data/curation-events.json',
         'data/C007a-v3-routing-proposal-v1-2026-11-12.json',
         'scripts/fixtures/c007a-v3/record.json',
         'scripts/fixtures/c007a-v3/source-review.json']
manifest = json.loads((root / 'data/library-inputs.json').read_text())
for field in ('bundles', 'post_snapshots', 'record_snapshots'):
    names.extend('data/' + name for name in manifest[field])
names = sorted(set(names))
def hashes():
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
before = hashes()
read = lambda name: json.loads((root / name).read_text())
record = read('scripts/fixtures/c007a-v3/record.json')
review = read('scripts/fixtures/c007a-v3/source-review.json')
proposal = read('data/C007a-v3-routing-proposal-v1-2026-11-12.json')
assert hashlib.sha256((root / 'scripts/fixtures/c007a-v3/record.json').read_bytes()).hexdigest() == proposal['candidate_binding']['record_raw_sha256']
assert hashlib.sha256((root / 'scripts/fixtures/c007a-v3/source-review.json').read_bytes()).hexdigest() == proposal['source_review_binding']['raw_sha256']
bundle = {'schema_version': 1, 'records': [record], 'reviews': []}
# Synthetic pending event only, not a curation receipt. Never written to active data.
event = {'seq': 1, 'claim_id': 'C007a', 'version': 3,
         'record_sha256': record_digest(record), 'post_revision': 1,
         'state': 'pending', 'review_post_ids': [], 'actor': '@adrian.factomaton',
         'at': '2026-11-12T12:00:00+00:00',
         'reason': 'SYNTHETIC offline compatibility probe; no curation approval.'}
view = derive_view([bundle], [event], {record['tilori_post_id']: 1})
claim = view['claims'][0]
assert claim['answer'] is None and claim['current_review_state'] == 'awaiting_review'
assert record['limitations'][0] in claim['limitations']
assert record['limitations'][0] not in HISTORICAL_REVIEW_NOTES
raw_attached = copy.deepcopy(bundle)
raw_attached['reviews'] = [review]
errors = validate(raw_attached)
assert errors and 'reviews[0]: invalid reviewer decision' in errors

routes = [{'kind': 'claim', 'claim_id': 'C007a', 'version': 3,
           'record_sha256': record_digest(record), 'questions': [f['query']]}
          for f in proposal['fixtures'][:3]]
catalog = {'schema_version': 1, 'routing_review_status': 'reviewed', 'routes': routes}
pending = [lookup(f['query'], view, catalog) for f in proposal['fixtures'][:3]]
assert all(x['status'] == 'withheld' and x['answer'] is None for x in pending)
# Bypass curation ONLY in a deep-copied in-memory view to isolate lookup behavior.
# This does not pass derive_view's approval checks and is not an approved package.
synthetic = copy.deepcopy(view)
synthetic['claims'][0].update(state='approved', answer_kind='supported_assertion',
                               answer=record['answer'])
answers = [lookup(f['query'], synthetic, catalog) for f in proposal['fixtures'][:3]]
assert all(x['answer'] == record['answer'] for x in answers)
normalized = lookup(proposal['fixtures'][0]['query'].upper(), synthetic, catalog)
assert normalized['status'] == 'answer'
unsupported = copy.deepcopy(catalog)
unsupported['routes'][0]['kind'] = 'outside_scope'
try:
    lookup(proposal['fixtures'][0]['query'], view, unsupported)
except ValueError as error:
    unsupported_error = str(error)
else:
    raise AssertionError('unexpected outside_scope support')
assert unsupported_error == 'unknown route kind'

baseline_view = load_view(root)
seed = build_snapshot(root)
public = export_public(root)
assert all(row['claim_id'] != 'C007a' for row in baseline_view['claims'])
assert all(row['claimId'] != 'C007a' for row in seed['claims'])
assert all(row['claim_id'] != 'C007a' for row in public['records'])
assert hashes() == before
result = {
    'schema_version': 1, 'kind': 'local_consumer_compatibility_evaluation',
    'scope': 'Local existing Python consumer only; no live API/runtime/source factual check.',
    'input_raw_sha256': before,
    'observations': {
        'detached_review_direct_legacy_validation_errors': errors,
        'synthetic_pending_view': {
            'answer': claim['answer'], 'current_review_state': claim['current_review_state'],
            'creation_note_still_in_current_limitations': True,
            'creation_note_in_historical_review_notes': False},
        'synthetic_pending_Q01_Q02_Q03_status': [x['status'] for x in pending],
        'synthetic_lookup_bypass_Q01_Q02_Q03_return_whole_compound_answer': True,
        'synthetic_lookup_bypass_uppercase_query_status': normalized['status'],
        'outside_scope_route_kind_error': unsupported_error,
        'baseline': {'local_view_claims': len(baseline_view['claims']),
                     'local_seed_claims': len(seed['claims']),
                     'local_public_records': len(public['records']),
                     'local_seed_import_id': seed['importId'],
                     'local_public_snapshot_sha256': public['snapshot_sha256'],
                     'C007a_present': False},
        'all_named_input_bytes_unchanged': True},
    'limitations': [
        'Synthetic pending event and lookup-only approved-state bypass are in-memory probes, not curation or validated approval.',
        'Legacy failure is interface incompatibility, not invalid factual evidence or failed exact preview code review.',
        'Whole-answer behavior is intended by the existing claim route; predicate slicing and byte-exact matching require new explicit policy.',
        'Local seed/export checks do not identify the deployed runtime or certify remote currentness.',
        'Input hash equality covers named code/active data files, not all filesystem state or remote state.']}
print(json.dumps(result, indent=2, ensure_ascii=False))
