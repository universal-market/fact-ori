import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from review_frontier_store import frontier_metadata, store_frontier
from review_receipt_store import MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]


class FrontierStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'frontier.sqlite'
        self.receipt = b'{"schema_version":1,"decision":"accept"}\n'
        self.time = '2026-11-11T01:00:00.000Z'
        self.post = '44444444-4444-4444-8444-444444444444'
        self.reviewer = '33333333-3333-4333-8333-333333333333'
        def obs(tool, args):
            return {'tool': tool, 'arguments': args, 'result_json': '{"ratio":0.5}', 'observed_at': self.time}
        self.value = {'schema_version': 1, 'started_at': self.time, 'finished_at': self.time,
                      'capture': {'schema_version': 1, 'capture_id': '11111111-1111-4111-8111-111111111111',
                                  'recorded_at': self.time, 'recorder_agent_id': '22222222-2222-4222-8222-222222222222',
                                  'reviewer_agent_id': self.reviewer, 'reviewer_owner_id': None,
                                  'decision_post_id': self.post, 'decision_revision': 1,
                                  'reviewed_commit': 'a' * 40, 'receipt_raw_sha256': hashlib.sha256(self.receipt).hexdigest(),
                                  'observations': [obs('get_my_profile', {}), obs('get_agent', {'agent_id': self.reviewer}),
                                                   obs('get_post', {'post_id': self.post}),
                                                   obs('get_post_revision', {'post_id': self.post, 'revision': 1})]},
                      'observations': [obs('search_posts', {'root_post_id': self.post, 'max_depth': None, 'sort': 'created_at', 'limit': 20}),
                                       obs('get_post', {'post_id': self.post})],
                      'reply_refs': [], 'pages_read': 1, 'next_cursor': None, 'frontier_complete': True,
                      'diagnostics': [], 'observation_state': 'empty_frontier_observed',
                      'receipt_authentication': 'unverified_import', 'implementation_review': 'pending'}

    def raw(self, value=None):
        return json.dumps(self.value if value is None else value).encode()

    def test_storage_preserves_original_bytes_and_fixed_pending_labels(self):
        first = store_frontier(self.database, self.raw(), self.receipt)
        self.assertEqual(first, store_frontier(self.database, self.raw(), self.receipt))
        with sqlite3.connect(self.database) as db:
            rows = db.execute('SELECT frontier_raw, receipt_raw FROM review_frontiers').fetchall()
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        self.assertEqual(rows, [(self.raw(), self.receipt)])
        self.assertEqual(tables, [('review_frontiers',)])
        self.assertEqual(first['authentication'], 'unverified_import')
        self.assertEqual(first['frontier_verification'], 'pending')
        self.assertEqual(first['implementation_review'], 'pending')
        self.assertEqual(first['owner_relationship'], 'unknown')

    def test_raw_reformat_conflict_preserves_original(self):
        store_frontier(self.database, self.raw(), self.receipt)
        with self.assertRaises(ValueError):
            store_frontier(self.database, json.dumps(self.value, indent=2).encode(), self.receipt)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT frontier_raw FROM review_frontiers').fetchall(), [(self.raw(),)])

    def test_concurrent_identical_imports_make_one_row(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: store_frontier(self.database, self.raw(), self.receipt), range(4)))
        self.assertTrue(all(x == results[0] for x in results))
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM review_frontiers').fetchone()[0], 1)

    def test_invalid_fields_counts_labels_and_completion_reject_before_db(self):
        variants = [('schema_version', True), ('pages_read', True), ('pages_read', 11),
                    ('pages_read', 0), ('frontier_complete', 1), ('next_cursor', []),
                    ('next_cursor', 'x'), ('receipt_authentication', 'authenticated'),
                    ('implementation_review', 'accepted'), ('diagnostics', ['x']),
                    ('observation_state', 'accepted'), ('extra', 1)]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                v = copy.deepcopy(self.value); v[key] = value
                with self.assertRaises((ValueError, TypeError)):
                    store_frontier(self.database, self.raw(v), self.receipt)
                self.assertFalse(self.database.exists())

    def test_strict_outer_and_nested_duplicate_json_and_bounds(self):
        for raw in [self.raw().replace(b'"pages_read": 1', b'"pages_read": 1, "pages_read": 1'),
                    self.raw().replace(b'"pages_read": 1', b'"pages_read": 1.0'), b' ' * (MAX_BYTES + 1)]:
            with self.assertRaises(ValueError): frontier_metadata(raw, self.receipt)
        for result in ['{"x":1,"x":2}', '[1]', '{', '{"x":NaN}']:
            v = copy.deepcopy(self.value); v['observations'][0]['result_json'] = result
            with self.assertRaises(ValueError): frontier_metadata(self.raw(v), self.receipt)

    def test_times_are_strict_utc_ordered_and_bounded(self):
        for invalid in ['2026-02-30T01:00:00Z', '2026-11-11 01:00:00Z', '2026-11-11T01:00:00+00:00',
                        '2026-11-11T01:00:00.1234Z', None]:
            v = copy.deepcopy(self.value); v['finished_at'] = invalid
            with self.assertRaises((ValueError, TypeError)): frontier_metadata(self.raw(v), self.receipt)
        v = copy.deepcopy(self.value); v['observations'][0]['observed_at'] = '2026-11-11T01:00:01.000Z'
        with self.assertRaises(ValueError): frontier_metadata(self.raw(v), self.receipt)

    def test_binding_and_fixed_read_scope(self):
        v = copy.deepcopy(self.value); v['capture']['receipt_raw_sha256'] = 'b' * 64
        with self.assertRaises(ValueError): frontier_metadata(self.raw(v), self.receipt)
        for mutate in [lambda x: x['observations'][0]['arguments'].update(max_depth=1),
                       lambda x: x['observations'][1].update(tool='create_post'),
                       lambda x: x['capture']['observations'][0].update(tool='get_post'),
                       lambda x: x['capture']['observations'][3]['arguments'].update(revision=True),
                       lambda x: x['observations'][0]['arguments'].update(cursor='unexpected')]:
            v = copy.deepcopy(self.value); mutate(v)
            with self.assertRaises(ValueError): frontier_metadata(self.raw(v), self.receipt)

    def test_partial_and_access_failure_retained_pending(self):
        v = copy.deepcopy(self.value); v.update(frontier_complete=False, next_cursor='continue',
                                               diagnostics=['frontier_page_budget_exhausted'], observation_state='pending')
        self.assertEqual(frontier_metadata(self.raw(v), self.receipt)['frontier_verification'], 'pending')
        v['observations'] = v['observations'][:1]; v['observations'][0]['result_json'] = '{"error":"DENIED"}'
        self.assertEqual(frontier_metadata(self.raw(v), self.receipt)['authentication'], 'unverified_import')

    def test_reply_references_cannot_be_duplicate_root_or_boolean_revision(self):
        ref = {'post_id': '55555555-5555-4555-8555-555555555555', 'revision': 1,
               'author_agent_id': self.reviewer, 'author_owner_id': self.reviewer}
        for refs in [[ref, ref], [{**ref, 'post_id': self.post}], [{**ref, 'revision': True}]]:
            v = copy.deepcopy(self.value); v.update(reply_refs=refs, diagnostics=['replies_require_full_review'], observation_state='pending')
            with self.assertRaises(ValueError): frontier_metadata(self.raw(v), self.receipt)

    def test_cli_entrypoint_returns_metadata(self):
        root = Path(self.temp.name); (root / 'frontier.json').write_bytes(self.raw()); (root / 'receipt.json').write_bytes(self.receipt)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/review_frontier_store.py'),
                                 '--database', str(self.database), '--frontier', str(root / 'frontier.json'),
                                 '--receipt', str(root / 'receipt.json')], capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['frontier_verification'], 'pending')

    def test_actual_s4_synthetic_output_imports_without_promotion(self):
        source = '''
import {acquireReviewFrontier} from './scripts/acquire_review_frontier.mjs';
import {createHash} from 'node:crypto';
const ids=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','44444444-4444-4444-8444-444444444444'];
const receipt='{"schema_version":1,"decision":"accept"}\\n';
const post={id:ids[3],kind:'post',revision:1,status:null,title:'Decision',body:'accept',edited_by:null,reply_count:0,author:{id:ids[1],user_id:ids[2]}};
const values={get_my_profile:{profile:{id:ids[0],user_id:ids[2],kind:'agent'}},get_agent:{id:ids[1],user_id:ids[2],kind:'agent'},get_post:post,get_post_revision:{post_id:ids[3],revision:1,title:'Decision',body:'accept',edited_by:null},search_posts:{items:[],next_cursor:null}};
const result=await acquireReviewFrontier(async tool=>({result_json:JSON.stringify({result:values[tool]})}),{max_pages:1,capture_request:{capture_id:'55555555-5555-4555-8555-555555555555',recorder_agent_id:ids[0],reviewer_agent_id:ids[1],decision_post_id:ids[3],decision_revision:1,reviewed_commit:'a'.repeat(40),receipt_raw_sha256:createHash('sha256').update(receipt).digest('hex')}});
console.log(JSON.stringify(result));
'''
        raw = subprocess.check_output(['node', '--input-type=module', '-e', source], cwd=ROOT)
        metadata = store_frontier(self.database, raw, self.receipt)
        self.assertEqual(metadata['frontier']['observation_state'], 'empty_frontier_observed')
        self.assertEqual(metadata['frontier_verification'], 'pending')
        self.assertEqual(metadata['authentication'], 'unverified_import')
