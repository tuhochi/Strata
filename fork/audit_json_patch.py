#!/usr/bin/env python3
"""CPU-only probes against a specified checkout; never start a model or server."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

PROBE = r'''
import contextlib,io,json,importlib.metadata,subprocess
from types import SimpleNamespace
from unittest.mock import patch
from serve import constrain as c,structured
from serve.server import ByteTokenizer,Service

tok=ByteTokenizer();stop=set(tok.encode('<|im_end|>',parse_special=True));v=c.Vocab(tok,stop)
schema={'type':'object','properties':{'values':{'type':'array','items':{'type':'integer'},'minItems':3,'maxItems':3,'uniqueItems':True}},'required':['values'],'additionalProperties':False}
fmt={'type':'json_schema','json_schema':{'name':'audit','strict':True,'schema':schema}}
report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'llguidance_version':importlib.metadata.version('llguidance'),'execution':'CPU library and service-method calls only; no model or HTTP server'}
try:
    c.Constraint(v,c.grammar(fmt,False,v),armed=True)
    report['uniqueItems_compilation']={'accepted':True}
except Exception as error:
    report['uniqueItems_compilation']={'accepted':False,'error':str(error)}
svc=Service.__new__(Service);svc.engine=SimpleNamespace(supports_mask=True);svc.tok=tok;svc.stop_ids=stop;svc.family='qwen';svc._llg_vocab=v
with contextlib.redirect_stdout(io.StringIO()) as log:
    sampling=svc._with_constraint({'response_format':fmt},None,False)
report['unsupported_schema_server_gate']={'constraint_present':c.KEY in sampling,'log':log.getvalue().strip()}
no_unique=json.loads(json.dumps(fmt));del no_unique['json_schema']['schema']['properties']['values']['uniqueItems']
check=c.Constraint(v,c.grammar(no_unique,False,v),armed=True)
for token in b'{"values":[1,1':
    assert c.Constraint.allowed(check.mask(),token)
    check.feed(token)
report['supported_minItems_control']={'early_closing_bracket_allowed':bool(c.Constraint.allowed(check.mask(),ord(']')))}
with patch.object(structured,'_jsonschema',False),contextlib.redirect_stdout(io.StringIO()):
    _,post=structured.prepare_format(fmt,[{'role':'user','content':'synthetic test'}])
    try:
        text=structured.validated_json('{"values":[1,1]}',post,'stop')
        report['without_postvalidator_dependency']={'schema_invalid_object_accepted':True,'returned':text}
    except structured.StructuredOutputError as error:
        report['without_postvalidator_dependency']={'schema_invalid_object_accepted':False,'error':str(error)}
with patch.object(structured,'_jsonschema',None),contextlib.redirect_stdout(io.StringIO()):
    _,post=structured.prepare_format(fmt,[{'role':'user','content':'synthetic test'}])
    try:
        structured.validated_json('{"values":[1,1]}',post,'stop')
        report['with_postvalidator_dependency']={'schema_invalid_object_rejected':False}
    except structured.StructuredOutputError as error:
        report['with_postvalidator_dependency']={'schema_invalid_object_rejected':True,'error':str(error)}
report['fork_guard_present']=hasattr(c,'ToolNameConstraint')
report['mask_widths']=[]
for size in [262,287,288,289,319,320,321,352]:
    class Padded(ByteTokenizer):
        n_vocab=size
        types=[1]*256+[3]*6+[0]*(size-262)
        def token_bytes(self,i):
            return bytes([i]) if i<256 else self.SPECIALS[i-256].encode() if i<262 else b''
    pv=c.Vocab(Padded(),stop)
    inner=c.Constraint(pv,c.grammar({'type':'json_object'},True,pv),armed=True)
    mask=inner.mask()
    row={'vocab_tokens':size,'schema_mask_bytes':len(mask),'rounded_vocab_bytes':4*((size+31)//32)}
    if report['fork_guard_present']:
        guard=c.ToolNameConstraint(pv,['sql_query'],inner=inner)
        row['guard_mask_bytes']=len(guard._bits(guard.state))
        try:
            guard.reply()
            row['composition_succeeds']=True
        except Exception as error:
            row.update(composition_succeeds=False,error=str(error))
    report['mask_widths'].append(row)
print(json.dumps(report,indent=2))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']}
    env.update(STRATA_TOOL_MASK='0',STRATA_TOOL_NAME_ENUM='0',STRATA_TOOL_MASK_STRICT='0')
    result=subprocess.run([sys.executable,'-c',PROBE],cwd=args.source,env=env,capture_output=True,text=True,check=True)
    report=json.loads(result.stdout)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(args.out.name,report['source_commit'][:8],
          'uniqueItems supported:',report['uniqueItems_compilation']['accepted'],
          'unsupported schema mask active:',report['unsupported_schema_server_gate']['constraint_present'],
          'fork guard:',report['fork_guard_present'])


if __name__=='__main__':main()
