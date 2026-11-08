"""C010 consumer boundaries on isolated copies; no publication decision."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ask import lookup
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
from library_view import InvalidLibrary, load_view
from validate_pilot import record_digest

ROOT = Path(__file__).resolve().parents[1]


class C010IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'data', self.root / 'data')
        self.fixture = json.loads((self.root / 'data/C010-test-library-fixture.json').read_text())
        for name, value in self.fixture['files'].items():
            self.write(name, value)
        self.record = self.read('C010-v2.json')
        self.catalog = self.read('query-catalog.json')
        self.route = next(r for r in self.catalog['routes'] if r.get('claim_id') == 'C010')

    def read(self, name):
        return json.loads((self.root / 'data' / name).read_text())

    def write(self, name, value):
        (self.root / 'data' / name).write_text(json.dumps(value))

    def transition(self, state):
        events = self.read('curation-events.json')
        event = copy.deepcopy(events['curation_events'][-1])
        event.update(seq=event['seq'] + 1, state=state,
                     at=f"2026-11-08T04:00:{event['seq'] - 12:02d}Z",
                     reason='SYNTHETIC TEST ONLY: exercise consumer state boundary.')
        events['curation_events'].append(event)
        self.write('curation-events.json', events)

    def ask(self, question, catalog=None):
        return lookup(question, load_view(self.root), catalog or self.catalog)

    def test_frozen_inputs_and_exact_reviewed_routes(self):
        binding = self.fixture['review_binding']
        bundle_path = self.root / 'data/C010-v2-factomaton-review.json'
        self.assertEqual(hashlib.sha256(bundle_path.read_bytes()).hexdigest(), binding['bundle_sha256'])
        routing_path = self.root / 'data' / binding['routing_artifact']
        self.assertEqual(hashlib.sha256(routing_path.read_bytes()).hexdigest(), binding['routing_artifact_sha256'])
        reviewed = json.loads(routing_path.read_text())['routes_reviewed']['C010']['routes']
        self.assertEqual(self.catalog['routes'][-2:], reviewed)
        self.assertEqual(record_digest(self.record), self.route['record_sha256'])

    def test_pending_withholds_and_does_not_export_draft(self):
        self.assertEqual(self.ask(self.route['questions'][0])['status'], 'withheld')
        public = export_public(self.root)
        self.assertNotIn('C010', [r['claim_id'] for r in public['records']])
        self.assertFalse(any(r.get('claim_id') == 'C010' for r in public['exact_mappings']))

    def test_approved_preserves_scope_sources_history_and_decision_actor(self):
        self.transition('approved')
        result = self.ask(self.route['questions'][0])
        self.assertEqual(result['status'], 'answer')
        package = result['evidence_package']
        self.assertEqual(package['answer'], self.record['answer'])
        self.assertEqual(package['scope'], self.record['scope'])
        self.assertEqual(package['sources'], self.record['evidence'])
        self.assertEqual(package['author'], '@don.tinker')
        self.assertEqual(package['reviews'][0]['reviewer'], '@adrian.factomaton')
        self.assertEqual([h['review_decisions'] for h in package['history']], [['revise'], ['accept']])
        seed = build_snapshot(self.root)
        claim = next(c for c in seed['claims'] if c['claimId'] == 'C010')
        bundle = self.read('C010-v2-factomaton-review.json')
        self.assertEqual(claim['sourceReviews'], bundle['reviews'][1:])
        public = next(r for r in export_public(self.root)['records'] if r['claim_id'] == 'C010')
        self.assertEqual(public['record'], self.record)

    def test_missing_medium_always_clarifies(self):
        route = self.catalog['routes'][-1]
        for state in ['pending', 'approved', 'reopened']:
            if state != 'pending':
                self.transition(state)
            for question in route['questions']:
                with self.subTest(state=state, question=question):
                    result = self.ask(question)
                    self.assertEqual(result['status'], 'needs_clarification')
                    self.assertIsNone(result['answer'])
                    self.assertEqual(result['reason'], route['clarification'])

    def test_drift_reopening_and_excluded_predicates(self):
        self.transition('approved')
        for field, value in [('version', 1), ('record_sha256', '0' * 64)]:
            catalog = copy.deepcopy(self.catalog)
            next(r for r in catalog['routes'] if r.get('claim_id') == 'C010')[field] = value
            self.assertEqual(self.ask(self.route['questions'][0], catalog)['status'], 'withheld')
        for question in ['Is the speed of light in water exactly 299,792,458 metres per second?',
                         'Is the measured speed of light exact?',
                         'Is light in glass always slower than light in vacuum?']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'not_in_library')
            self.assertIsNone(result['answer'])
        self.transition('reopened')
        self.assertEqual(self.ask(self.route['questions'][0])['status'], 'withheld')
        self.assertNotIn('C010', [r['claim_id'] for r in export_public(self.root)['records']])

    def test_revised_v1_cannot_be_approved(self):
        events = self.read('curation-events.json')
        event = events['curation_events'][-1]
        event.update(version=1, state='approved', record_sha256=record_digest(self.read('C010-v1.json')),
                     review_post_ids=['bd288539-7cb7-44d0-9e4d-42f4990fc95e'])
        self.write('curation-events.json', events)
        with self.assertRaises(InvalidLibrary):
            load_view(self.root)

    def test_existing_projections_and_answers_unchanged(self):
        original = load_view(ROOT)
        self.transition('approved')
        staged = load_view(self.root)
        self.assertEqual([c for c in staged['claims'] if c['claim_id'] != 'C010'], original['claims'])
        catalog = json.loads((ROOT / 'data/query-catalog.json').read_text())
        for route in catalog['routes']:
            for question in route['questions']:
                self.assertEqual(self.ask(question), lookup(question, original, catalog))
