"""Canonical plugin build; never refresh integrity expectations automatically."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,cwd=ROOT):
 with tempfile.TemporaryDirectory(prefix='sanctum-build-') as td:
  subprocess.run(args,cwd=cwd,check=True,env={**os.environ,'OPENCLAW_HOME':td,'OPENCLAW_STATE_DIR':td,'OPENCLAW_CONFIG_PATH':td+'/openclaw.json','PATH':str(ROOT/'node_modules/.bin')+os.pathsep+os.environ['PATH']})
def build():
 for p in sorted((ROOT/'plugins').iterdir()):
  if 'defineToolPlugin' in (p/'src/index.ts').read_text():
   run(['npm','run','plugin:build'],p)
   run(['npm','run','plugin:validate'],p)
  else:
   run(['npm','run','build'],p)
   run(['node','--input-type=module','-e',"const m=await import('./dist/index.js'); if (!m.default || typeof m.default.register !== 'function') process.exit(1);"],p)
 # The original runtime hashes are reviewed version pins, not newly observed trust.
 for name,expected in json.loads((ROOT/'reliability/runtime-pins.json').read_text()).items():
  if name.startswith('node_modules/') and digest(ROOT/name)!=expected:raise SystemExit('OpenClaw runtime drift: '+name)
 subprocess.run(['node',str(ROOT/'scripts/capability_manifest.mjs'),'--check'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 print('Plugin builds/manifests validated; reviewed OpenClaw runtime pins match.')
if __name__=='__main__':build()
