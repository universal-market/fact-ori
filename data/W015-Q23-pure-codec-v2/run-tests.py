"""Run each authored evidence group in a fresh process, bounded to 45s each."""
import subprocess,pathlib,json,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
base=root/'data/W015-Q23-pure-codec-v2'
for mode in ['grammar','fault','purity']:
 r=subprocess.run(['node','scripts/diagnostic-checkpoint-codec-v2.test.mjs',mode],cwd=root,capture_output=True,text=True,timeout=45)
 assert r.returncode==0,(mode,r.stdout,r.stderr)
 print(mode,json.loads((base/f'{mode}-results.json').read_text())['passed'],'passed')
