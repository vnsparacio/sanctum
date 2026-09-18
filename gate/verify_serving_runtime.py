"""Observe the pinned running server and verify schemas without completion calls.

Only reviewed code plus synthetic artifacts belong in the remote temporary bundle.
Importing this module has no environment, provider or model side effects.
"""
import argparse
import dataclasses
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import traceback

BASE=Path(__file__).resolve().parent
CACHE_KEYS=('HF_HOME','HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE','HF_ENDPOINT',
            'HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')


class VerificationFailure(ValueError):
    pass


def require(condition,code):
    if not condition:raise VerificationFailure(code)


def launch_contract(text):
    """Parse reviewed literal launch facts; never execute shell substitutions."""
    values={}
    for key in ('BASE','CACHE','MODEL','REVISION','ALIAS','VLLM'):
        match=re.search(r'^'+key+r'=(.+)$',text,re.M)
        require(match is not None,'BOOTSTRAP_CONTRACT')
        parts=shlex.split(match[1]);require(len(parts)==1,'BOOTSTRAP_CONTRACT')
        value=parts[0]
        for name,prior in values.items():value=value.replace('$'+name,prior)
        require(not any(c in value for c in ('$','`','\n')),'BOOTSTRAP_CONTRACT')
        values[key]=value
    command=re.search(r'^"\$VLLM" serve (.*?)\s+> ',text.replace('\\\n',''),re.M)
    require(command is not None,'BOOTSTRAP_CONTRACT')
    args=shlex.split('"$VLLM" serve '+command[1])
    for i,arg in enumerate(args):
        for name,value in values.items():arg=arg.replace('$'+name,value)
        require('$' not in arg and '`' not in arg,'BOOTSTRAP_CONTRACT');args[i]=arg
    return {'values':values,'command':args}


def verify_command(command,contract):
    expected=contract['command']
    require(command==expected or (len(command)==len(expected)+1 and command[1:]==expected
            and Path(command[0]).parent==Path(expected[0]).parent
            and re.fullmatch(r'python(?:3(?:\.[0-9]+)?)?',Path(command[0]).name)),'SERVER_COMMAND_IDENTITY')
    return command[command.index('serve')+1:]


