"""Actual signed/frozen worker; only loopback endpoint bytes are synthetic."""
import io
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
package=Path(PACKAGE_ROOT);fixture=Path(FIXTURE_ROOT)
sys.path[:0]=[str(package),str(package/'src')]
import backends
from experiment import ExperimentLedger
settings=json.loads((package/'SETTINGS.json').read_text())
ledger=ExperimentLedger(Path(settings['state_directory'])/'private-lead')

class Opener:
    def open(self,req,timeout=None):
        if req.full_url.endswith('/models'):
            return io.BytesIO(json.dumps({'data':[{'id':settings['private_lead']['alias']}]}).encode())
        record=ledger.current();snapshot=ledger.snapshot({k:record[k] for k in ('experiment_id','source_id','install_id','deadline')})
        with (fixture/'dispatch-counts.jsonl').open('a') as out:out.write(json.dumps({'reserved':snapshot['counts']['reserved'],'dispatched':snapshot['counts']['dispatched'],'timeout':timeout,'deadline':record['deadline']})+'\n')
        text=json.dumps({'kind':'ESCALATION','reason':'SYNTHETIC'})
        return io.BytesIO(('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode())
with patch('backends.urllib.request.build_opener',return_value=Opener()):
    runpy.run_path(str(package/'worker.py'),run_name='__main__')
