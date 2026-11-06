"""C002 v3 migration boundaries using isolated copies of frozen staged inputs."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ask import lookup
from library_view import InvalidLibrary, load_view

ROOT = Path(__file__).resolve().parents[1]


class C002V3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        shutil.copytree(ROOT / 'data', self.data)
        prior = self.read('C002-v3-integration-prior-inputs.json')['files']
        for name in ['library-inputs.json', 'query-catalog.json', 'curation-events.json']:
            (self.data / name).write_text(prior['data/' + name]['text'])
        self.old_view = load_view(self.root)
        self.old_catalog = self.read('query-catalog.json')
        for target, source in [('library-inputs.json', 'C002-v3-inputs-proposed.json'),
                               ('curation-events.json', 'C002-v3-curation-proposed.json')]:
            self.write(target, self.read(source))
        self.catalog = self.read('C002-v3-catalog-proposed.json')
        self.route = next(r for r in self.catalog['routes'] if r.get('claim_id') == 'C002')
        self.question = self.route['questions'][0]
        self.record = self.read('C002-v3.json')

    def read(self, name):
        return json.loads((self.data / name).read_text())

    def write(self, name, value):
        (self.data / name).write_text(json.dumps(value))

    def transition(self, state):
        events = self.read('curation-events.json')
        selected = events['curation_events'][-1]
        events['curation_events'].append({**selected,
            'seq': selected['seq'] + 1, 'state': state,
            'reason': 'Isolated simulated transition for migration boundary checks.'})
        self.write('curation-events.json', events)

    def ask(self, catalog=None):
        return lookup(self.question, load_view(self.root), catalog or self.catalog)

    def test_pending_selection_withholds_for_old_and_proposed_routes(self):
        for catalog in [self.old_catalog, self.catalog]:
            result = self.ask(catalog)
            self.assertEqual(result['status'], 'withheld')
            self.assertIsNone(result['answer'])
            self.assertNotIn('evidence_package', result)

    def test_approval_exposes_corrected_locator_roles_and_all_history(self):
        self.transition('approved')
        result = self.ask()
        self.assertEqual(result['status'], 'answer')
        package = result['evidence_package']
        self.assertEqual(package['selected_version'], 3)
        self.assertEqual(package['sources'], self.record['evidence'])
        self.assertTrue(package['sources'][0]['locator'].startswith('Notes, passage beginning'))
        self.assertEqual(package['author'], '@adrian.factomaton')
        self.assertEqual(package['reviews'][0]['reviewer'], '@adrian.factfinder')
        self.assertEqual(package['reviews'][0]['relationship'], 'internal_shared_owner')
        self.assertEqual([h['version'] for h in package['history']], [1, 2, 3])
        old = next(c for c in self.old_view['claims'] if c['claim_id'] == 'C002')
        self.assertEqual(package['history'][:2], old['history'])
        self.assertEqual(result['answer'], old['answer'])
        note = self.record['limitations'][-1]
        self.assertIn(note, package['historical_draft_metadata']['review_notes'])
        self.assertNotIn(note, package['limitations'])

    def test_old_route_hash_and_version_drift_withhold_after_approval(self):
        self.transition('approved')
        self.assertEqual(self.ask(self.old_catalog)['status'], 'withheld')
        for field, value in [('version', 2), ('record_sha256', '0' * 64)]:
            catalog = copy.deepcopy(self.catalog)
            next(r for r in catalog['routes'] if r.get('claim_id') == 'C002')[field] = value
            self.assertEqual(self.ask(catalog)['status'], 'withheld')

    def test_reopening_and_retirement_withhold(self):
        self.transition('approved')
        for state in ['reopened', 'retired']:
            self.transition(state)
            result = self.ask()
            self.assertEqual(result['status'], 'withheld')
            self.assertIsNone(result['answer'])

    def test_other_claim_outputs_and_question_set_preserved(self):
        self.transition('approved')
        view = load_view(self.root)
        self.assertEqual([c for c in view['claims'] if c['claim_id'] != 'C002'],
                         [c for c in self.old_view['claims'] if c['claim_id'] != 'C002'])
        self.assertEqual([r['questions'] for r in self.catalog['routes']],
                         [r['questions'] for r in self.old_catalog['routes']])
        for route in self.old_catalog['routes']:
            if route.get('claim_id') != 'C002':
                for question in route['questions']:
                    expected = lookup(question, self.old_view, self.old_catalog)
                    actual = lookup(question, view, self.catalog)
                    actual['routing_review_status'] = expected['routing_review_status']
                    self.assertEqual(actual, expected)

    def test_frozen_record_and_post_revision_mismatches_fail_closed(self):
        record = self.read('C002-v3.json')
        record['answer'] = 'altered'
        self.write('C002-v3.json', record)
        with self.assertRaisesRegex(InvalidLibrary, 'frozen record snapshot'):
            load_view(self.root)
        self.write('C002-v3.json', self.record)
        snapshot = self.read('C002-v3-post-snapshot.json')
        snapshot['posts'][0]['post_revision'] = 2
        self.write('C002-v3-post-snapshot.json', snapshot)
        with self.assertRaisesRegex(InvalidLibrary, 'conflicting source post revisions'):
            load_view(self.root)


if __name__ == '__main__':
    unittest.main()
