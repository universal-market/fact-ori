import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from review_input_report import review_input_report
import test_release_manifest as git_fixtures
import test_verify_review_frontier as frontier_fixtures


class ReviewInputReportTests(unittest.TestCase):
    setUpGit = git_fixtures.ReleaseManifestTests.setUp
    git = git_fixtures.ReleaseManifestTests.git
    write = git_fixtures.ReleaseManifestTests.write
    commit = git_fixtures.ReleaseManifestTests.commit

    def setUp(self):
        self.setUpGit()
        fixture = frontier_fixtures.SemanticFrontierTests()
        fixture.setUp()
        self.frontier = copy.deepcopy(fixture.value)
        self.receipt = {"schema_version": 1, "kind": "exact_code_review", "decision": "accept",
                        "reviewed_commit": self.git("rev-parse", "HEAD").decode().strip(),
                        "source_raw_bindings": {"convex/checks.ts": hashlib.sha256(
                            b"export const scope = 'current';\n").hexdigest()},
                        "authenticated": True, "recipient_decision": "accept"}

    def inputs(self):
        raw = json.dumps(self.receipt, indent=2).encode() + b"\n"
        self.frontier["capture"]["receipt_raw_sha256"] = hashlib.sha256(raw).hexdigest()
        self.frontier["capture"]["reviewed_commit"] = self.receipt["reviewed_commit"]
        return json.dumps(self.frontier).encode(), raw

    def report(self):
        return review_input_report(self.root, *self.inputs())

    def test_matching_input_binds_domains_and_never_approves(self):
        frontier, receipt = self.inputs()
        with patch('sqlite3.connect', side_effect=AssertionError('No SQL')):
            r = review_input_report(self.root, frontier, receipt)
        self.assertEqual(r['input_consistency'], 'matching_checked_inputs')
        self.assertEqual(r['inputs']['receipt_raw_sha256'], hashlib.sha256(receipt).hexdigest())
        self.assertEqual(r['inputs']['frontier_raw_sha256'], hashlib.sha256(frontier).hexdigest())
        self.assertEqual(r['frontier_check']['receipt_raw_sha256'], r['inputs']['receipt_raw_sha256'])
        self.assertEqual(r['source_check']['receipt_raw_sha256'], r['inputs']['receipt_raw_sha256'])
        self.assertEqual(r['source_check']['projection_source_binding']['receipt_raw_sha256'],
                         r['inputs']['normalized_projection_sha256'])
        self.assertNotEqual(r['inputs']['receipt_raw_sha256'], r['inputs']['normalized_projection_sha256'])
        self.assertEqual(r['recipient_decision'], 'not_evaluated')
        self.assertEqual(r['authentication'], 'unverified_import')
        self.assertEqual(r['implementation_review'], 'pending')
        self.assertEqual(r['runtime_review'], 'pending')
        self.assertEqual(r['overall_status'], 'pending')
        self.assertEqual(len(r['unmet_gates']), 6)

    def test_cross_input_commit_and_raw_receipt_mismatch_before_git(self):
        f, r = self.inputs();v=json.loads(f);v['capture']['reviewed_commit']='a'*40
        with patch('review_input_report.inspect_adapted_binding') as source:
            with self.assertRaisesRegex(ValueError, 'commits differ'):
                review_input_report(self.root,json.dumps(v).encode(),r)
            with self.assertRaises(ValueError): review_input_report(self.root,f,r+b' ')
            source.assert_not_called()

    def test_invalid_receipt_and_frontier_reject_before_git(self):
        f, r = self.inputs()
        with patch('review_input_report.inspect_adapted_binding') as source:
            for bad in (b'{}', b'[]', b'{', b' '*1048577):
                with self.assertRaises(ValueError): review_input_report(self.root,bad,r)
            self.receipt['decision']=['accept'];f,r=self.inputs()
            with self.assertRaises(ValueError): review_input_report(self.root,f,r)
            source.assert_not_called()

    def test_forged_response_and_collector_pending_remain_pending(self):
        original = copy.deepcopy(self.frontier)
        self.frontier['capture']['observations'][0]['result_json']='{}'
        r=self.report();self.assertEqual(r['input_consistency'],'pending')
        self.assertIn('recorder_identity_mismatch',r['diagnostics'])
        self.frontier = original
        self.frontier.update(diagnostics=['opaque_reason'],observation_state='pending')
        r=self.report();self.assertEqual(r['input_consistency'],'pending')
        self.assertIn('collector_reported_pending',r['diagnostics'])

    def test_every_reply_requires_full_content(self):
        cap=self.frontier['capture']
        ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,
             'author_agent_id':cap['recorder_agent_id'],'author_owner_id':cap['reviewer_owner_id']}
        reply={'kind':'post','id':ref['post_id'],'revision':1,
               'author':{'id':ref['author_agent_id'],'user_id':ref['author_owner_id']}}
        for obs in [cap['observations'][2],self.frontier['observations'][-1]]:
            v=json.loads(obs['result_json']);v['result']['reply_count']=1;obs['result_json']=json.dumps(v)
        self.frontier['observations'][0]['result_json']=json.dumps({'items':[{'post':reply}],'next_cursor':None})
        self.frontier.update(reply_refs=[ref],diagnostics=['replies_require_full_review'],observation_state='pending')
        r=self.report();self.assertIn('replies_require_full_content_disposition',r['diagnostics'])
        self.assertEqual(r['input_consistency'],'pending')

    def test_nonaccept_verdict_source_mismatch_and_target_drift(self):
        for verdict in ('revise','unresolved'):
            self.receipt['decision']=verdict;r=self.report()
            self.assertEqual(r['declared_review_verdict'],verdict)
            self.assertIn('declared_verdict_not_accept',r['diagnostics'])
            self.assertEqual(r['overall_status'],'pending')
        self.receipt['decision']='accept'
        self.receipt['source_raw_bindings']['missing.py']='0'*64
        self.assertIn('declared_source_bytes_mismatch',self.report()['diagnostics'])
        self.receipt['source_raw_bindings'].pop('missing.py')
        self.write('convex/checks.ts','new tree\n');self.commit()
        r=self.report();self.assertIn('target_tree_differs',r['diagnostics'])
        self.assertTrue(r['source_check']['projection_source_binding']['declared_bindings_match'])

    def test_cli_preserves_all_bytes_and_only_reports(self):
        f,r=self.inputs();fp=self.root/'frontier.json';rp=self.root/'receipt.json'
        fp.write_bytes(f);rp.write_bytes(r)
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        cli=[sys.executable,'-B',str(Path(__file__).with_name('review_input_report.py')),
             '--root',str(self.root),'--frontier',str(fp),'--receipt',str(rp)]
        result=json.loads(subprocess.check_output(cli))
        self.assertEqual(result['overall_status'],'pending')
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        fp.write_bytes(b'{}');bad=subprocess.run(cli,capture_output=True)
        self.assertEqual(bad.returncode,2)
        self.assertIn(b'Review input report failed',bad.stderr)


if __name__ == '__main__': unittest.main()
