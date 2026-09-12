"""Credential-free suites; no provider/real source calls."""
from pathlib import Path
import os,subprocess,sys,tempfile,json
ROOT=Path(__file__).resolve().parents[1]
def main():
 with tempfile.TemporaryDirectory(prefix='sanctum-tests-') as td:
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OPENCLAW_HOME':td,'OPENCLAW_STATE_DIR':td,'OPENCLAW_CONFIG_PATH':td+'/openclaw.json','VINCEAI_STATE_DIR':td,'PATH':str(ROOT/'node_modules/.bin')+os.pathsep+os.environ['PATH']}
  for k in ['VINCEAI_GATEWAY_PORT','VINCEAI_MLX_PORT','VINCEAI_CONTACTS_FILE']:env.pop(k,None)
  jobs=[('gate',['node','--test','--test-reporter=tap','tests/core.test.mjs','tests/local-agent.test.mjs']),('gate',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py']),('reliability',['node','--test','--test-reporter=tap',*[str(p.relative_to(ROOT/'reliability')) for p in sorted((ROOT/'reliability/tests').glob('*.test.mjs'))]]),('reliability',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py']),('mcp-integration',['node','--test','--test-reporter=tap','tests/guard.test.mjs']),('.', [sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py'])]
  for directory,args in jobs:subprocess.run(args,cwd=ROOT/directory,env=env,check=True)
  for p in sorted((ROOT/'plugins').iterdir()):
   if list((p/'src').glob('*.test.ts')):subprocess.run(['vitest','run','--config','vitest.config.ts'],cwd=p,env=env,check=True)
if __name__=='__main__':main()
