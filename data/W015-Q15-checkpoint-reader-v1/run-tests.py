"""Prepare an owned FIFO in Python; Node subprocess spawning is host-restricted."""
import os,pathlib,tempfile,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='factori-q15-fifo-') as directory:
 os.chmod(directory,0o700);os.mkfifo(pathlib.Path(directory)/'01-capital.json',0o600)
 result=subprocess.run(['node','scripts/diagnostic-checkpoint-reader-v1.test.mjs',directory],cwd=root,capture_output=True,text=True,timeout=20)
 print(result.stdout,end='');print(result.stderr,end='')
 assert result.returncode==0 and 'pass 18' in result.stdout and 'skipped 0' in result.stdout
