#!/usr/bin/env python3
"""Frozen JSON-format baseline/comparison client; no tool execution or service control."""
import argparse
from collections import Counter
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import time

from jsonschema import validators
from referencing import Registry
from referencing.exceptions import NoSuchResource

try:
    from fork.evaluate import Transport, digest, stats
except ModuleNotFoundError:
    from evaluate import Transport, digest, stats


def validator(schema):
    def no_remote(uri):
        raise NoSuchResource(ref=uri)
    cls = validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema, registry=Registry(retrieve=no_remote))


def evaluate(case, code, response):
    expected = case['expected']
    result = {'http_status': code, 'category': None, 'passed': False, 'json_valid': None,
              'schema_valid': None, 'schema_errors': [], 'content': None, 'calls': [],
              'usage': response.get('usage', {}), 'timings': response.get('timings', {})}
    if case['group'] == 'negative':
        result.update(category='expected_request_rejection' if code == expected['http_status'] else 'unexpected_negative_result',
                      passed=code == expected['http_status'])
        return result
    error = response.get('error')
    if code != 200 or error:
        result['category'] = 'structured_output_failed' if isinstance(error, dict) and error.get('type') == 'structured_output_failed' else 'api_error'
        result['error_type'] = error.get('type') if isinstance(error, dict) else None
        return result
    choices = response.get('choices') or []
    if not choices:
        result['category'] = 'missing_choice'
        return result
    choice = choices[0]
    message = choice.get('message') or {}
    result.update(content=message.get('content'), calls=message.get('tool_calls') or [],
                  finish_reason=choice.get('finish_reason'))
    if choice.get('finish_reason') not in ('stop', 'tool_calls'):
        result['category'] = 'incomplete_generation'
        return result
    if expected.get('kind') == 'tool':
        declared = {t['function']['name']:t['function']['parameters'] for t in case['body']['tools']}
        calls = result['calls']
        if response.get('strata_rejected_tool_calls'):
            result['category'] = 'rejected_generated_tool'
            return result
        if not calls:
            result['category'] = 'missing_expected_tool'
            return result
        if len(calls) != 1 or calls[0].get('function', {}).get('name') != expected['tool']:
            result['category'] = 'wrong_tool'
            return result
        function = calls[0]['function']
        try:
            args = json.loads(function.get('arguments', ''))
        except ValueError:
            result['category'] = 'invalid_tool_arguments_json'
            return result
        errors = list(validator(declared[function['name']]).iter_errors(args))
        if errors:
            result['category'] = 'invalid_tool_arguments_schema'
            return result
        # Only these synthetic SELECT-literal cases allow an optional semicolon.
        wanted = expected['arguments']
        same = args == wanted or (set(args) == {'query'} and args['query'] == wanted['query'] + ';')
        result.update(category='tool_call_success' if same else 'wrong_tool_arguments', passed=same)
        return result
    if result['calls']:
        result['category'] = 'unexpected_tool_call'
        return result
    if 'value' in expected and isinstance(expected['value'], str) and not case['body'].get('response_format'):
        ok = (result['content'] or '').strip() == expected['value']
        result.update(category='text_success' if ok else 'wrong_text', passed=ok)
        return result
    try:
        # Reject non-standard NaN/Infinity, which Python otherwise accepts as JSON.
        def invalid_constant(value):
            raise ValueError('non-standard JSON constant')
        value = json.loads(result['content'] or '', parse_constant=invalid_constant)
    except (ValueError, TypeError):
        result.update(category='invalid_json_syntax', json_valid=False)
        return result
    result['json_valid'] = True
    fmt = case['body'].get('response_format')
    if fmt:
        schema = {'type':'object'} if fmt['type'] == 'json_object' else fmt['json_schema']['schema']
        errors = sorted(validator(schema).iter_errors(value), key=lambda e: str(list(e.absolute_path)))
        result['schema_valid'] = not errors
        result['schema_errors'] = [{'path':list(e.absolute_path), 'validator':e.validator, 'message':e.message} for e in errors]
        if errors:
            result['category'] = 'schema_violation'
            return result
    wanted = expected.get('value', expected.get('text_json_value'))
    if wanted is not None and value != wanted:
        result['category'] = 'wrong_value'
        return result
    result.update(category='json_success', passed=True)
    return result