def bind_cache(contract,server_environment,environ=None,modules=None):
    env=os.environ if environ is None else environ
    modules=sys.modules if modules is None else modules
    require(not any(x in modules for x in ('huggingface_hub.constants','transformers','vllm')),'CACHE_IMPORT_ORDER')
    home=contract['values']['CACHE'];hub=home+'/hub'
    require(server_environment.get('HF_HOME')==home,'SERVER_CACHE_IDENTITY')
    require(all(server_environment.get(k)=='1' for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')),'SERVER_OFFLINE_REQUIRED')
    for key in ('HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE'):
        require(server_environment.get(key,hub)==hub,'SERVER_CACHE_OVERRIDE')
    require(server_environment.get('HF_ENDPOINT','https://huggingface.co')=='https://huggingface.co','SERVER_ENDPOINT_OVERRIDE')
    for key in CACHE_KEYS:env.pop(key,None)
    env.update(HF_HOME=home,HF_HUB_CACHE=hub,HUGGINGFACE_HUB_CACHE=hub,
               HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',VLLM_LOGGING_LEVEL='ERROR')
    return Path(hub)/('models--'+contract['values']['MODEL'].replace('/','--'))/'snapshots'/contract['values']['REVISION']


def verify_model_identity(requested_model,requested_revision,resolved_model,contract,snapshot):
    values=contract['values']
    require(requested_model==values['MODEL'] and requested_revision==values['REVISION'],'MODEL_REQUEST_IDENTITY')
    require(snapshot.is_dir() and not snapshot.is_symlink() and snapshot.name==values['REVISION'],'CACHED_SNAPSHOT_ABSENT')
    require(Path(resolved_model).is_absolute() and Path(resolved_model).resolve()==snapshot.resolve(),'MODEL_SNAPSHOT_IDENTITY')


def failure_record(error,stage):
    # No exception messages, source lines, arguments, locals or absolute paths.
    frames=[{'module':Path(f.filename).name,'line':f.lineno,'function':f.name}
            for f in traceback.extract_tb(error.__traceback__)[-8:]]
    code=str(error) if type(error) is VerificationFailure and re.fullmatch('[A-Z0-9_]{1,80}',str(error)) else 'EXACT_RUNTIME_CHECK_FAILED'
    return {'schema':'sanctum-serving-runtime-verification/v1','status':'FAIL','stage':stage,
            'code':code,'errorType':type(error).__name__,'frames':frames,'modelInference':'NOT_RUN'}


def process_facts(root,proc=Path('/proc')):
    pid_text=(root/'pids/vllm.pid').read_text().strip()
    require(pid_text.isdigit() and int(pid_text)>1,'SERVER_PID')
    directory=proc/pid_text
    stat=(directory/'stat').read_text();identity=stat.rsplit(')',1)[1].split()[19]
    command=[x.decode() for x in (directory/'cmdline').read_bytes().split(b'\0') if x]
    # Only the cache whitelist leaves this function; all other environment values
    # are ignored and never written to evidence or copied to another process.
    env={}
    for entry in (directory/'environ').read_bytes().split(b'\0'):
        key,sep,value=entry.partition(b'=')
        if sep and key.decode(errors='replace') in CACHE_KEYS:env[key.decode()]=value.decode()
    return pid_text,identity,command,env


def run(base=BASE,proc=Path('/proc'),progress=None):
    stage='BOOTSTRAP_IDENTITY'
    def mark(value):
        nonlocal stage
        stage=value
        if progress:progress(value)
    try:
        contract=launch_contract((base/'runtime/bootstrap-private-lead-vllm.sh').read_text())
        mark('SERVER_IDENTITY')
        root=Path(contract['values']['BASE']);pid,start,command,environment=process_facts(root,proc)
        argv=verify_command(command,contract)
        mark('CACHE_BINDING')
        snapshot=bind_cache(contract,environment)
        require(snapshot.is_dir(),'CACHED_SNAPSHOT_ABSENT')
        sys.path[:0]=[str(base),str(base/'src')]
        mark('EXACT_IMPORTS')
        import verify_exact_runtime as exact
        from common import canonical,digest,strict_json
        from transformers import AutoTokenizer
        from vllm.engine.arg_utils import AsyncEngineArgs
        from vllm.entrypoints.openai.cli_args import make_arg_parser
        from vllm.utils.argparse_utils import FlexibleArgumentParser
        from vllm.sampling_params import SamplingParams,StructuredOutputsParams
        from vllm.v1.structured_output.backend_types import StructuredOutputOptions
        from types import SimpleNamespace
        mark('MODEL_RESOLUTION')
        args=make_arg_parser(FlexibleArgumentParser()).parse_args(argv)
        requested=args.model_tag or args.model;revision=args.revision
        args.model=requested
        engine=AsyncEngineArgs.from_cli_args(args)
        verify_model_identity(requested,revision,engine.model,contract,snapshot)
        config=engine.structured_outputs_config
        if engine.reasoning_parser:config.reasoning_parser=engine.reasoning_parser
        require(config.backend=='auto' and config.disable_any_whitespace is False,'BACKEND_CONFIG_DRIFT')
        mark('TOKENIZER_IDENTITY')
        expected=strict_json((base/'expected-tokenizer.json').read_text())
        for name,sha in expected['files'].items():
            require(name in exact.TOKEN_FILES and exact.sha(snapshot/name)==sha,'TOKENIZER_BYTES_MISMATCH')
        require({'config.json','tokenizer.json','tokenizer_config.json'}<=set(expected['files']),'TOKENIZER_EXPECTATION_INCOMPLETE')
        tokenizer=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True,trust_remote_code=False)
        require(hashlib.sha256(tokenizer.get_chat_template().encode()).hexdigest()==expected['template'],'TEMPLATE_MISMATCH')
        artifact=strict_json((base/'runtime-requests.json').read_text());exact.verify_artifact(artifact)
        mark('BACKEND_RESOLUTION');selected={}
        for label,row in artifact['surfaces'].items():
            params=SamplingParams(structured_outputs=StructuredOutputsParams(json=exact.generation_order(row['request']['schema'])))
            params._validate_structured_outputs(config,tokenizer)
            selected[label]=params.structured_outputs._backend
        resolution={'command_sha256':digest(command),'selection_config':dataclasses.asdict(config),'per_surface_backend':selected,
                    'sampling_params_sha256':exact.sha(Path(importlib.import_module('vllm.sampling_params').__file__)),
                    'cacheBindingVerified':True,'immutableSnapshotVerified':True}
        resolved={'model':requested,'model_revision':revision,'selection_config':dataclasses.asdict(config),
                  'per_surface_backend':selected,'resolution_evidence_sha256':digest(resolution)}
        mark('ENVIRONMENT_INVENTORY')
        observed,_=exact.inventory(snapshot,resolved);observed['artifactDigest']=digest(artifact)
        mark('SCHEMA_AND_TOKEN_VERIFICATION')
        result=exact.run(artifact,observed,snapshot);result['resolutionEvidence']=resolution
        mark('NEGATIVE_COMPILER_CONTROLS');negative=[]
        model=strict_json((snapshot/'config.json').read_text());vocab=model.get('vocab_size',model.get('text_config',{}).get('vocab_size'))
        cfg=SimpleNamespace(structured_outputs_config=config,speculative_config=None)
        for label,row in artifact['surfaces'].items():
            module,cls=exact.BACKENDS[selected[label]]
            backend=getattr(importlib.import_module('vllm.v1.structured_output.'+module),cls)(cfg,tokenizer,vocab)
            try:
                grammar=backend.compile_grammar(StructuredOutputOptions.JSON,exact.generation_wire_json(row['request']['schema']))
                accepted=all(grammar.accept_tokens('invalid',[t]) for t in tokenizer.encode('{}',add_special_tokens=False))
                if accepted:accepted=grammar.accept_tokens('invalid',[tokenizer.eos_token_id])
                refused=False
                try:backend.compile_grammar(StructuredOutputOptions.JSON,'{"type":"INVALID_TYPE"}')
                except Exception:refused=True
                negative.append({'surface':label,'invalidRepresentativeRefused':not accepted,'invalidSchemaRefused':refused})
            finally:backend.destroy()
        result['negativeControls']=negative
        if not all(x['invalidRepresentativeRefused'] and x['invalidSchemaRefused'] for x in negative):
            result.update(status='FAIL',code='NEGATIVE_COMPILER_CONTROL')
        mark('SERVER_RECHECK')
        end_pid,end_start,end_command,end_env=process_facts(root,proc)
        require((pid,start,command,environment)==(end_pid,end_start,end_command,end_env),'SERVER_IDENTITY_CHANGED')
        result.update(stage='COMPLETE',serverIdentityStable=True)
        return result
    except BaseException as error:return failure_record(error,stage)


def main():
    parser=argparse.ArgumentParser();parser.parse_args()
    sys.dont_write_bytecode=True
    # Libraries may log arbitrary messages. Suppress them even at file-descriptor
    # level; output only the bounded structured verification result.
    stdout=os.dup(1);stderr=os.dup(2)
    with open(os.devnull,'w') as sink:
        try:
            sys.stdout.flush();sys.stderr.flush();os.dup2(sink.fileno(),1);os.dup2(sink.fileno(),2)
            result=run()
            sys.stdout.flush();sys.stderr.flush()
        finally:os.dup2(stdout,1);os.dup2(stderr,2);os.close(stdout);os.close(stderr)
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':sys.exit(main())
