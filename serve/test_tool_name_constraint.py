"""Names must stay constrained across prose, thinking, multiple calls and MTP windows."""
import base64
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from serve import constrain as C
from serve.server import Service, ByteTokenizer


@unittest.skipUnless(C.available(), 'llguidance required')
class ToolNameConstraintTests(unittest.TestCase):
    def setUp(self):
        self.tok = ByteTokenizer()
        self.stop = set(self.tok.encode('<|im_end|>', parse_special=True))
        self.vocab = C.Vocab(self.tok, self.stop)

    def test_tools_without_response_format_are_actually_constrained(self):
        app = Service.__new__(Service)
        app.engine = SimpleNamespace(supports_mask=True)
        app.tok, app.stop_ids = self.tok, self.stop
        tools = [{'name': 'sql_query', 'parameters': {'type': 'object'}}]
        with patch.dict(os.environ, {'STRATA_TOOL_MASK': '1', 'STRATA_TOOL_NAME_ENUM': '1', 'STRATA_TOOL_MASK_STRICT': '1'}):
            sampling = app._with_constraint({}, tools, thinking=True)
        self.assertIsNotNone(sampling.get(C.KEY))

    def guard(self):
        return C.ToolNameConstraint(self.vocab, ['sql_query', 'exec', 'exec_command'])

    def feed(self, guard, text):
        for t in self.tok.encode(text, parse_special=True):
            self.assertTrue(C.Constraint.allowed(guard.mask(), t), (text, t))
            guard.feed(t)

    def test_wrong_prefix_is_masked_after_prose_and_inside_thinking(self):
        for lead in ['', 'Ich prüfe das.\n', '<think>Plan: ', '<tool_call>\n']:
            with self.subTest(lead=lead):
                c = self.guard()
                self.feed(c, lead + '<function=')
                self.assertFalse(C.Constraint.allowed(c.mask(), ord('m')))
                self.assertTrue(C.Constraint.allowed(c.mask(), ord('s')))
                self.assertFalse(C.Constraint.allowed(c.mask(), min(self.stop)))

    def test_each_call_and_prefix_pair_stays_constrained(self):
        c = self.guard()
        self.feed(c, '<tool_call><function=exec>anything</function></tool_call>\nMore prose.\n<tool_call><function=exec')
        self.assertTrue(C.Constraint.allowed(c.mask(), ord('>')))
        self.assertTrue(C.Constraint.allowed(c.mask(), ord('_')))
        self.assertFalse(C.Constraint.allowed(c.mask(), ord('x')))
        self.feed(c, '_command>args</function></tool_call>')
        self.feed(c, 'Deutsch: äöü und 中文.')

    def test_lookahead_does_not_mutate_live_state_or_accept_bad_draft(self):
        c = self.guard()
        self.feed(c, '<function=')
        before = c.mask()
        reply = c.reply(list(b'sql_x'))
        _, n, *rows = reply.split()
        self.assertEqual(int(n), 5)  # sql_ accepted, x is outside the name trie
        self.assertEqual(c.mask(), before)
        self.assertTrue(C.Constraint.allowed(base64.b64decode(rows[-1]), ord('q')))
        self.assertFalse(C.Constraint.allowed(base64.b64decode(rows[-1]), ord('x')))

    def test_many_toolboxes_do_not_accumulate_unbounded_masks(self):
        first = C.ToolNameConstraint(self.vocab, ['original'])
        self.feed(first, '<function=')
        for i in range(20):
            guard = C.ToolNameConstraint(self.vocab, ['tool_' + str(i)])
            self.feed(guard, '<function=tool_' + str(i) + '>')
        self.assertLessEqual(len(self.vocab._tool_masks), 8)
        # Eviction must not change an already-active request's declared names.
        self.assertTrue(C.Constraint.allowed(first.mask(), ord('o')))
        self.assertFalse(C.Constraint.allowed(first.mask(), ord('t')))

    def test_illegal_emitted_token_fails_closed(self):
        c = self.guard()
        self.feed(c, '<function=')
        with self.assertRaises(ValueError):
            c.feed(ord('m'))

    def test_unsupported_engine_fails_closed_when_opted_in(self):
        app = Service.__new__(Service)
        app.engine = SimpleNamespace(supports_mask=False)
        with patch.dict(os.environ, {'STRATA_TOOL_MASK_STRICT': '1'}):
            with self.assertRaises(ValueError):
                app._with_constraint({}, [{'name': 'sql_query'}], thinking=False)


if __name__ == '__main__':
    unittest.main()
