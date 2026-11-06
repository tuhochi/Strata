#!/usr/bin/env python3
"""Record synthetic API evidence; never execute tools or change server configuration."""
import argparse
import contextlib
import datetime
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Transport:
    def __init__(self, args):
        self.url, self.timeout = args.url.rstrip('/'), args.timeout
        self.nc, self.socket = args.tailscale, args.tailscale_socket
        self.headers = {'Content-Type': 'application/json'}
        if args.api_key_env:
            self.headers['Authorization'] = 'Bearer ' + os.environ[args.api_key_env]

    @contextlib.contextmanager
    def open(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        if not self.socket:
            req = urllib.request.Request(self.url + path, data=data, headers=self.headers)
            try:
                response = urllib.request.urlopen(req, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                yield response.status, response
            return
        url = urllib.parse.urlsplit(self.url)
        if url.scheme != 'http' or url.path not in ('', '/'):
            raise ValueError('Tailscale nc transport requires an HTTP origin without a path')
        proc = subprocess.Popen([self.nc, '--socket=' + self.socket, 'nc', url.hostname, str(url.port or 80)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        timer = threading.Timer(self.timeout, proc.kill)
        timer.start()
        class Socket:
            def makefile(self, *args, **kwargs):
                return proc.stdout
        try:
            headers = {**self.headers, 'Host': url.netloc, 'Connection': 'close'}
            if data is not None:
                headers['Content-Length'] = str(len(data))
            wire = ('POST' if data is not None else 'GET') + ' ' + path + ' HTTP/1.1\r\n'
            wire += ''.join(k + ': ' + v + '\r\n' for k, v in headers.items()) + '\r\n'
            proc.stdin.write(wire.encode() + (data or b''))
            proc.stdin.flush()  # nc must keep stdin open while receiving the response.
            response = http.client.HTTPResponse(Socket())
            response.begin()
            try:
                yield response.status, response
            finally:
                response.close()
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.terminate()
            proc.wait()
            proc.stdin.close()
            proc.stdout.close()

    def status(self):
        with self.open('/v1/status') as (code, response):
            if code != 200:
                raise RuntimeError('Status HTTP ' + str(code))
            raw = json.load(response)
        # Do not save endpoint addresses, paths, credentials or unrelated request history.
        return {k: raw.get(k) for k in ['service', 'model', 'loaded', 'engine', 'structured_output',
                                       'context', 'concurrency', 'machine', 'activity']}


def assemble(events):
    content, reasoning, calls, rejected, usage, timings, finish, errors = [], [], {}, [], {}, {}, None, []
    for event in events:
        if 'error' in event:
            errors.append(event['error'])
        rejected.extend(event.get('strata_rejected_tool_calls', []))
        usage = event.get('usage') or usage
        timings = event.get('timings') or timings
        for choice in event.get('choices', []):
            finish = choice.get('finish_reason') or finish
            delta = choice.get('delta', choice.get('message', {}))
            content.append(delta.get('content') or '')
            reasoning.append(delta.get('reasoning_content') or '')
            for call in delta.get('tool_calls', []):
                slot = calls.setdefault(call.get('index', len(calls)), {'name': '', 'arguments': ''})
                function = call.get('function', {})
                slot['name'] += function.get('name') or ''
                slot['arguments'] += function.get('arguments') or ''
    return {'content': ''.join(content), 'reasoning': ''.join(reasoning), 'calls': list(calls.values()),
            'rejected': rejected, 'usage': usage, 'timings': timings, 'finish_reason': finish, 'errors': errors}


def grade(case, result, http_status=200):
    allowed = {t['function']['name']: t['function']['parameters'] for t in case['body'].get('tools', [])}
    raw_names = re.findall(r'<function=([^>\s]+)>', result['content'])
    unknown = sorted({c['name'] for c in result['calls'] if c['name'] not in allowed} |
                     {c['name'] for c in result['rejected'] if c.get('reason') == 'undeclared'} |
                     {n for n in raw_names if n not in allowed})
    raw_markup = '<tool_call>' in result['content'] or bool(raw_names)
    invalid_args = []
    arguments = []
    for call in result['calls']:
        try:
            value = json.loads(call['arguments'])
            schema = allowed.get(call['name'], {})
            valid = isinstance(value, dict) and all(k in value for k in schema.get('required', []))
            valid = valid and all(isinstance(v, str) for v in value.values())
            valid = valid and (schema.get('additionalProperties', True) or set(value) <= set(schema.get('properties', {})))
            if not valid:
                invalid_args.append(call['name'])
            arguments.append(value)
        except (ValueError, AttributeError):
            invalid_args.append(call['name'])
            arguments.append(None)
    expected = case['expected']
    if 'tool' in expected:
        task_ok = len(result['calls']) == 1 and result['calls'][0]['name'] == expected['tool'] and arguments == [expected['arguments']]
    else:
        task_ok = not result['calls'] and result['content'].strip() == expected.get('text')
    completed = http_status == 200 and not result['errors'] and result['finish_reason'] in ('stop', 'tool_calls')
    return {'unknown_tool_names': unknown, 'unknown_tool_failure': bool(unknown),
            'raw_tool_markup': raw_markup, 'invalid_arguments': invalid_args,
            'missing_expected_call': 'tool' in expected and not result['calls'],
            'completed': completed, 'task_passed': bool(task_ok and completed and not unknown and not invalid_args and not raw_markup)}


def quantile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * q) - 1)] if ordered else None


def stats(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return {'n': len(values), 'median': statistics.median(values) if values else None,
            'p95': quantile(values, .95), 'min': min(values) if values else None, 'max': max(values) if values else None}


def summarize(rows):
    groups = {}
    for group in sorted({r['group'] for r in rows if not r['warmup']}):
        items = [r for r in rows if r['group'] == group and not r['warmup']]
        groups[group] = {'requests': len(items), 'unknown_tool_failures': sum(r['grade']['unknown_tool_failure'] for r in items),
                         'raw_tool_markup': sum(r['grade']['raw_tool_markup'] for r in items),
                         'invalid_arguments': sum(bool(r['grade']['invalid_arguments']) for r in items),
                         'incomplete_or_error': sum(not r['grade']['completed'] for r in items),
                         'task_passed': sum(r['grade']['task_passed'] for r in items)}
    performance = {}
    for case_id in sorted({r['case_id'] for r in rows if r['group'] == 'performance'}):
        items = [r for r in rows if r['case_id'] == case_id and not r['warmup']]
        good = [r for r in items if r['grade']['completed']]
        performance[case_id] = {'requests': len(items), 'completed': len(good), 'task_passed': sum(r['grade']['task_passed'] for r in items),
            **{k: stats([r['metrics'].get(k) for r in good]) for k in ['seconds', 'ttft_seconds', 'decode_tokens_per_second', 'prompt_tokens', 'completion_tokens', 'cached_tokens', 'draft_acceptance']}}
    return {'groups': groups, 'performance': performance}


def run(args):
    suite = json.loads(args.suite.read_text())
    if args.out.exists():
        raise SystemExit('Output directory already exists; use a new run directory')
    args.out.mkdir(parents=True)
    transport = Transport(args)
    before = transport.status()
    if not before.get('loaded') or not before.get('engine'):
        raise SystemExit('A real loaded model is required')
    if args.expect_engine and before['engine'] != args.expect_engine:
        raise SystemExit('Unexpected engine: ' + str(before['engine']))
    if (before.get('activity') or {}).get('in_flight', 0):
        raise SystemExit('Server is busy; run this serial benchmark when idle')
    metadata = {'label': args.label, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'suite_sha256': digest(suite), 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'suite_note': suite['sampling_note'], 'model': before['model'], 'status_before': before,
                'sampling': 'exact body per request; temperature 0, seed 123, reasoning none; serial; no logit bias',
                'performance_repeats': args.repeats, 'latency_scope': 'client includes transport; server decode timing separately; TTFT includes content, reasoning or tool output, excludes empty role/progress events',
                'configuration_attestation': args.config_note or 'Owner must confirm identical model files, tokenizer, launch flags, MTP, server source and hardware for a causal comparison.'}
    (args.out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (args.out / 'suite.json').write_text(json.dumps(suite, indent=2) + '\n')
    jobs = [(c, 0, False) for c in suite['cases'] if c['group'] != 'performance']
    perf = [c for c in suite['cases'] if c['group'] == 'performance']
    jobs += [(c, -1, True) for c in perf]
    repeated = [(c, i, False) for i in range(args.repeats) for c in perf]
    random.Random(20261106).shuffle(repeated)
    jobs += repeated
    rows = []
    with (args.out / 'requests.jsonl').open('w') as output:
        for case, repeat, warmup in jobs:
            body = {**case['body'], 'model': before['model'], 'stream': True, 'stream_options': {'include_usage': True}}
            row = {'case_id': case['id'], 'group': case['group'], 'repeat': repeat, 'warmup': warmup,
                   'request': body, 'request_sha256': digest(body)}
            events, first, done, code = [], None, False, None
            started = time.perf_counter()
            try:
                with transport.open('/v1/chat/completions', body) as (code, response):
                    if code != 200:
                        events.append({'error': response.read().decode(errors='replace')})
                    else:
                        for line in response:
                            if not line.startswith(b'data:'):
                                continue
                            payload = line[5:].strip()
                            if payload == b'[DONE]':
                                done = True
                                break
                            event = json.loads(payload)
                            events.append(event)
                            if first is None:
                                for choice in event.get('choices', []):
                                    delta = choice.get('delta', {})
                                    if delta.get('content') or delta.get('reasoning_content') or delta.get('tool_calls'):
                                        first = time.perf_counter() - started
            except Exception as error:
                # Preserve failure as a measured outcome. Never retry silently.
                events.append({'error': type(error).__name__})
            elapsed = time.perf_counter() - started
            result = assemble(events)
            if code == 200 and not done:
                result['errors'].append('missing SSE DONE')
            timing, usage = result['timings'], result['usage']
            draft = timing.get('draft_n') or 0
            row.update(http_status=code, sse_done=done, response_events=events, result=result,
                       grade=grade(case, result, code), metrics={'seconds': elapsed, 'ttft_seconds': first,
                       'decode_tokens_per_second': timing.get('predicted_per_second'), 'prompt_tokens': usage.get('prompt_tokens'),
                       'completion_tokens': usage.get('completion_tokens'), 'cached_tokens': usage.get('prompt_tokens_details', {}).get('cached_tokens'),
                       'draft_acceptance': timing.get('draft_n_accepted', 0) / draft if draft else None})
            rows.append(row)
            output.write(json.dumps(row) + '\n')
            output.flush()
            print(json.dumps({'case': case['id'], 'repeat': repeat, 'warmup': warmup, 'seconds': round(elapsed, 3), **row['grade']}), flush=True)
    metadata['status_after'] = transport.status()
    metadata['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata['identity_stable'] = all(before.get(k) == metadata['status_after'].get(k) for k in ['model', 'engine', 'context', 'concurrency'])
    metadata['activity_delta'] = (metadata['status_after'].get('activity') or {}).get('requests', 0) - (before.get('activity') or {}).get('requests', 0)
    metadata['measured_requests'] = len(rows)
    (args.out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    summary = summarize(rows)
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


def compare(args):
    dirs = [args.baseline, args.candidate]
    meta = [json.loads((d / 'metadata.json').read_text()) for d in dirs]
    if meta[0]['suite_sha256'] != meta[1]['suite_sha256'] or meta[0]['model'] != meta[1]['model']:
        raise SystemExit('Suite or model differs; comparison refused')
    rows = [[json.loads(line) for line in (d / 'requests.jsonl').read_text().splitlines()] for d in dirs]
    keys = lambda rs: {(r['case_id'], r['repeat'], r['warmup']): r['request_sha256'] for r in rs}
    if keys(rows[0]) != keys(rows[1]):
        raise SystemExit('Requests or repeat counts differ; comparison refused')
    summaries = [summarize(r) for r in rows]
    same = {k: meta[0]['status_before'].get(k) == meta[1]['status_before'].get(k) for k in ['context', 'concurrency']}
    changed = []
    for a, b in zip(rows[0], rows[1]):
        if a['group'] not in ('control', 'performance') or a['warmup']:
            continue
        view = lambda r: {k: r['result'][k] for k in ['content', 'reasoning', 'calls', 'finish_reason']}
        if view(a) != view(b):
            changed.append({'case': a['case_id'], 'repeat': a['repeat']})
    perf = {}
    for name, base in summaries[0]['performance'].items():
        new = summaries[1]['performance'][name]
        ratios = {}
        for metric in ['seconds', 'ttft_seconds', 'decode_tokens_per_second']:
            a, b = base[metric]['median'], new[metric]['median']
            ratios[metric] = None if not a or b is None else 100 * (b / a - 1)
        perf[name] = {'baseline': base, 'candidate': new, 'median_change_percent': ratios}
    result = {'baseline_engine': meta[0]['status_before']['engine'], 'candidate_engine': meta[1]['status_before']['engine'],
              'reported_configuration_equal': same, 'baseline': summaries[0]['groups'], 'candidate': summaries[1]['groups'],
              'control_or_performance_output_changes': changed, 'performance': perf,
              'limits': 'No automatic no-regression verdict. Verify launch flags, file hashes, cache_n, token counts, load, warm/cold state and variability. Repeat same-day A/B/A; ten deterministic stress failures are not production incidence. Other API dialects and reasoning configurations require separate runs.'}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run')
    r.add_argument('--url', required=True)
    r.add_argument('--label', required=True)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--suite', type=Path, default=Path(__file__).parent / 'evaluation/suite.json')
    r.add_argument('--repeats', type=int, default=10)
    r.add_argument('--timeout', type=float, default=180)
    r.add_argument('--expect-engine')
    r.add_argument('--config-note')
    r.add_argument('--api-key-env')
    r.add_argument('--tailscale-socket')
    r.add_argument('--tailscale', default='tailscale')
    c = sub.add_parser('compare')
    c.add_argument('--baseline', type=Path, required=True)
    c.add_argument('--candidate', type=Path, required=True)
    c.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'run' and args.repeats < 1:
        p.error('--repeats must be positive')
    (run if args.command == 'run' else compare)(args)


if __name__ == '__main__':
    main()
