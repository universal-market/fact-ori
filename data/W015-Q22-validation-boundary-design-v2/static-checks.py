"""Static v2 commitment/pin consistency only. No proposed runtime test executes."""
import hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2];base=root/'data/W015-Q22-validation-boundary-design-v2'
d=json.loads((base/'design.json').read_text());m=json.loads((base/'fault-matrix.json').read_text());prior=json.loads((base/'prior-bindings.json').read_text());doc=(root/'docs/diagnostic-validation-boundary-design-v2.md').read_text()
assert d['status']=='proposed_not_implemented' and d['design_version']==2
assert d['roles']['validator_owner']=='@adrian.factfinder'
assert d['codec_own_keys']['objects']=='Object.create(null)'
assert len(m['rows'])==35 and len({r['id'] for r in m['rows']})==35
assert all(r['status']=='REQUIRED_NOT_EXECUTED' for r in m['rows'])
old=json.loads((root/'data/W015-Q21-validation-boundary-design-v1/fault-matrix.json').read_text());assert m['rows'][:24]==old['rows']
for phrase in ['Object.defineProperty','syncBuiltinESMExports','preloaded captured-original control','Buffer.toString("utf8")','No shared edit exception/assignment']:
 assert phrase in doc,phrase
assert d['classification']['unknown_or_bug_or_resource']=='whole_verifier_failure_no_rows'
for f,h in prior.items():assert hashlib.sha256((root/f).read_bytes()).hexdigest()==h,f
paths=['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs'];bs=[(root/'service'/x).read_bytes() for x in paths]
assert all(not b.startswith(b'\xef\xbb\xbf') for b in bs)
for b in bs:b.decode('utf8')
assert hashlib.sha256(b'\n'.join(bs)).hexdigest()==json.loads((root/'data/W015-Q8-real-model-protocol-v1/protocol.json').read_text())['engine_fingerprint']
result={'schema_version':1,'task_key':'FO-W015-Q22','static_checks':'pass','prior_bindings_verified':len(prior),'original_24_obligations_preserved':True,'required_runtime_scenarios':35,'runtime_scenarios_executed':0,'current_valid_UTF8_no_BOM_pins_fingerprint_consistent':True,'scope':'Static design commitment/pin consistency only; no proposed parser/harness/loader implementation, runtime scenario, feasibility/correctness or factual acceptance.'}
pathlib.Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
