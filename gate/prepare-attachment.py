"""Local file picker. Preparation never contacts an AI provider."""
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent;sys.path.insert(0,str(BASE/'src'))
from common import load_settings, verify_release
from media import prepare

def main():
    verify_release()
    script='var a=Application.currentApplication(); a.includeStandardAdditions=true; JSON.stringify(a.chooseFile({withPrompt:"Select photos, a short video, or text documents for the Mac gate",multipleSelectionsAllowed:true}).map(String));'
    r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,timeout=600)
    if r.returncode:return
    files=json.loads(r.stdout);p=prepare(files,load_settings())
    subprocess.run(['/usr/bin/pbcopy'],input=p['command'].encode(),check=True)
    print('Prepared locally. Nothing has been sent to a model.\nPaste the copied /gate attach command into your saved Mac gate chat, then ask your question.\n'+p['command'])
if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Attachment preparation failed. Nothing was sent. Check the supported types and limits in README.md.')
