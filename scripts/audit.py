"""Publication checks: report filenames/categories, never secret match contents."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
SKIP={'node_modules','.venv','.local','__pycache__','dist','.git','state','logs'}
def sources(root=ROOT):
 import os
 for base,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=sorted(d for d in dirs if d not in SKIP)
  for n in sorted(files):yield Path(base)/n
PATTERNS={'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','provider_key':r'\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})\b','owner_home':r'/Users/(?!example(?:/|$)|<)[a-zA-Z][a-zA-Z0-9_-]+/'}
# Exact public location declarations requested for V1.1 developer context.
# No directory-wide exemption: additional home bindings in either file fail.
APPROVED_LOCATION_DECLARATIONS = {
 'AGENTS.md': (
  '- `/Users/tter/Projects/sanctum` is the canonical V1.1 source. Its remote is `https://github.com/vnsparacio/sanctum.git`; preserve the V1 tag and stable `main` history.',
  '- `/Users/tter/.sanctum/vinceai-v1.1` is the external private owner runtime. `/Users/tter/Projects/hybrid-ai` is legacy reference and rollback evidence. Never modify or repin the legacy tree during V1.1 engineering.',
 ),
 'docs/V1.1-LIVE-BASELINE.md': (
  '`/Users/tter/Projects/sanctum` is the development source of truth.',
  '`/Users/tter/.sanctum/vinceai-v1.1` is the external private owner runtime.',
  '`/Users/tter/Projects/hybrid-ai` is legacy reference/rollback only.',
 ),
}
def scan(root=ROOT):
 issues=[]
 for p in sources(root):
  rel=str(p.relative_to(root))
  if p.is_symlink():issues.append((rel,'symlink'));continue
  if p.name=='.DS_Store':issues.append((rel,'private/generated Finder metadata'))
  if p.name.startswith('.env') and p.name!='.env.example':issues.append((rel,'environment file'))
  if p.suffix in {'.sqlite','.db','.pem','.key','.gguf','.safetensors','.zip','.gz'}:issues.append((rel,'private/generated artifact'))
  if p.stat().st_size>5*1024*1024:issues.append((rel,'large source'))
  text=p.read_text(errors='replace')
  if rel!='scripts/audit.py':
   for label,pattern in PATTERNS.items():
    review_text=text
    if label=='owner_home' and rel in APPROVED_LOCATION_DECLARATIONS:
     review_text='\n'.join(line for line in text.splitlines() if line not in APPROVED_LOCATION_DECLARATIONS[rel])
    if re.search(pattern,review_text):issues.append((rel,label))
 return issues

def docs():
 issues=[]
 for p in (ROOT/'docs').rglob('*.md'):
  for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
   if '://' not in target and not target.startswith('#') and not (p.parent/target.split('#')[0]).exists():issues.append((str(p.relative_to(ROOT)),'broken link: '+target))
 return issues
if __name__=='__main__':
 issues=scan()+docs();print(json.dumps({'files_scanned':sum(1 for _ in sources()),'issues':issues},indent=2));sys.exit(bool(issues))
