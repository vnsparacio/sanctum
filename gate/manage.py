"""Owner-operated local maintenance. Never sends prompts to hosted models."""
import argparse
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from common import Refused, canonical, load_settings, verify_release
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from media import prepare

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['prepare','status','stop','resume','sweep']); p.add_argument('files',nargs='*'); p.add_argument('--release',choices=['PRIVATE_80B','PRIVATE_LEAD'],default='PRIVATE_80B')
    args=p.parse_args(); verify_release(); settings=load_settings()
    if args.command=='prepare': return prepare(args.files,settings)
    if args.files: raise Refused('unexpected_arguments')
    lc=PrivateLeadLifecycle(settings) if args.release=='PRIVATE_LEAD' else Private80BLifecycle(settings)
    if args.command=='stop': lc.sweep(immediate=True,manual=True)
    elif args.command=='resume': lc.resume()
    elif args.command=='sweep': lc.sweep()
    return lc.status()
if __name__=='__main__':
    try: print(canonical(main()))
    except Exception as e: raise SystemExit('REFUSED: '+(str(e) if type(e) is Refused else 'local_operation_failed'))
