import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from full_content_snapshot import snapshot_report, sha, MAX_BYTES
import test_verify_review_frontier as antecedent

ROOT = Path(__file__).resolve().parents[1]
encode = lambda v: json.dumps(v, ensure_ascii=True).encode()


def fixture(reply=False, distinct_editor=False):
    # Complete invented inputs; never load a private capture or contact a host.
    base = antecedent.SemanticFrontierTests(); base.setUp()
    f = copy.deepcopy(base.value)
    selected = copy.deepcopy(base.post)
    selected.update(parent_post_id=base.recorder, direct_reply_count=0)
    selected['author']['kind'] = 'agent'
    if reply:
        selected.update(id='66666666-6666-4666-8666-666666666666', parent_post_id=base.pid)
        selected['author']['id'] = base.recorder
        ref = {'post_id': selected['id'], 'revision': 1, 'author_agent_id': base.recorder, 'author_owner_id': base.owner}
        f.update(reply_refs=[ref], diagnostics=['replies_require_full_review'], observation_state='pending')
        f['observations'][0]['result_json'] = json.dumps({'result': {'items': [{'post': selected}], 'next_cursor': None}})
        for o in [f['capture']['observations'][2], f['observations'][-1]]:
            v = json.loads(o['result_json']); v['result']['reply_count'] = 1; o['result_json'] = json.dumps(v)
    editor_id = '77777777-7777-4777-8777-777777777777'
    if distinct_editor:
        selected['edited_by'] = {'id': editor_id, 'kind': 'agent', 'handle': 'ignored label'}
    def obs(tool, args, value):
        return {'tool': tool, 'arguments': args, 'result_json': json.dumps({'result': value, 'fractional_metadata': 0.25}), 'observed_at': base.time, 'is_error': False}
    agents = sorted({selected['author']['id']} | ({editor_id} if distinct_editor else set()))
    pinned = {k:selected[k] for k in ('revision','title','body','status','edited_by')}
    pinned.update(post_id=selected['id'], changed_by={'id':editor_id,'kind':'agent'})
    observations = [obs('get_my_profile', {}, {'profile': {'id':base.recorder,'user_id':base.owner,'kind':'agent'}}), obs('get_post', {'post_id':selected['id']}, selected)]
    observations += [obs('get_agent', {'agent_id':a}, {'id':a,'user_id':base.owner,'kind':'agent'}) for a in agents]
    observations += [obs('get_post_revision', {'post_id':selected['id'],'revision':1}, pinned), obs('get_post', {'post_id':selected['id']}, selected)]
    receipt = base.receipt
    packet = {'schema_version':1,'profile':'full-post-snapshot-input-v1','capture_id':f['capture']['capture_id'],'recorder_agent_id':base.recorder,'receipt_raw_sha256':sha(receipt),'frontier_raw_sha256':sha(encode(f)),'reviewed_commit':'a'*40,'target_commit':'b'*40,'selector':{'post_id':selected['id'],'revision':1,'parent_post_id':selected['parent_post_id']},'observations':observations}
    return packet, f, receipt


