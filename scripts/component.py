"""Foreground host components with fixed commands and isolated environment."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys,json,urllib.request
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_operator',ROOT/'scripts/release_operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
p=argparse.ArgumentParser();p.add_argument('component',choices=['mlx','messages','gmail','calendar','markdown','files','webui']);p.add_argument('--prefix',type=Path,default=ROOT/'.local');p.add_argument('--health',action='store_true');p.add_argument('--cache-only',action='store_true');a=p.parse_args();prefix=a.prefix.absolute();op.verify();r=op.verify_install(prefix);env=op.environment(prefix)
if a.health:
 if a.component not in ('mlx','webui'):raise SystemExit('Health probe is supported for mlx/webui only')
 url=f"http://127.0.0.1:{r['mlx_port']}/v1/models" if a.component=='mlx' else 'http://127.0.0.1:28000/health'
 try:
  with urllib.request.urlopen(url,timeout=5) as response:result=json.load(response)
  if a.component=='mlx' and 'mlx-community/Qwen3-4B-Instruct-2507-4bit' not in [x.get('id') for x in result.get('data',[])]:raise ValueError('Unexpected local model identity')
  if a.component=='webui' and result.get('status') is not True:raise ValueError('WebUI not healthy')
 except Exception:raise SystemExit('Component unavailable or identity mismatch; inspect its private log and start the candidate component. No fallback was used.')
 print('Healthy:',a.component);raise SystemExit(0)
env.setdefault('VINCEAI_NOTES_DIR',str(prefix/'notes'));env['VINCEAI_GOOGLE_HOME']=str(prefix/'state/google-readonly')
python=str(ROOT/'.venv/bin/python');brokers={'messages':'messages-read-broker.py','gmail':'gmail-read-broker.py','calendar':'calendar-read-broker.py','markdown':'local-markdown-broker.py','files':'file-steward-broker.py'}
if a.component in brokers:
 if a.component in ('messages','gmail','calendar') and (not (prefix/'config'/(a.component+'.enabled')).is_file() or (prefix/'config'/(a.component+'.enabled')).read_text().strip()!='enabled'):raise SystemExit('Configure the read-only integration and create config/'+a.component+'.enabled first; see docs/installation.md')
 args=[python,'-B',str(ROOT/'host/macos'/brokers[a.component])]
elif a.component=='mlx':
 exe=str(prefix/'runtime/mlx/bin/mlx_lm.server')
 if not Path(exe).is_file():raise SystemExit('Run scripts/bootstrap.py mlx with the same --prefix first')
 if a.cache_only:env['HF_HUB_OFFLINE']='1'
 args=[exe,'--model','mlx-community/Qwen3-4B-Instruct-2507-4bit','--host','127.0.0.1','--port',str(r['mlx_port']),'--max-tokens','4096','--decode-concurrency','1','--prompt-concurrency','1','--prefill-step-size','512','--prompt-cache-size','2','--prompt-cache-bytes','4294967296']
else:
 exe=str(prefix/'runtime/webui/bin/open-webui')
 if not Path(exe).is_file():raise SystemExit('Run scripts/bootstrap.py webui with the same --prefix first')
 for name in ('ENABLE_OLLAMA_API','ENABLE_OPENAI_API','ENABLE_MEMORIES','ENABLE_WEB_SEARCH','ENABLE_VERSION_UPDATE_CHECK','ENABLE_EVALUATION_ARENA_MODELS','ENABLE_AUTOMATIONS','ENABLE_MEMORY_SYSTEM_CONTEXT','ENABLE_MEMORY_BACKGROUND_REVIEW'):
  env[name]='False'
 env['OFFLINE_MODE']='True'
 env['CORS_ALLOW_ORIGIN']='http://127.0.0.1:28000;http://localhost:28000'
 env['DO_NOT_TRACK']='True';env['ANONYMIZED_TELEMETRY']='False';env['SCARF_NO_ANALYTICS']='True'
 env['DATA_DIR']=str(prefix/'state/webui');args=[exe,'serve','--host','127.0.0.1','--port','28000']
os.umask(0o077)
raise SystemExit(subprocess.call(args,cwd=prefix,env=env))
