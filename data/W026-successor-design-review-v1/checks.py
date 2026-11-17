"""Offline artifact integrity checks, not a source/model/router implementation."""
import hashlib
import json
from pathlib import Path
import subprocess

SCOPE='3b59496f1b23fcc50c8cd5270dc815f8563a81c6'
def read(p):return json.loads(Path(p).read_bytes())
m=read('data/W026-successor-design-input-v1.json');bindings=[]
for b in [dict(path='data/W026-successor-design-input-v1.json',commit=SCOPE,raw_sha256='aee44578fd8cd106c196093f44420d7085b6811411ec005cac1874681a933045'),m['proposal'],*m['frozen_inputs']]:
    c=SCOPE if b['commit']=='this_scope_commit' else b['commit']
    raw=subprocess.check_output(['git','show',c+':'+b['path']])
    assert hashlib.sha256(raw).hexdigest()==b['raw_sha256'] and raw==Path(b['path']).read_bytes()
    bindings.append(dict(path=b['path'],commit=c,raw_sha256=b['raw_sha256'],git_workspace_equal=True))
p=read('data/W026-successor-design-v1.json');old=read('data/W026-reference-candidate-v1/record.json');prior=read('data/FO-W026-factfinder-review-v1.json')
assert p['claim_id'] is None and p['decisions']['formal_candidate']=='not_authored'
assert p['decisions']['factual_verdict']=='none_for_new_library_record' and p['decisions']['api_activation'] is False
assert p['inference']['kind']=='source_attribution_only'
assert p['proposed_claim'].startswith("IAPWS's") and 'approximately' in p['proposed_claim'] and 'ITS-90' in p['proposed_claim']
assert '101.325' not in p['proposed_claim'] and 'pure water' not in p['proposed_claim']
assert old['id']=='W026-A' and prior['decision']['review']=='REVISE'
assert p['prior_history']['candidate_raw_sha256']==hashlib.sha256(Path('data/W026-reference-candidate-v1/record.json').read_bytes()).hexdigest()
assert p['prior_history']['source_review_raw_sha256']==hashlib.sha256(Path('data/FO-W026-factfinder-review-v1.json').read_bytes()).hexdigest()
assert p['source']['dependence_group']=='iapws-reference-formulation'
assert len(p['fixtures'])==len({r['id'] for r in p['fixtures']})==10
assert {r['id'] for r in p['fixtures'] if r['expected']=='attributed_answer'}=={'A01','A02'}
assert next(r for r in p['fixtures'] if r['id']=='B07')['expected']=='withhold_pending_gates'
print(json.dumps(dict(schema_version=1,bindings=bindings,checks=dict(scope_pins=5,claim_id_null=True,no_new_library_factual_verdict_or_api_activation=True,narrow_source_attribution_not_pressure_purity_conjunction=True,original_candidate_and_REVISE_history_preserved=True,unique_authored_fixtures=10,attributed_answer_case_ids=['A01','A02'],api_gates_withheld=True,source_model_dependence_explicit=True),limits='Artifact integrity/structural assertions only; manual source and fixture review recorded separately. No equations, physical-property calculations, identifier search/reservation, router or deployed API executed.'),indent=2))
