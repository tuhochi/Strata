#!/usr/bin/env python3
"""Run synthetic real-model acceptance checks against the installed fork server."""
import argparse
import json
import os
import pathlib
import time
import urllib.request


def run(url, output, tokenizer=None, api_key_env=None):
    headers = {'Content-Type': 'application/json'}
    if api_key_env:
        headers['Authorization'] = 'Bearer ' + os.environ[api_key_env]
        headers['x-api-key'] = os.environ[api_key_env]
    def request(path, body=None):
        req = urllib.request.Request(url.rstrip('/') + path, None if body is None else json.dumps(body).encode(), headers)
        return urllib.request.urlopen(req, timeout=300)
    with request('/v1/status') as response:
        status = json.load(response)
    assert status['loaded'], 'A real model must be loaded'
    assert status['engine'], 'Mock engines do not qualify as hardware evidence'
    assert status['structured_output']['constrained_decoding'], 'Engine token masks are unavailable'
    model = status['model']
    function = {'name': 'sql_query', 'description': 'Run a read-only SQL query.',
                'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}
    prompt = 'Call mcp__local__sql_query with query SELECT 1. Use a real tool call, no explanation.'
    common = {'model': model, 'max_tokens': 96, 'temperature': 0, 'reasoning_effort': 'none'}
    results = []
    def record(name, names, started):
        assert names and set(names) == {'sql_query'}, (name, names)
        row = {'case': name, 'tool_names': names, 'seconds': round(time.monotonic() - started, 3), 'passed': True}
        results.append(row)
        print(json.dumps(row), flush=True)
    started = time.monotonic()
    with request('/v1/chat/completions', {**common, 'messages': [{'role': 'user', 'content': prompt}],
                 'tools': [{'type': 'function', 'function': function}]}) as response:
        data = json.load(response)
    record('chat_undeclared_prefix', [c['function']['name'] for c in data['choices'][0]['message'].get('tool_calls', [])], started)
    started = time.monotonic()
    names = []
    with request('/v1/chat/completions', {**common, 'messages': [{'role': 'user', 'content': prompt}],
                 'tools': [{'type': 'function', 'function': function}], 'stream': True}) as response:
        for line in response:
            if not line.startswith(b'data:') or line.strip() == b'data: [DONE]':
                continue
            event = json.loads(line[5:])
            for choice in event.get('choices', []):
                delta = choice.get('delta', {})
                assert '<tool_call' not in delta.get('content', ''), 'Raw tool-call text escaped in stream'
                for call in delta.get('tool_calls', []):
                    name = call.get('function', {}).get('name')
                    if name:
                        names.append(name)
    record('chat_stream_undeclared_prefix', names, started)
    started = time.monotonic()
    with request('/v1/responses', {**common, 'input': prompt, 'max_output_tokens': 96,
                 'tools': [{'type': 'function', **function}]}) as response:
        data = json.load(response)
    record('responses_undeclared_prefix', [c['name'] for c in data.get('output', []) if c.get('type') == 'function_call'], started)
    started = time.monotonic()
    with request('/v1/messages', {**common, 'messages': [{'role': 'user', 'content': prompt}],
                 'tools': [{'name': function['name'], 'description': function['description'], 'input_schema': function['parameters']}]}) as response:
        data = json.load(response)
    record('anthropic_undeclared_prefix', [c['name'] for c in data.get('content', []) if c.get('type') == 'tool_use'], started)
    if tokenizer:
        vocab = json.loads((tokenizer / 'vocab.json').read_text())
        forbidden = vocab['m']
        other = {**function, 'name': 'search_text'}
        started = time.monotonic()
        with request('/v1/chat/completions', {**common, 'max_tokens': 1,
                     'messages': [{'role': 'user', 'content': 'Call mcp__local__sql_query.'}],
                     'tools': [{'type': 'function', 'function': f} for f in [function, other]],
                     'tool_choice': 'required', 'logit_bias': {str(forbidden): 100}, 'logprobs': True, 'top_logprobs': 5}) as response:
            data = json.load(response)
        entries = data['choices'][0].get('logprobs', {}).get('content', [])
        assert entries, 'No sampled-token evidence for forced name'
        token = entries[0]['token']
        assert token and token != 'm' and any(n.startswith(token.strip()) for n in ['sql_query', 'search_text']), token
        results.append({'case': 'forbidden_name_head_bias_100', 'sampled_token': token,
                        'seconds': round(time.monotonic() - started, 3), 'passed': True})
        print(json.dumps(results[-1]), flush=True)
    report = {'engine': status['engine'], 'model': model, 'context': status['context'],
              'scope': 'Actual Metal model, Qwen XML names, current speculative configuration; no speed claim', 'checks': results}
    output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--tokenizer', type=pathlib.Path)
    parser.add_argument('--api-key-env')
    args = parser.parse_args()
    run(args.url, args.out, args.tokenizer, args.api_key_env)
