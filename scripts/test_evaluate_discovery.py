"""Relevance scoring must preserve negatives and fail corrupted output."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from discover import discover
from evaluate_discovery import evaluate, score_case
from library_view import InvalidLibrary, load_view

ROOT = Path(__file__).resolve().parents[1]


class DiscoveryEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        shutil.copytree(ROOT / 'data', root / 'data')
        fixture = json.loads((root / 'data/C005-test-library-fixture.json').read_text())
        for name, value in fixture['files'].items():
            (root / 'data' / name).write_text(json.dumps(value))
        self.view = load_view(root)
        self.catalog = fixture['files']['query-catalog.json']
        self.dataset = json.loads((ROOT / 'data/discovery-evaluation-v1.json').read_text())

    def case(self, case_id):
        return next(c for c in self.dataset['cases'] if c['id'] == case_id)

    def result(self, case_id):
        case = self.case(case_id)
        response = discover(case['question'], self.view, self.catalog)
        return score_case(case, response, copy.deepcopy(response))

    def test_wrong_country_is_irrelevant_even_with_scope_disclosure(self):
        row = self.result('Q20')
        self.assertTrue(row['output_checks_pass'])
        self.assertFalse(row['exact_relevance_set_match'])
        self.assertIn({'claim_id': 'C004', 'version': 1}, row['irrelevant_targets'])
        self.assertEqual(row['relevant_retrieved'], 0)

    def test_wrong_year_empty_is_successful_negative(self):
        row = self.result('Q21')
        self.assertTrue(row['exact_relevance_set_match'])
        self.assertEqual(row['retrieved'], 0)

    def test_useful_candidate_is_never_an_answer(self):
        row = self.result('Q09')
        self.assertEqual(row['relevant_retrieved'], 1)
        self.assertTrue(row['top_candidate_relevant'])
        self.assertIsNone(row['response']['answer'])

    def test_corrupted_or_malformed_output_fails_even_negative_cases(self):
        case = self.case('Q21')
        reference = discover(case['question'], self.view, self.catalog)
        wrong = copy.deepcopy(reference)
        wrong['answer'] = 'invented'
        malformed = copy.deepcopy(reference)
        malformed['candidates'] = [None]
        for response in (None, [], wrong, malformed, {}, dict(reference, status=[])):
            with self.subTest(response=response):
                row = score_case(case, response, reference)
                self.assertFalse(row['output_checks_pass'])
                self.assertFalse(row['exact_relevance_set_match'])

    def test_modified_scope_does_not_pass_fidelity(self):
        case = self.case('Q09')
        reference = discover(case['question'], self.view, self.catalog)
        response = copy.deepcopy(reference)
        response['candidates'][0]['scope'] = 'all countries'
        self.assertFalse(score_case(case, response, reference)['output_checks_pass'])

    def test_invalid_output_suppresses_all_headline_scores(self):
        # A stub cannot count as valid discovery for a positive; no divide by zero.
        data = dict(self.dataset, cases=[self.case('Q09')])
        report = evaluate(data, self.view, self.catalog, search=lambda *args: {})
        self.assertIsNone(report['micro_precision'])
        self.assertIsNone(report['micro_recall'])
        self.assertIsNone(report['retrieved'])
        self.assertIsNone(report['relevant_retrieved'])
        self.assertIsNone(report['exact_relevance_set_matches'])
        self.assertEqual(report['run_status'], 'invalid')
        self.assertEqual(report['valid_case_counts']['case_count'], 0)
        self.assertEqual(report['valid_case_counts']['excluded_case_count'], 1)
        self.assertEqual(report['output_check_failures'], 1)

    def test_one_corrupt_negative_cannot_improve_headline_precision(self):
        question = self.case('Q20')['question']
        baseline = evaluate(self.dataset, self.view, self.catalog)
        self.assertEqual(baseline['run_status'], 'valid')
        for replacement in ('leaked text', None):
            def corrupt(q, *args):
                response = discover(q, *args)
                if q == question:
                    if replacement is None:
                        return None
                    response['answer'] = replacement
                return response
            with self.subTest(replacement=replacement):
                report = evaluate(self.dataset, self.view, self.catalog, search=corrupt)
                self.assertEqual(report['run_status'], 'invalid')
                self.assertEqual(report['invalid_output_case_ids'], ['Q20'])
                self.assertIsNone(report['micro_precision'])
                self.assertIsNone(report['micro_recall'])
                self.assertIsNone(report['retrieved'])
                self.assertEqual(report['valid_case_counts']['case_count'], 31)
                self.assertEqual(report['valid_case_counts']['excluded_case_count'], 1)
                self.assertEqual(report['valid_case_counts']['retrieved'], 38)
                row = next(r for r in report['cases'] if r['id'] == 'Q20')
                self.assertFalse(row['output_checks_pass'])
                if replacement is None:
                    self.assertIsNone(row['response'])
                else:
                    self.assertEqual(row['response']['answer'], replacement)

    def test_valid_empty_negative_remains_a_valid_run(self):
        data = dict(self.dataset, cases=[self.case('Q21')])
        report = evaluate(data, self.view, self.catalog)
        self.assertEqual(report['run_status'], 'valid')
        self.assertEqual(report['invalid_output_case_ids'], [])
        self.assertEqual(report['retrieved'], 0)
        self.assertIsNone(report['micro_precision'])
        self.assertIsNone(report['micro_recall'])
        self.assertEqual(report['exact_relevance_set_matches'], 1)

    def test_duplicate_or_stale_labels_fail(self):
        for target in ([{'claim_id': 'C004', 'version': 9}],
                       [{'claim_id': 'C004', 'version': 1}] * 2):
            data = copy.deepcopy(self.dataset)
            data['cases'][0]['relevant_targets'] = target
            with self.assertRaises(InvalidLibrary):
                evaluate(data, self.view, self.catalog)

    def test_replay_is_nonmutating_and_summary_retains_bad_cases(self):
        before = copy.deepcopy((self.view, self.catalog, self.dataset))
        report = evaluate(self.dataset, self.view, self.catalog)
        self.assertEqual((self.view, self.catalog, self.dataset), before)
        self.assertEqual(report['total'], 32)
        self.assertIn('Q20', report['irrelevant_retrieval_case_ids'])
        self.assertEqual(report['output_check_failures'], 0)
        self.assertFalse(report['held_out'])


if __name__ == '__main__':
    unittest.main()
