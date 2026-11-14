"""Prepare an owned FIFO and run finite raw observation probes."""
import os,pathlib,tempfile,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='factori-q19-fifo-') as directory:
 os.chmod(directory,0o700);os.mkfifo(pathlib.Path(directory)/'01-capital.json',0o600)
 r=subprocess.run(['node','scripts/diagnostic-checkpoint-observation-v2.test.mjs',directory],cwd=root,capture_output=True,text=True,timeout=30)
 print(r.stdout,end='');print(r.stderr,end='')
 assert r.returncode==0 and 'pass 20' in r.stdout and 'skipped 0' in r.stdout
