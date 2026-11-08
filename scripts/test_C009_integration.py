"""C009 package-limited abstention boundaries on isolated library copies."""
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


class C009IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'data', self.root / 'data')
        self.fixture = self.read('C009-test-library-fixture.json')
        for name, value in self.fixture['files'].items():
            self.write(name, value)
        self.record = self.read('C009-v2.json')
        self.catalog = self.read('query-catalog.json')
        self.route = next(r for r in self.catalog['routes'] if r.get('claim_id') == 'C009')

    def read(self, name):
        return json.loads((self.root / 'data' / name).read_text())

    def write(self, name, value):
        (self.root / 'data' / name).write_text(json.dumps(value))

    def transition(self, state):
        events = self.read('curation-events.json')
        previous = events['curation_events'][-1]
        events['curation_events'].append({**previous, 'seq': previous['seq'] + 1,
            'state': state, 'reason': 'SYNTHETIC TEST ONLY: exercise consumer state boundary.'})
        self.write('curation-events.json', events)

    def ask(self, question, catalog=None):
        return lookup(question, load_view(self.root), catalog or self.catalog)

    def test_frozen_bindings_and_exact_reviewed_routes(self):
        binding = self.fixture['review_binding']
        for name, expected in [('C009-v2-factomaton-review.json', binding['bundle_sha256']),
                               (binding['routing_artifact'], binding['routing_artifact_sha256'])]:
            self.assertEqual(hashlib.sha256((self.root / 'data' / name).read_bytes()).hexdigest(), expected)
        reviewed = self.read(binding['routing_artifact'])['routes_reviewed']['C009']['routes']
        self.assertEqual(self.catalog['routes'][-2:], reviewed)
        self.assertEqual(record_digest(self.record), self.route['record_sha256'])

    def test_pending_withholds_both_aliases_and_public_record(self):
        for question in self.route['questions']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'withheld')
            self.assertIsNone(result['answer'])
        public = export_public(self.root)
        self.assertNotIn('C009', [r['claim_id'] for r in public['records']])
        self.assertFalse(any(r.get('claim_id') == 'C009' for r in public['exact_mappings']))

    def test_approved_aliases_preserve_abstention_attribution_and_history(self):
        self.transition('approved')
        for question in self.route['questions']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'abstain')
            package = result['evidence_package']
            self.assertEqual(package['answer_kind'], 'reviewed_abstention')
            self.assertEqual(package['evidence_verdict'], 'insufficient_evidence')
            self.assertEqual(result['answer'], self.record['answer'])
            self.assertEqual(package['scope'], self.record['scope'])
            self.assertEqual(package['sources'], self.record['evidence'])
            self.assertEqual(package['claim_under_review'], self.record['claim'])
            self.assertEqual(package['author'], '@don.tinker')
            self.assertEqual(package['reviews'][0]['reviewer'], '@adrian.factomaton')
            self.assertEqual([h['review_decisions'] for h in package['history']], [['revise'], ['accept']])
        seed = build_snapshot(self.root)
        claim = next(c for c in seed['claims'] if c['claimId'] == 'C009')
        bundle = self.read('C009-v2-factomaton-review.json')
        self.assertEqual(claim['sourceReviews'], bundle['reviews'][1:])
        self.assertEqual(claim['sourceReviews'][0]['recorded_by'], '@adrian.factfinder')
        public = next(r for r in export_public(self.root)['records'] if r['claim_id'] == 'C009')
        self.assertEqual(public['record'], self.record)
        self.assertEqual(public['evidence_package']['answer_kind'], 'reviewed_abstention')

    def test_broad_space_questions_clarify_in_every_state(self):
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

    def test_drift_reopening_and_different_predicates_withhold(self):
        self.transition('approved')
        for field, value in [('version', 1), ('record_sha256', '0' * 64)]:
            catalog = copy.deepcopy(self.catalog)
            next(r for r in catalog['routes'] if r.get('claim_id') == 'C009')[field] = value
            for question in self.route['questions']:
                self.assertEqual(self.ask(question, catalog)['status'], 'withheld')
        for question in ['Has an astronaut reported seeing the Great Wall from low Earth orbit?',
                         'Is the Great Wall easy to see from low Earth orbit?',
                         'Has anyone seen the Great Wall from the Moon with the naked eye?',
                         'Was the Great Wall photographed from low Earth orbit?']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'not_in_library')
            self.assertIsNone(result['answer'])
        self.transition('reopened')
        for question in self.route['questions']:
            self.assertEqual(self.ask(question)['status'], 'withheld')
        self.assertNotIn('C009', [r['claim_id'] for r in export_public(self.root)['records']])

    def test_revised_v1_cannot_be_approved(self):
        events = self.read('curation-events.json')
        events['curation_events'][-1].update(version=1, state='approved',
            record_sha256=record_digest(self.read('C009-v1.json')),
            review_post_ids=['043a466e-db3b-4201-9621-3b3d172abc9d'])
        self.write('curation-events.json', events)
        with self.assertRaises(InvalidLibrary):
            load_view(self.root)

    def test_existing_six_claims_and_fourteen_responses_preserved(self):
        original = load_view(ROOT)
        original_catalog = json.loads((ROOT / 'data/query-catalog.json').read_text())
        self.transition('approved')
        staged = load_view(self.root)
        self.assertEqual([c for c in staged['claims'] if c['claim_id'] != 'C009'], original['claims'])
        for route in original_catalog['routes']:
            for question in route['questions']:
                self.assertEqual(self.ask(question), lookup(question, original, original_catalog))
