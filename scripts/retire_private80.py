"""Stopped-gateway historical cleanup using reviewed source and installed bindings.

This bridge is needed before installing the amendment that knows RETIRED. It
never copies runtime files, allocates, starts a model, or refreshes a freeze.
"""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'gate/src'),str(ROOT/'scripts')]
import release_operator as op
from common import Refused, canonical, strict_json
from lifecycle import Private80BLifecycle
from runpod import Runpod


def reconcile(prefix):
    op.verify();op.verify_install(prefix)
    if op.owns_process(op.process_record(prefix)):raise Refused('gateway_must_be_stopped')
    settings=strict_json((prefix/'gate/SETTINGS.json').read_text())
    if Path(settings['state_directory']) != prefix/'state/gate':raise Refused('retirement_state_binding')
    provider=Runpod(settings)
    provider.cli=prefix/'gate/runtime/runpodctl'
    # Cleanup provider errors retain fixed codes only, never response bodies.
    provider.experiment_deadline=0;provider.experiment_cleanup=True
    lc=Private80BLifecycle(settings,provider=provider)
    lc.sweep(immediate=True,manual=True)
    result=lc.status()
    if result['phase']!='RETIRED':raise Refused('retired_ownership_unreconciled')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True,type=Path);p.add_argument('--reconcile',action='store_true',required=True)
    args=p.parse_args()
    try:print(canonical(reconcile(args.prefix.absolute())))
    except (OSError,ValueError,KeyError):raise SystemExit('REFUSED: retirement reconciliation incomplete; preserve ownership and supervision')