class SnapshotTests(unittest.TestCase):
    def run_packet(self, p, f, r):
        return snapshot_report(encode(p), encode(f), r)

    def assert_pending(self, result):
        self.assertEqual(result['authentication'], 'unverified_import')
        self.assertEqual(result['coverage_state'], 'pending_resolver')
        self.assertEqual(len(result['unmet_gates']), 6)
        self.assertEqual(result['recipient_decision'], 'not_evaluated')
        self.assertEqual(result['overall_status'], 'pending')
        for key in ('frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied'):
            self.assertNotIn(key, result)

    def test_complete_root_reply_and_editor_positives_preserve_bytes(self):
        for reply, edited in itertools.product([False, True], repeat=2):
            p,f,r = fixture(reply,edited); before=encode([p,f]); result=self.run_packet(p,f,r)
            self.assertEqual(result['snapshot_state'],'matching_imported_full_content_observations')
            self.assert_pending(result);self.assertEqual(before,encode([p,f]))
            self.assertEqual(result['provenance']['observations'],p['observations'])
            self.assertEqual(result['snapshot']['body_sha256'],sha(b'accept'))
            self.assertEqual(result['prerequisite']['original_collector_diagnostics'],f['diagnostics'])
            self.assertEqual(len(result['provenance']['result_json_sha256']),6 if edited else 5)

    def mutate_response(self,p,index,change):
        value=json.loads(p['observations'][index]['result_json']);change(value['result']);p['observations'][index]['result_json']=json.dumps(value)

    def test_selected_fields_missing_drift_identity_and_bounds(self):
        changes=[lambda v:v.pop('body'),lambda v:v.update(body=None),lambda v:v.update(title='changed'),lambda v:v.update(body='changed'),lambda v:v.pop('status'),lambda v:v.update(status='accepted'),lambda v:v.update(parent_post_id=None),lambda v:v.update(reply_count=1),lambda v:v.update(direct_reply_count=1),lambda v:v.update(revision=True),lambda v:v.update(reply_count=2**53),lambda v:v.update(direct_reply_count=-1),lambda v:v.pop('edited_by'),lambda v:v.update(edited_by={'id':'x','kind':'agent'}),lambda v:v['author'].update(kind='human'),lambda v:v['author'].update(user_id='77777777-7777-4777-8777-777777777777')]
        for change in changes:
            p,f,r=fixture();self.mutate_response(p,-1,change);result=self.run_packet(p,f,r)
            self.assertEqual(result['snapshot_state'],'hold');self.assertIsNone(result['snapshot']);self.assert_pending(result)
        for change in [lambda v:v.update(revision=True),lambda v:v.update(status='done'),lambda v:v.pop('status'),lambda v:v.update(edited_by={})]:
            p,f,r=fixture();self.mutate_response(p,-2,change);self.assertEqual(self.run_packet(p,f,r)['snapshot_state'],'hold')

    def test_order_arguments_error_flags_and_time_fail_closed(self):
        mutations=[lambda p:p['observations'][0].pop('is_error'),lambda p:p['observations'][0].update(is_error=True),lambda p:p['observations'][0].update(is_error=0),lambda p:p['observations'][1].update(tool='search_posts'),lambda p:p['observations'][2]['arguments'].update(extra=True),lambda p:p['observations'].reverse(),lambda p:p['observations'].pop(2),lambda p:p['observations'][0].update(observed_at='2026-02-30T00:00:00Z'),lambda p:p['observations'][0].update(observed_at='2026-11-11T04:00:01Z'),lambda p:p['observations'][0].update(observed_at='2026-11-11T04:00:00+01:00'),lambda p:p.update(capture_id='77777777-7777-4777-8777-777777777777'),lambda p:p.update(receipt_raw_sha256='0'*64),lambda p:p.update(target_commit='abc')]
        for mutate in mutations:
            p,f,r=fixture();mutate(p);self.assertEqual(self.run_packet(p,f,r)['snapshot_state'],'hold')
        for wrapper in [False,True]:
            for flag,value in [('error',None),('partial',True),('redacted',None),('unavailable',0),('truncated','false')]:
                p,f,r=fixture();v=json.loads(p['observations'][1]['result_json']);(v['result'] if wrapper else v)[flag]=value;p['observations'][1]['result_json']=json.dumps(v);self.assertEqual(self.run_packet(p,f,r)['snapshot_state'],'hold')

    def test_raw_reason_state_table_and_direct_parent(self):
        for reply,reasons,state in itertools.product([False,True],[[],['replies_require_full_review'],['opaque_transport_failure'],['replies_require_full_review','opaque_transport_failure'],['replies_require_full_review']*2],['pending','empty_frontier_observed','future',None]):
            p,f,r=fixture(reply);f.update(diagnostics=reasons,observation_state=state);p['frontier_raw_sha256']=sha(encode(f));result=self.run_packet(p,f,r)
            expected=(not reply and reasons==[] and state=='empty_frontier_observed') or (reply and reasons==['replies_require_full_review'] and state=='pending')
            self.assertEqual(result['snapshot_state']=='matching_imported_full_content_observations',expected)
        p,f,r=fixture(True);nested='77777777-7777-4777-8777-777777777777';p['selector']['parent_post_id']=nested
        for index in (1,-1): self.mutate_response(p,index,lambda v:v.update(parent_post_id=nested))
        self.assertEqual(self.run_packet(p,f,r)['snapshot_state'],'hold')

    def test_strict_json_depth_size_surrogates_and_no_echo(self):
        p,f,r=fixture();raw=encode(p)
        for bad in [b'{"schema_version":1,"schema_version":1}',b'['*65+b']'*65,b' '* (MAX_BYTES+1),b'{"n":NaN}',b'{"n":1.5}',b'{"x":"\\ud800"}',b'\xff']:
            result=snapshot_report(bad,encode(f),r);self.assertEqual(result['snapshot_state'],'hold');self.assert_pending(result)
        for bad in ['{"secret":"DO_NOT_ECHO","x":1,"x":2}', '{"n":NaN}', '['*65+']'*65, '{"text":"\\ud800"}', '{}'+ ' ' *262145]:
            p,f,r=fixture();p['observations'][1]['result_json']=bad;result=self.run_packet(p,f,r);self.assertEqual(result['snapshot_state'],'hold');self.assertNotIn('DO_NOT_ECHO',json.dumps(result))

    def test_exact_utf8_empty_text_editor_owner_and_coherent_forgery_limit(self):
        for title,body in [('', ''),('é','e\u0301\n'),('标题','正文\r\n')]:
            p,f,r=fixture(True,True)
            for index in (1,-2,-1):self.mutate_response(p,index,lambda v:v.update(title=title,body=body))
            result=self.run_packet(p,f,r);self.assertEqual(result['snapshot']['body_sha256'],sha(body.encode()));self.assert_pending(result)
        p,f,r=fixture(True,True);self.mutate_response(p,2,lambda v:v.update(user_id='77777777-7777-4777-8777-777777777777'));self.assertEqual(self.run_packet(p,f,r)['snapshot_state'],'hold')
        # All invented host-shaped JSON can correspond without authenticating it.
        p,f,r=fixture(True);result=self.run_packet(p,f,r);self.assertEqual(result['snapshot_state'],'matching_imported_full_content_observations');self.assert_pending(result)

    def test_extreme_exponents_hold_in_function_and_cli(self):
        for token, expected in [('1e999999999999999999999999','hold'),
                                ('1e-999999999999999999999999','hold'),
                                ('0.25','matching_imported_full_content_observations'),
                                ('1e-25','matching_imported_full_content_observations')]:
            p,f,r=fixture(True,True)
            raw=p['observations'][0]['result_json']
            p['observations'][0]['result_json']=raw[:-1]+',"ignored_numeric_metadata":'+token+'}'
            before=encode(p);result=self.run_packet(p,f,r)
            self.assertEqual(result['snapshot_state'],expected);self.assert_pending(result)
            self.assertEqual(before,encode(p))
            if expected=='hold':
                self.assertIsNone(result['snapshot'])
                self.assertEqual(result['diagnostics'],['snapshot_input_or_correspondence_invalid'])
                self.assertNotIn(token,json.dumps(result))
            else:
                self.assertEqual(result['provenance']['observations'],p['observations'])
            with tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);files={'packet':encode(p),'frontier':encode(f),'receipt':r}
                for name,content in files.items():(d/name).write_bytes(content)
                cmd=[sys.executable,'-B',str(ROOT/'scripts/full_content_snapshot.py')]
                for name in files:cmd.extend(['--'+name,str(d/name)])
                run=subprocess.run(cmd,cwd=tmp,capture_output=True,timeout=30)
                self.assertEqual(run.returncode,0);self.assertEqual(run.stderr,b'')
                actual=json.loads(run.stdout);self.assertEqual(actual,result)
                self.assertLessEqual(len(run.stdout),MAX_BYTES)
                self.assertEqual({x.name:x.read_bytes() for x in d.iterdir()},files)

    def test_cli_no_side_effects(self):
        p,f,r=fixture(True)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);files={'packet':encode(p),'frontier':encode(f),'receipt':r}
            for name,raw in files.items():(d/name).write_bytes(raw)
            cmd=[sys.executable,'-B',str(ROOT/'scripts/full_content_snapshot.py')]
            for name in files:cmd.extend(['--'+name,str(d/name)])
            result=json.loads(subprocess.check_output(cmd,cwd=tmp));self.assertEqual(result['snapshot_state'],'matching_imported_full_content_observations')
            self.assertEqual({x.name:x.read_bytes() for x in d.iterdir()},files)


if __name__ == '__main__':
    unittest.main()
