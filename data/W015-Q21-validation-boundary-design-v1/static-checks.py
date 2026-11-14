"""Static design/pin consistency only; proposed runtime scenarios are not executed."""
import hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
p=root/'data/W015-Q21-validation-boundary-design-v1'
d=json.loads((p/'design.json').read_text());m=json.loads((p/'fault-matrix.json').read_text())
assert d['status']=='proposed_not_implemented'
assert d['roles']['validator_owner']=='@adrian.factfinder'
assert d['caps']=={'checkpoint_bytes':262144,'json_depth':16,'projection_bytes':4096,'cases':2}
assert d['loader']['all_dependency_io_before_checkpoint_access']
assert d['classification']['unknown_or_bug_or_resource']=='whole_verifier_failure_no_rows'
assert len(m['rows'])==24 and len({r['id'] for r in m['rows']})==24
assert all(r['status']=='REQUIRED_NOT_EXECUTED' for r in m['rows'])
assert {r['stage'] for r in m['rows']}=={'loader','pure','prefix','commit','positive','history','content','lifecycle'}
basis=json.loads((root/'data/W015-Q20-adapter-readiness-v1/review-input.json').read_text())
for f,h in basis['raw_bindings'].items():assert hashlib.sha256((root/f).read_bytes()).hexdigest()==h,f
paths=['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs']
fingerprint=hashlib.sha256('\n'.join((root/'service'/x).read_bytes().decode('utf8') for x in paths).encode()).hexdigest()
protocol=json.loads((root/'data/W015-Q8-real-model-protocol-v1/protocol.json').read_text());assert fingerprint==protocol['engine_fingerprint']
result={'schema_version':1,'task_key':'FO-W015-Q21','static_checks':'pass','prior_bindings_verified':114,'required_runtime_scenarios':24,'runtime_scenarios_executed':0,'cached_fingerprint_formula_matches_pinned_protocol':True,'scope':'Static structure/source-pin consistency only; no design feasibility/correctness/runtime acceptance or factual truth established.'}
pathlib.Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
