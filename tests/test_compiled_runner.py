"""Real compiler/runtime checks. Opt in after running the setup tool."""
import os
from pathlib import Path
import unittest
import subprocess
from unittest.mock import patch

from code_runner import DockerRunner, grade_case
from compiled_runner import CompiledRunner
from language_contracts import function_header

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('java', 'c', 'cpp')


def source_for(language, signature, body, includes=''):
    function = function_header(language, signature) + ' { ' + body + ' }'
    return 'public class Solution { ' + function + ' }' if language == 'java' else includes + '\n' + function


@unittest.skipUnless(os.environ.get('AM_COMPILED_TESTS') == '1', 'Set AM_COMPILED_TESTS=1 after compiler setup.')
class CompiledContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pin = ROOT / '.am-runtime/compiled-image.txt'
        if not pin.exists():
            raise RuntimeError('Run python tools/setup_compiled_runtime.py first.')
        cls.image = pin.read_text().strip()
        cls.command = ('docker',) if os.environ.get('AM_DOCKER_DIRECT') == '1' else ('sudo', '-n', 'docker')

    def run_case(self, language, signature, body, args, expected, includes=''):
        source = source_for(language, signature, body, includes)
        runner = CompiledRunner(self.image, language, signature, self.command)
        return grade_case(runner, source, 'solve', {'name': 'native check', 'args': args, 'expected': expected}, True)

    def test_requests_execute_without_waiting_for_stdin_eof(self):
        python_image = (ROOT / 'infrastructure/python-runner-image.txt').read_text().strip()
        runners = [(DockerRunner(python_image, self.command), 'def solve(x): return x+1'),
                   (CompiledRunner(self.image, 'java', {'parameters':['int'], 'returns':'int'}, self.command),
                    'public class Solution { public static int solve(int arg0) { return arg0+1; } }')]
        real_popen = subprocess.Popen
        for runner, source in runners:
            closers = []
            def keep_input_open(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                if process.stdin is not None:
                    closers.append(process.stdin.close)
                    process.stdin.close = lambda: None
                return process
            with self.subTest(driver=type(runner).__name__):
                try:
                    with patch('code_runner.subprocess.Popen', side_effect=keep_input_open):
                        result = runner.run(source, 'solve', [41])
                    self.assertEqual(result['status'], 'ok', result)
                    self.assertEqual(result['value'], 42)
                finally:
                    for close in closers:
                        close()

    def test_correct_incorrect_and_compiler_errors(self):
        signature = {'parameters': ['int'], 'returns': 'int'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(self.run_case(language, signature, 'return arg0+1;', [41], 42)['status'], 'passed')
                self.assertEqual(self.run_case(language, signature, 'return 0;', [41], 42)['status'], 'failed')
                broken = self.run_case(language, signature, 'return ???;', [41], 42)
                self.assertEqual(broken['status'], 'compile_error', broken)
                self.assertTrue(broken['message'])

    def test_runtime_errors_and_time_limits(self):
        signature = {'parameters': ['int'], 'returns': 'int'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                error = self.run_case(language, signature, 'return 1/arg0;', [0], 0)
                self.assertEqual(error['status'], 'runtime_error', error)
                timeout = self.run_case(language, signature, 'while(true) {}', [0], 0)
                self.assertEqual(timeout['status'], 'timeout', timeout)

    def test_output_limit_and_captured_output(self):
        signature = {'parameters': ['int'], 'returns': 'int'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                statement = 'System.out.println("hello");' if language == 'java' else 'printf("hello\\n");'
                normal = self.run_case(language, signature, statement + ' return arg0;', [7], 7)
                self.assertEqual(normal['status'], 'passed', normal)
                self.assertIn('hello', normal['output'])
                large = self.run_case(language, signature, 'for(int i=0;i<100000;i++) { ' + statement + ' } return arg0;', [7], 7)
                self.assertEqual(large['status'], 'output_limit', large)

    def test_array_mutation_is_not_accepted(self):
        signature = {'parameters': ['int_array'], 'returns': 'int'}
        bodies = {'java': 'arg0[0]=99; return 0;', 'c': '((int*)arg0)[0]=99; return 0;',
                  'cpp': 'const_cast<std::vector<int>&>(arg0)[0]=99; return 0;'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                result = self.run_case(language, signature, bodies[language], [[1,2]], 0)
                self.assertEqual(result['status'], 'failed', result)
                self.assertTrue(result['input_modified'])

    def test_string_roundtrips_preserve_empty_quotes_newlines_and_escape_text(self):
        signature = {'parameters': ['string'], 'returns': 'string'}
        for language in LANGUAGES:
            for value in ('', '"; abort(); //\n\\u000a\\"'):
                with self.subTest(language=language, value=value):
                    result = self.run_case(language, signature, 'return arg0;', [value], value)
                    self.assertEqual(result['status'], 'passed', result)

    def test_escaped_harness_allows_large_valid_string_arguments(self):
        # Valid source and <4,000 JSON characters of inputs expand beyond the
        # Python transport's 32 KB allowance once native literals are escaped.
        signature = {'parameters':['string']*4, 'returns':'bool'}
        result = self.run_case('c', signature,
            "return arg0[0]=='x' && arg1[0]=='x' && arg2[0]=='x' && arg3[0]=='x';",
            ['x'*990]*4, True, '/*' + 'padding '*875 + '*/')
        self.assertEqual(result['status'], 'passed', result)

    def test_typed_values_and_floating_point_serialization(self):
        mixed = {'parameters': ['bool', 'long', 'double', 'string', 'int_array'], 'returns': 'bool'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                result = self.run_case(language, mixed, 'return arg0;', [True, 2**63-1, 1.0, 'a"b', [1,-2]], True)
                self.assertEqual(result['status'], 'passed', result)
                long = self.run_case(language, {'parameters':['long'], 'returns':'long'}, 'return arg0;', [-(2**63)], -(2**63))
                self.assertEqual(long['status'], 'passed', long)
                real = self.run_case(language, {'parameters':['double'], 'returns':'double'}, 'return arg0/2;', [2.0], 1.0)
                self.assertEqual(real['status'], 'passed', real)

    def test_java_and_cpp_array_returns(self):
        signature = {'parameters': ['int_array'], 'returns': 'int_array'}
        java = 'int[] out=arg0.clone(); for(int i=0,j=out.length-1;i<j;i++,j--) {int t=out[i];out[i]=out[j];out[j]=t;} return out;'
        cpp = 'std::vector<int> out=arg0; std::reverse(out.begin(),out.end()); return out;'
        for language, body, includes in [('java', java, ''), ('cpp', cpp, '#include <algorithm>')]:
            with self.subTest(language=language):
                result = self.run_case(language, signature, body, [[1,2,3]], [3,2,1], includes)
                self.assertEqual(result['status'], 'passed', result)

    def test_root_filesystem_write_is_denied(self):
        signature = {'parameters': [], 'returns': 'bool'}
        bodies = {'java': 'try { java.nio.file.Files.writeString(java.nio.file.Path.of("/am-forbidden"),"x"); return false; } catch(java.io.IOException error) { return true; }',
                  'c': 'FILE *file=fopen("/am-forbidden","w"); if(file) {fclose(file);return false;} return true;',
                  'cpp': 'FILE *file=fopen("/am-forbidden","w"); if(file) {fclose(file);return false;} return true;'}
        for language in LANGUAGES:
            with self.subTest(language=language):
                result = self.run_case(language, signature, bodies[language], [], True)
                self.assertEqual(result['status'], 'passed', result)


if __name__ == '__main__':
    unittest.main()