def summarize(rows):
    groups = {}
    for group in sorted({r['group'] for r in rows if not r['warmup']}):
        selected = [r for r in rows if r['group'] == group and not r['warmup']]
        groups[group] = {'requests':len(selected), 'passed':sum(r['evaluation']['passed'] for r in selected),
                         'categories':dict(Counter(r['evaluation']['category'] for r in selected))}
    perf = {}
    for name in sorted({r['case_id'] for r in rows if r['group']=='performance'}):
        selected = [r for r in rows if r['case_id']==name and not r['warmup']]
        successful = [r for r in selected if r['evaluation']['passed']]
        perf[name] = {'requests':len(selected), 'successful':len(successful),
            **{k:stats([r['metrics'].get(k) for r in successful]) for k in
               ['seconds','decode_tokens_per_second','completion_tokens','prompt_tokens','cached_tokens','draft_acceptance']}}
    return {'groups':groups,'performance':perf}


def run(args):
    suite = json.loads(args.suite.read_text())
    if args.out.exists():
        raise SystemExit('Use a new output directory; existing evidence is never overwritten')
    t = Transport(args)
    before = t.status()
    if not before.get('loaded') or before.get('engine') != args.expect_engine:
        raise SystemExit('Expected loaded engine '+args.expect_engine+'; got '+str(before.get('engine')))
    if (before.get('activity') or {}).get('in_flight',0):
        raise SystemExit('Service busy; benchmark requires an idle start')
    args.out.mkdir(parents=True)
    meta = {'label':args.label,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'suite_sha256':digest(suite),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'transport_sha256':hashlib.sha256((Path(__file__).parent/'evaluate.py').read_bytes()).hexdigest(),
            'jsonschema_version':importlib.metadata.version('jsonschema'),
            'status_before':before,'model':before['model'],'performance_repeats':args.repeats,
            'scope':suite['scope'],'selection':suite['selection'],
            'configuration_attestation':args.config_note or 'Launch flags and model file hashes not independently attested by API.',
            'timing_scope':'Non-streaming HTTP total, includes validation/buffering and network. No TTFT claim. Engine decode timing separately. No retries.'}
    (args.out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    (args.out/'suite.json').write_text(json.dumps(suite,indent=2)+'\n')
    jobs = [(c,0,False) for c in suite['cases'] if c['group']!='performance']
    perf = [c for c in suite['cases'] if c['group']=='performance']
    jobs += [(c,-1,True) for c in perf]
    repeated = [(c,i,False) for i in range(args.repeats) for c in perf]
    random.Random(20261106).shuffle(repeated)
    jobs += repeated
    rows=[]
    with (args.out/'requests.jsonl').open('w') as out:
        for case,repeat,warmup in jobs:
            body={**case['body'],'model':before['model'],'stream':False}
            row={'case_id':case['id'],'group':case['group'],'repeat':repeat,'warmup':warmup,
                 'request':body,'request_sha256':digest(body)}
            started=time.perf_counter();code=None
            try:
                with t.open('/v1/chat/completions',body) as (code,response):
                    data=json.load(response)
                if not isinstance(data,dict):
                    data={'error':{'type':'invalid_response_envelope'}}
                grading=evaluate(case,code,data)
            except Exception as error:
                data={'error':{'type':type(error).__name__}}
                grading=evaluate(case,code,data)
            elapsed=time.perf_counter()-started
            timing=grading['timings'];usage=grading['usage'];draft=timing.get('draft_n') or 0
            row.update(http_status=code,response=data,evaluation=grading,metrics={
                'seconds':elapsed,'decode_tokens_per_second':timing.get('predicted_per_second'),
                'completion_tokens':usage.get('completion_tokens'),'prompt_tokens':usage.get('prompt_tokens'),
                'cached_tokens':usage.get('prompt_tokens_details',{}).get('cached_tokens'),
                'draft_acceptance':timing.get('draft_n_accepted',0)/draft if draft else None})
            rows.append(row);out.write(json.dumps(row)+'\n');out.flush()
            print(json.dumps({'case':case['id'],'repeat':repeat,'warmup':warmup,'http':code,
                              'seconds':round(elapsed,3),'category':grading['category'],'passed':grading['passed']}),flush=True)
    after=t.status();meta.update(status_after=after,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        identity_stable=all(before.get(k)==after.get(k) for k in ['engine','model','context','concurrency']),
        activity_delta=(after.get('activity') or {}).get('requests',0)-(before.get('activity') or {}).get('requests',0),measured_requests=len(rows))
    (args.out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    summary=summarize(rows);(args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


def compare(args):
    def load(folder):
        return json.loads((folder/'metadata.json').read_text()),[json.loads(s) for s in (folder/'requests.jsonl').read_text().splitlines()]
    a,ar=load(args.baseline);b,br=load(args.candidate)
    for key in ['suite_sha256','model','jsonschema_version']:
        if a[key]!=b[key]:raise SystemExit('Comparison refused: mismatch in '+key)
    index=lambda rows:{(r['case_id'],r['repeat'],r['warmup']):r for r in rows}
    ai,bi=index(ar),index(br)
    if set(ai)!=set(bi) or any(ai[k]['request_sha256']!=bi[k]['request_sha256'] for k in ai):
        raise SystemExit('Comparison refused: request bodies or repetitions differ')
    summaries=[summarize(ar),summarize(br)];changes=[]
    for key,row in ai.items():
        other=bi[key]
        if row['warmup']:continue
        get=lambda r:{k:r['evaluation'].get(k) for k in ['category','content','calls','finish_reason','schema_errors']}
        if get(row)!=get(other):changes.append({'case':row['case_id'],'repeat':row['repeat'],
             'baseline_category':row['evaluation']['category'],'candidate_category':other['evaluation']['category']})
    perf={}
    for name,base in summaries[0]['performance'].items():
        new=summaries[1]['performance'][name];ratios={}
        for metric in ['seconds','decode_tokens_per_second']:
            x,y=base[metric]['median'],new[metric]['median']
            ratios[metric]=None if not x or y is None else 100*(y/x-1)
        perf[name]={'baseline':base,'candidate':new,'median_change_percent':ratios}
    report={'baseline_engine':a['status_before']['engine'],'candidate_engine':b['status_before']['engine'],
            'reported_configuration_equal':{k:a['status_before'].get(k)==b['status_before'].get(k) for k in ['context','concurrency']},
            'baseline':summaries[0]['groups'],'candidate':summaries[1]['groups'],'changes':changes,'performance':perf,
            'limits':'HTTP errors and invalid successful JSON are distinct. Compare successful requests only for speed; mismatched output/cache/draft/load is not a causal patch benchmark. No /v1/responses API, streaming, cold-cache or other-model claim.'}
    args.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('--url',required=True);r.add_argument('--label',required=True)
    r.add_argument('--expect-engine',required=True);r.add_argument('--out',type=Path,required=True)
    r.add_argument('--suite',type=Path,default=Path(__file__).parent/'evaluation/json/suite.json')
    r.add_argument('--repeats',type=int,default=10);r.add_argument('--timeout',type=float,default=180)
    r.add_argument('--api-key-env');r.add_argument('--tailscale',default='tailscale');r.add_argument('--tailscale-socket');r.add_argument('--config-note')
    c=sub.add_parser('compare');c.add_argument('--baseline',type=Path,required=True);c.add_argument('--candidate',type=Path,required=True);c.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.command=='run' and args.repeats<1:p.error('--repeats must be positive')
    (run if args.command=='run' else compare)(args)


if __name__=='__main__':main()
