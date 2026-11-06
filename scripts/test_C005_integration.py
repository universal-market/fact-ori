"""C005 staged routing and publication boundaries on isolated library copies."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ask import lookup
from library_view import load_view

ROOT = Path(__file__).resolve().parents[1]


class C005IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'data', self.root / 'data')
        for name, value in self.read('C005-test-library-fixture.json')['files'].items():
            (self.root / 'data' / name).write_text(json.dumps(value))
        self.catalog = self.read('C005-query-catalog-proposed.json')
        self.route = next(r for r in self.catalog['routes'] if r.get('claim_id') == 'C005')
        self.record = self.read('C005-v1.json')
        events = self.read('curation-events.json')
        pending = next(e for e in events['curation_events'] if e['claim_id'] == 'C005' and e['state'] == 'pending')
        last_at = events['curation_events'][-1]['at']
        events['curation_events'] = [e for e in events['curation_events'] if e['claim_id'] != 'C005']
        events['curation_events'].append({**pending, 'seq': events['curation_events'][-1]['seq'] + 1, 'at': last_at})
        (self.root / 'data' / 'curation-events.json').write_text(json.dumps(events))

    def read(self, name):
        return json.loads((self.root / 'data' / name).read_text())

    def transition(self, state):
        events = self.read('curation-events.json')
        pending = next(e for e in events['curation_events'] if e['claim_id'] == 'C005')
        events['curation_events'].append({**pending, 'seq': events['curation_events'][-1]['seq'] + 1,
            'state': state, 'at': events['curation_events'][-1]['at'],
            'reason': 'Isolated simulated transition, no real curation decision.'})
        (self.root / 'data' / 'curation-events.json').write_text(json.dumps(events))

    def ask(self, question):
        return lookup(question, load_view(self.root), self.catalog)

    def test_pending_staged_aliases_withhold(self):
        for question in self.route['questions']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'withheld')
            self.assertIsNone(result['answer'])
            self.assertNotIn('evidence_package', result)

    def test_simulated_approval_retains_sources_roles_and_draft_history(self):
        self.transition('approved')
        for question in self.route['questions']:
            result = self.ask(question)
            self.assertEqual(result['status'], 'answer')
            self.assertEqual(result['answer'], self.record['answer'])
            package = result['evidence_package']
            self.assertEqual(package['author'], '@adrian.factfinder')
            self.assertEqual(package['reviews'][0]['reviewer'], '@adrian.factomaton')
            self.assertEqual(package['reviews'][0]['relationship'], 'internal_shared_owner')
            self.assertEqual(package['sources'], self.record['evidence'])
            note = 'Researcher evidence verdict only. Review and publication disposition remain pending; no curation approval is implied.'
            self.assertNotIn(note, package['limitations'])
            self.assertIn(note, package['historical_draft_metadata']['review_notes'])
            self.assertTrue(any('same BIPM' in s for s in package['limitations']))

    def test_reopening_and_pinned_input_drift_withhold(self):
        self.transition('approved')
        for field, value in [('version', 2), ('record_sha256', '0' * 64)]:
            changed = copy.deepcopy(self.catalog)
            route = next(r for r in changed['routes'] if r.get('claim_id') == 'C005')
            route[field] = value
            self.assertEqual(lookup(self.route['questions'][0], load_view(self.root), changed)['status'], 'withheld')
        self.transition('reopened')
        self.assertEqual(self.ask(self.route['questions'][0])['status'], 'withheld')

    def test_nearby_measurement_mass_and_temperature_questions_have_no_route(self):
        self.transition('approved')
        for question in ['Does my one-litre bottle contain exactly 1,000 millilitres?',
                         'Does one litre weigh exactly 1,000 grams?',
                         'Does one litre of water have the same volume at every temperature?',
                         'Does one litre equal exactly 100 millilitres?']:
            self.assertEqual(self.ask(question)['status'], 'not_in_library')

    def test_prior_routes_and_claims_preserved(self):
        prior = self.read('C005-integration-prior-inputs.json')['files']
        old_catalog = json.loads(prior['data/query-catalog.json']['text'])
        live = self.read('query-catalog.json')
        self.assertEqual([r for r in live['routes'] if r.get('claim_id') != 'C005'], old_catalog['routes'])
        self.assertEqual([r for r in self.catalog['routes'] if r.get('claim_id') != 'C005'], old_catalog['routes'])
        view = load_view(self.root)
        for name in ['library-inputs.json', 'curation-events.json']:
            (self.root / 'data' / name).write_text(prior['data/' + name]['text'])
        old_view = load_view(self.root)
        self.assertEqual([c for c in view['claims'] if c['claim_id'] != 'C005'], old_view['claims'])
        for route in old_catalog['routes']:
            for question in route['questions']:
                self.assertEqual(lookup(question, old_view, old_catalog), lookup(question, view, live))


if __name__ == '__main__':
    unittest.main()
