"""Offline checks for evidence classification, streaming assembly and comparison integrity."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from fork.evaluate import assemble, compare, grade, summarize, public_status

TOOL = {'type': 'function', 'function': {'name': 'sql_query', 'parameters': {
    'type': 'object', 'properties': {'query': {'type': 'string'}},
    'required': ['query'], 'additionalProperties': False}}}
CASE = {'body': {'tools': [TOOL]}, 'expected': {'tool': 'sql_query', 'arguments': {'query': 'SELECT 1'}}}


class Evidence(unittest.TestCase):
    def result(self, calls=None, content='', rejected=None):
        return {'content': content, 'reasoning': '', 'calls': calls or [], 'rejected': rejected or [],
                'usage': {}, 'timings': {}, 'finish_reason': 'stop', 'errors': []}

    def test_public_metadata_excludes_nested_identifiers_and_private_fields(self):
        raw = {'engine': 'test-engine', 'model': 'test-model', 'serial_number': 'PRIVATE-SERIAL',
               'hostname': 'PRIVATE-HOST', 'model_path': '/Users/private/model',
               'machine': {'serial': 'PRIVATE-SERIAL', 'hardware_uuid': 'PRIVATE-UUID',
                           'gpu': {'name': 'Apple M1 Ultra', 'uuid': 'PRIVATE-UUID', 'serial': 'PRIVATE-SERIAL'},
                           'ram': {'total_gib': 128, 'owner': 'PRIVATE-OWNER'}},
               'context': {'native': 262144, 'hostname': 'PRIVATE-HOST'},
               'activity': {'requests': 10, 'client_ip': 'PRIVATE-IP'},
               'structured_output': {'constrained_decoding': True, 'api_key': 'PRIVATE-KEY'}}
        public = public_status(raw)
        self.assertNotIn('PRIVATE-', json.dumps(public))
        self.assertNotIn('/Users/', json.dumps(public))
        self.assertEqual(public['machine']['gpu'], {'name': 'Apple M1 Ultra'})
        self.assertEqual(public['machine']['ram'], {'total_gib': 128})
        self.assertEqual(public['activity'], {'requests': 10})
        self.assertEqual(public['context'], {'native': 262144})

    def test_fragmented_sse_tool_is_reassembled_before_grading(self):
        events = [ {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'name': 'sql_', 'arguments': '{"query":'}}]}}]},
                   {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'name': 'query', 'arguments': '"SELECT 1"}'}}]}}]},
                   {'choices': [{'delta': {}, 'finish_reason': 'tool_calls'}], 'usage': {'completion_tokens': 28}}]
        result = assemble(events)
        self.assertTrue(grade(CASE, result)['task_passed'])
        self.assertEqual(result['usage']['completion_tokens'], 28)

    def test_parser_rejected_call_counts_even_when_not_in_tool_calls(self):
        result = self.result(content='<tool_call>\n<function=sql_queri>\n',
                             rejected=[{'name': 'sql_queri', 'reason': 'undeclared'}])
        observed = grade(CASE, result)
        self.assertEqual(observed['unknown_tool_names'], ['sql_queri'])
        self.assertTrue(observed['raw_tool_markup'])
        self.assertFalse(observed['task_passed'])

    def test_missing_tool_is_task_failure_not_unknown_tool(self):
        observed = grade(CASE, self.result(content='I cannot do that.'))
        self.assertFalse(observed['unknown_tool_failure'])
        self.assertTrue(observed['missing_expected_call'])
        self.assertFalse(observed['task_passed'])

    def test_arguments_and_http_errors_do_not_pass(self):
        result = self.result(calls=[{'name': 'sql_query', 'arguments': '{"query": 1}'}])
        self.assertEqual(grade(CASE, result)['invalid_arguments'], ['sql_query'])
        result = self.result(calls=[{'name': 'sql_query', 'arguments': '{"query":"SELECT 1"}'}])
        self.assertFalse(grade(CASE, result, 503)['completed'])
        result['finish_reason'] = 'length'
        self.assertFalse(grade(CASE, result)['task_passed'])

    def test_valid_but_wrong_tool_is_distinct_from_unknown_name(self):
        case = {'body': {'tools': [TOOL, {'type': 'function', 'function': {
            'name': 'search_text', 'parameters': TOOL['function']['parameters']}}]}, 'expected': CASE['expected']}
        result = self.result(calls=[{'name': 'search_text', 'arguments': '{"query":"SELECT 1"}'}])
        observed = grade(case, result)
        self.assertFalse(observed['unknown_tool_failure'])
        self.assertFalse(observed['task_passed'])

    def test_warmup_and_failed_requests_do_not_inflate_speed(self):
        good = {'case_id': 'perf', 'group': 'performance', 'warmup': False,
                'grade': grade(CASE, self.result(calls=[{'name': 'sql_query', 'arguments': '{"query":"SELECT 1"}'}])),
                'metrics': {'decode_tokens_per_second': 50}}
        bad = {**good, 'grade': {**good['grade'], 'completed': False, 'task_passed': False},
               'metrics': {'decode_tokens_per_second': 1000}}
        warm = {**good, 'warmup': True, 'metrics': {'decode_tokens_per_second': 2000}}
        report = summarize([good, bad, warm])['performance']['perf']
        self.assertEqual((report['requests'], report['completed']), (2, 1))
        self.assertEqual(report['decode_tokens_per_second']['median'], 50)

    def test_comparison_refuses_different_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label, sha in [('a', 'first'), ('b', 'different')]:
                d = root / label
                d.mkdir()
                (d / 'metadata.json').write_text(json.dumps({'suite_sha256': 'same', 'model': 'same'}))
                (d / 'requests.jsonl').write_text(json.dumps({'case_id': 'x', 'repeat': 0, 'warmup': False,
                                                             'request_sha256': sha})+'\n')
            args = argparse.Namespace(baseline=root/'a', candidate=root/'b', out=root/'comparison.json')
            with self.assertRaisesRegex(SystemExit, 'Requests or repeat counts differ'):
                with contextlib.redirect_stdout(io.StringIO()):
                    compare(args)
            self.assertFalse(args.out.exists())


if __name__ == '__main__':
    unittest.main()
