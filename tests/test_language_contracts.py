"""Typed native interfaces and safe literal construction; no source is executed."""
import unittest
from unittest.mock import patch
from code_runner import RunnerError
from compiled_runner import CompiledRunner
from language_contracts import function_header, typed_cases, typed_value, validate_signature
from native_harness import build_harness, c_literal


class ContractTests(unittest.TestCase):
    def test_container_preparation_timeout_is_not_a_student_time_limit(self):
        runner = CompiledRunner('sha256:' + 'a'*64, 'java', {'parameters':[], 'returns':'int'})
        with patch('code_runner.DockerRunner.run', return_value={'status':'timeout', 'message':'Wall-time limit reached.'}):
            with self.assertRaises(RunnerError):
                runner.run('unused source', 'solve', [])
        program_limit = {'status':'timeout', 'message':'Program time limit reached.'}
        with patch('code_runner.DockerRunner.run', return_value=program_limit):
            self.assertEqual(runner.run('unused source', 'solve', []), program_limit)

    def test_headers_match_native_calling_conventions(self):
        signature = {'parameters': ['int_array', 'string', 'bool'], 'returns': 'long'}
        self.assertEqual(function_header('c', signature), 'long long solve(const int * arg0, int arg0_len, const char * arg1, bool arg2)')
        self.assertEqual(function_header('cpp', signature), 'long long solve(const std::vector<int>& arg0, const std::string& arg1, bool arg2)')
        self.assertEqual(function_header('java', signature), 'public static long solve(int[] arg0, String arg1, boolean arg2)')
        self.assertEqual(function_header('c', {'parameters': [], 'returns': 'int'}), 'int solve(void)')

    def test_signature_rejects_unsupported_types_and_c_array_returns(self):
        for language, signature in [('c', {'parameters': [], 'returns': 'int_array'}),
                ('java', {'parameters': ['arbitrary code'], 'returns': 'int'}),
                ('cpp', {'parameters': ['int'] * 6, 'returns': 'int'}),
                ('unknown', {'parameters': [], 'returns': 'int'})]:
            with self.subTest(language=language), self.assertRaises(ValueError):
                validate_signature(language, signature)

    def test_value_types_ranges_and_text_encoding_are_explicit(self):
        for value, kind in [(True, 'int'), (1, 'bool'), (2**31, 'int'), (2**63, 'long'),
                            (float('nan'), 'double'), ('😊', 'string'),
                            ([True], 'int_array'), ([0]*101, 'int_array')]:
            with self.subTest(value=value, kind=kind), self.assertRaises(ValueError):
                typed_value(value, kind)
        self.assertEqual(typed_value('\n\t"\\', 'string'), '\n\t"\\')
        self.assertEqual(typed_value("\0\x1f\x7f", "string", "java"), "\0\x1f\x7f")
        with self.assertRaises(ValueError):
            typed_value("\0", "string", "c")
        self.assertEqual(typed_value(-(2**31), 'int'), -(2**31))
        self.assertEqual(typed_value(2**63-1, 'long'), 2**63-1)
        self.assertEqual(typed_value(-(2**63), 'long'), -(2**63))

    def test_double_cases_normalize_without_changing_other_argument_types(self):
        signature = {'parameters': ['double', 'int_array'], 'returns': 'double'}
        result = typed_cases(signature, [{'name': 'sample', 'args': [1, [2]], 'expected': 3}])[0]
        self.assertIs(type(result['args'][0]), float)
        self.assertIs(type(result['args'][1][0]), int)
        self.assertIs(type(result['expected']), float)

    def test_literal_values_cannot_escape_the_trusted_harness(self):
        value = '"); abort(); //\n\\u000a'
        encoded = c_literal(value)
        self.assertNotIn('abort', encoded)
        self.assertTrue(encoded.startswith('"\\'))
        for language in ('c', 'cpp', 'java'):
            harness = build_harness(language, {'parameters': ['string'], 'returns': 'bool'}, [value])
            self.assertTrue(harness)
        self.assertIn('null', build_harness('java', {'parameters': [], 'returns': 'int'}, []))

    def test_harness_never_receives_expected_answers(self):
        signature = {'parameters': ['int_array'], 'returns': 'int'}
        for language in ('c', 'cpp', 'java'):
            harness = build_harness(language, signature, [[-4, -2]])
            self.assertNotIn('expected', str(harness))
            self.assertIn('AM_RESULT', str(harness))


if __name__ == '__main__':
    unittest.main()
