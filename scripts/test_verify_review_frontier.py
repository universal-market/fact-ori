import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_review_frontier import verify_frontier

ROOT = Path(__file__).resolve().parents[1]


class SemanticFrontierTests(unittest.TestCase):
    def setUp(self):
        self.receipt = b'{"schema_version":1}\n'
        self.recorder = '11111111-1111-4111-8111-111111111111'
        self.reviewer = '22222222-2222-4222-8222-222222222222'
        self.owner = '33333333-3333-4333-8333-333333333333'
        self.pid = '44444444-4444-4444-8444-444444444444'
        self.time = '2026-11-11T04:00:00.000Z'
        self.post = {'id': self.pid, 'kind': 'post', 'revision': 1, 'title': 'Decision',
                     'body': 'accept', 'status': None, 'reply_count': 0, 'edited_by': None,
                     'author': {'id': self.reviewer, 'user_id': self.owner}}
        profile = {'profile': {'id': self.recorder, 'user_id': self.owner, 'kind': 'agent'}}
        reviewer = {'id': self.reviewer, 'user_id': self.owner, 'kind': 'agent'}
        pinned = {'post_id': self.pid, 'revision': 1, 'title': 'Decision', 'body': 'accept', 'edited_by': None}
        def obs(tool, args, result):
            return {'tool': tool, 'arguments': args, 'result_json': json.dumps({'result': result}), 'observed_at': self.time}
        self.value = {'schema_version': 1, 'started_at': self.time, 'finished_at': self.time,
                      'capture': {'schema_version': 1, 'capture_id': '55555555-5555-4555-8555-555555555555',
                                  'recorded_at': self.time, 'recorder_agent_id': self.recorder,
                                  'reviewer_agent_id': self.reviewer, 'reviewer_owner_id': self.owner,
                                  'decision_post_id': self.pid, 'decision_revision': 1, 'reviewed_commit': 'a'*40,
                                  'receipt_raw_sha256': hashlib.sha256(self.receipt).hexdigest(),
                                  'observations': [obs('get_my_profile', {}, profile), obs('get_agent', {'agent_id': self.reviewer}, reviewer),
                                                   obs('get_post', {'post_id': self.pid}, self.post),
                                                   obs('get_post_revision', {'post_id': self.pid, 'revision': 1}, pinned)]},
                      'observations': [obs('search_posts', {'root_post_id': self.pid, 'max_depth': None, 'sort': 'created_at', 'limit': 20}, {'items': [], 'next_cursor': None}),
                                       obs('get_post', {'post_id': self.pid}, self.post)],
                      'reply_refs': [], 'pages_read': 1, 'next_cursor': None, 'frontier_complete': True,
                      'diagnostics': [], 'observation_state': 'empty_frontier_observed',
                      'receipt_authentication': 'unverified_import', 'implementation_review': 'pending'}

    def verify(self, value=None):
        return verify_frontier(json.dumps(self.value if value is None else value).encode(), self.receipt)

    def payload(self, value, group, index, change):
        observations = value['capture']['observations'] if group == 'base' else value['observations']
        raw = json.loads(observations[index]['result_json']); change(raw['result'])
        observations[index]['result_json'] = json.dumps(raw)

    def test_matching_responses_still_have_no_authority(self):
        r = self.verify()
        self.assertEqual(r['response_relationships'], 'matching_imported_observations')
        self.assertEqual(r['authentication'], 'unverified_import')
        self.assertEqual(r['implementation_review'], 'pending')
        self.assertEqual(r['source_binding'], 'unchecked')
        self.assertEqual(r['runtime_review'], 'pending')

    def test_forged_labels_with_empty_responses_cannot_match(self):
        v = copy.deepcopy(self.value)
        for o in v['capture']['observations'] + v['observations']: o['result_json'] = '{}'
        self.assertEqual(self.verify(v)['response_relationships'], 'pending')

    def test_identity_owner_and_kind_mismatches(self):
        cases = [('base', 0, lambda x: x['profile'].update(id=self.reviewer)),
                 ('base', 0, lambda x: x['profile'].update(user_id=[self.owner])),
                 ('base', 1, lambda x: x.update(kind='human')),
                 ('base', 1, lambda x: x.update(user_id=self.recorder)),
                 ('base', 2, lambda x: x['author'].update(user_id=self.recorder))]
        for group, index, change in cases:
            v = copy.deepcopy(self.value); self.payload(v, group, index, change)
            self.assertEqual(self.verify(v)['response_relationships'], 'pending')

    def test_pinned_and_final_drift_and_boolean_revisions(self):
        cases = [('base', 3, lambda x: x.update(revision=True)),
                 ('base', 3, lambda x: x.update(body='withdrawn')),
                 ('base', 3, lambda x: x.update(edited_by={})),
                 ('extra', 1, lambda x: x.update(revision=2)),
                 ('extra', 1, lambda x: x.update(body='correction')),
                 ('extra', 1, lambda x: x.update(status='done')),
                 ('extra', 1, lambda x: x.update(reply_count=True)),
                 ('extra', 1, lambda x: x.update(edited_by={'id': self.recorder}))]
        for group, index, change in cases:
            v = copy.deepcopy(self.value); self.payload(v, group, index, change)
            self.assertEqual(self.verify(v)['response_relationships'], 'pending')

    def two_pages(self):
        v = copy.deepcopy(self.value)
        second = copy.deepcopy(v['observations'][0]); second['arguments']['cursor'] = 'A'
        self.payload(v, 'extra', 0, lambda x: x.update(next_cursor='A'))
        v['observations'].insert(1, second); v['pages_read'] = 2
        return v

    def test_empty_partial_pages_continue_using_response_cursor(self):
        v = self.two_pages()
        self.assertEqual(self.verify(v)['response_relationships'], 'matching_imported_observations')
        v['observations'][1]['arguments']['cursor'] = 'wrong'
        self.assertIn('continuation_cursor_mismatch', self.verify(v)['diagnostics'])

    def test_hidden_more_pages_and_cycles_override_claimed_completion(self):
        v = copy.deepcopy(self.value); self.payload(v, 'extra', 0, lambda x: x.update(next_cursor='A'))
        self.assertEqual(self.verify(v)['response_relationships'], 'pending')
        v = self.two_pages(); self.payload(v, 'extra', 1, lambda x: x.update(next_cursor='A'))
        self.assertIn('repeated_response_cursor', self.verify(v)['diagnostics'])
        v = self.two_pages(); self.payload(v, 'extra', 0, lambda x: x.update(next_cursor=None))
        self.assertIn('search_after_completion', self.verify(v)['diagnostics'])

    def test_partial_flag_without_cursor_and_malformed_items_fail_closed(self):
        for change in [lambda x: x.update(partial=True), lambda x: x.update(partial=1),
                       lambda x: x.update(items={}), lambda x: x.update(next_cursor=[]),
                       lambda x: x.update(items=[{'post': {'id': self.pid}}])]:
            v = copy.deepcopy(self.value); self.payload(v, 'extra', 0, change)
            self.assertEqual(self.verify(v)['response_relationships'], 'pending')

    def test_errors_and_noninteger_response_revisions_cannot_match(self):
        for raw in ['{"error":"DENIED"}', '{"result":{"error":null}}', '{"result":[]}',
                    self.value['capture']['observations'][3]['result_json'].replace('"revision": 1', '"revision": 1.0')]:
            v = copy.deepcopy(self.value); v['capture']['observations'][3]['result_json'] = raw
            self.assertEqual(self.verify(v)['response_relationships'], 'pending')

    def test_reply_refs_reconstructed_and_all_replies_require_full_review(self):
        ref = {'post_id': '66666666-6666-4666-8666-666666666666', 'revision': 1,
               'author_agent_id': self.recorder, 'author_owner_id': self.owner}
        v = copy.deepcopy(self.value)
        self.payload(v, 'extra', 0, lambda x: x.update(items=[{'post': {'id': ref['post_id'], 'kind': 'post', 'revision': 1, 'author': {'id': self.recorder, 'user_id': self.owner}}}]))
        for group, index in [('base', 2), ('extra', 1)]: self.payload(v, group, index, lambda x: x.update(reply_count=1))
        self.assertIn('claimed_reply_refs_mismatch', self.verify(v)['diagnostics'])
        v.update(reply_refs=[ref], diagnostics=['replies_require_full_review'], observation_state='pending')
        r = self.verify(v)
        self.assertEqual(r['derived_reply_refs'], [ref])
        self.assertIn('replies_require_full_content_disposition', r['diagnostics'])
        self.assertEqual(r['response_relationships'], 'pending')

    def test_collector_pending_diagnostics_never_cleared(self):
        v = copy.deepcopy(self.value); v.update(diagnostics=['unexpected_error'], observation_state='pending')
        self.assertIn('collector_reported_pending', self.verify(v)['diagnostics'])

    def test_cli_is_read_only_and_returns_bound_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); f = folder/'frontier.json'; r = folder/'receipt.json'
            f.write_text(json.dumps(self.value)); r.write_bytes(self.receipt)
            before = f.read_bytes()
            result = subprocess.check_output([sys.executable, '-B', str(ROOT/'scripts/verify_review_frontier.py'), '--frontier', str(f), '--receipt', str(r)])
            self.assertEqual(json.loads(result)['response_relationships'], 'matching_imported_observations')
            self.assertEqual(f.read_bytes(), before)
            self.assertEqual(set(x.name for x in folder.iterdir()), {'frontier.json', 'receipt.json'})

    def test_actual_s4_output_matches_only_as_unverified(self):
        base = self.value['capture']
        request = {key: base[key] for key in ('capture_id', 'recorder_agent_id', 'reviewer_agent_id',
                                             'decision_post_id', 'decision_revision', 'reviewed_commit', 'receipt_raw_sha256')}
        values = {obs['tool']: json.loads(obs['result_json'])['result']
                  for obs in base['observations'] + self.value['observations']}
        source = '''
import {acquireReviewFrontier} from './scripts/acquire_review_frontier.mjs';
const [request,values]=JSON.parse(process.argv[1]);
const result=await acquireReviewFrontier(async tool=>({result_json:JSON.stringify({result:values[tool],ratio:0.5})}),{max_pages:1,capture_request:request});
console.log(JSON.stringify(result));
'''
        raw = subprocess.check_output(['node', '--input-type=module', '-e', source,
                                       json.dumps([request, values])], cwd=ROOT)
        result = verify_frontier(raw, self.receipt)
        self.assertEqual(result['response_relationships'], 'matching_imported_observations')
        self.assertEqual(result['authentication'], 'unverified_import')
        self.assertEqual(result['implementation_review'], 'pending')
