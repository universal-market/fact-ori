import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_reply_disposition import reply_disposition_report, SCHEMA_SHA256

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'data/W020-E1-F1-factfinder-design-v1'


class ReplyDispositionTests(unittest.TestCase):
    def setUp(self):
        self.d = json.loads((FIXTURES/'example.synthetic.json').read_bytes())
        self.o = json.loads((FIXTURES/'observations.synthetic.json').read_bytes())

    def report(self, d=None, o=None):
        return reply_disposition_report(json.dumps(self.d if d is None else d).encode(),
                                        json.dumps(self.o if o is None else o).encode())

    def test_all_frozen_design_recipes_and_unchanged_inputs(self):
        cases=json.loads((FIXTURES/'fixtures.json').read_bytes())['cases']
        self.assertEqual(len(cases),62)
        for case in cases:
            with self.subTest(case=case['id']):
                d=copy.deepcopy(self.d);o=copy.deepcopy(self.o)
                for op in case['operations']:
                    node=d if op['side']=='disposition' else o
                    for key in op['path'][:-1]:node=node[key]
                    if op.get('delete'):del node[op['path'][-1]]
                    else:node[op['path'][-1]]=copy.deepcopy(op['value'])
                before=copy.deepcopy((d,o))
                # Strict malformed observations reject before comparison.
                try:r=self.report(d,o)
                except ValueError:
                    self.assertEqual(case['expected'],'invalidated');continue
                self.assertEqual(r['outcome'],case['expected'])
                self.assertEqual(r['collector_diagnostics'],o['collector_diagnostics'])
                self.assertEqual(len(r['unmet_gates']),6)
                self.assertEqual(r['authentication'],'unverified_import')
                self.assertEqual(r['recipient_decision'],'not_evaluated')
                self.assertTrue(all(r[k]=='pending' for k in ('overall_status','runtime_review','implementation_review')))
                self.assertFalse(r['author_withdrawal_established'])
                self.assertEqual((d,o),before)

    def test_raw_canonical_domains_and_no_sql_or_network(self):
        raw=json.dumps(self.d).encode();other=json.dumps(self.d,indent=2).encode()
        with patch('sqlite3.connect',side_effect=AssertionError('no SQL')), patch('socket.socket',side_effect=AssertionError('no network')):
            a=reply_disposition_report(raw,json.dumps(self.o).encode())
            b=reply_disposition_report(other,json.dumps(self.o).encode())
        self.assertNotEqual(a['inputs']['disposition_raw_sha256'],b['inputs']['disposition_raw_sha256'])
        self.assertEqual(a['inputs']['disposition_canonical_sha256'],b['inputs']['disposition_canonical_sha256'])
        self.assertEqual(a['inputs']['schema_raw_sha256'],SCHEMA_SHA256)
        self.assertEqual(a['coverage_evidence'],'unchecked_imported_assertions')

    def test_strict_json_rejects_duplicates_numbers_and_size(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1.0}',b'{"x":9007199254740992}', b' '* (1024*1024+1)):
            with self.subTest(raw=raw[:40]),self.assertRaises(ValueError):
                reply_disposition_report(raw,json.dumps(self.o).encode())

    def test_observation_flags_shapes_and_conflicting_owner_are_not_authority(self):
        for field in ('frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied'):
            o=copy.deepcopy(self.o);o[field]=1
            with self.subTest(field=field),self.assertRaises(ValueError):self.report(o=o)
        o=copy.deepcopy(self.o);o['authenticated']=True
        with self.assertRaises(ValueError):self.report(o=o)
        o=copy.deepcopy(self.o);a=copy.deepcopy(o['known_actors'][0]);a['owner_id']='44444444-4444-4444-8444-444444444444';o['known_actors'].append(a)
        with self.assertRaises(ValueError):self.report(o=o)
        o=copy.deepcopy(self.o);o['replies'][0]['revision']=True
        with self.assertRaises(ValueError):self.report(o=o)

    def test_consistent_forgery_remains_unverified_and_drift_invalidates(self):
        o=copy.deepcopy(self.o);o['replies'][0]['body_sha256']='e'*64
        self.assertEqual(self.report(o=o)['outcome'],'invalidated')
        d=copy.deepcopy(self.d);d['entries'][0]['reply']['body_sha256']='e'*64
        from sidecar_digest import canonical_bytes
        d['coverage']['reply_set_sha256']=hashlib.sha256(canonical_bytes(o['replies'])).hexdigest()
        r=self.report(d,o)
        self.assertEqual(r['outcome'],'corresponding_nonblocking_declaration')
        self.assertEqual(r['overall_status'],'pending')
        self.assertEqual(r['coverage_evidence'],'unchecked_imported_assertions')

    def test_cli_success_error_and_unchanged_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);d=root/'d.json';o=root/'o.json'
            d.write_text(json.dumps(self.d));o.write_text(json.dumps(self.o))
            before={p.name:p.read_bytes() for p in root.iterdir()}
            cmd=[sys.executable,'-B',str(ROOT/'scripts/review_reply_disposition.py'),'--disposition',str(d),'--observations',str(o)]
            result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['outcome'],'corresponding_nonblocking_declaration')
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})
            o.write_bytes(b'{"x":1,"x":2}')
            result=subprocess.run(cmd,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,b'')
