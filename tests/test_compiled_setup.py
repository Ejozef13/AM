"""Compiler setup compatibility and all-or-nothing runtime publication."""
from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import setup_compiled_runtime as setup


class CompiledSetupTests(unittest.TestCase):
    def run_setup(self, options=(), failure=None, probe_statuses=None, existing_pin=None):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            if existing_pin is not None:
                (root / '.am-runtime').mkdir()
                (root / '.am-runtime/compiled-image.txt').write_text(existing_pin)
            stack.enter_context(patch.object(setup, 'ROOT', root))
            stack.enter_context(patch('sys.argv', ['setup_compiled_runtime.py', *options]))
            build = stack.enter_context(patch.object(setup.subprocess, 'run', side_effect=failure))
            stack.enter_context(patch.object(setup.subprocess, 'check_output', return_value='sha256:'+'a'*64))
            grade = stack.enter_context(patch.object(setup, 'grade_case',
                side_effect=[{'status': status} for status in (probe_statuses or ['passed']*3)]))
            stack.enter_context(patch('builtins.print'))
            result = setup.main()
            pin = root / '.am-runtime/compiled-image.txt'
            return result, build.call_args_list, grade.call_count, pin.read_text() if pin.exists() else None

    def test_normal_setup_works_without_buildkit_flags_and_probes_all_languages(self):
        result, calls, probes, pin = self.run_setup()
        self.assertEqual(result, 0)
        command = calls[0].args[0]
        self.assertNotIn('--secret', command)
        self.assertNotIn('--file', command)
        self.assertEqual(probes, 3)
        self.assertEqual(pin, 'sha256:'+'a'*64+'\n')

    def test_custom_ca_selects_the_separate_buildkit_dockerfile(self):
        result, calls, _, _ = self.run_setup(['--ca-bundle', '/tmp/trusted-public-ca.pem'])
        self.assertEqual(result, 0)
        command = calls[0].args[0]
        self.assertTrue(command[command.index('--file')+1].endswith('/Dockerfile.buildkit'))
        self.assertEqual(command[command.index('--secret')+1], 'id=am_ca_bundle,src=/tmp/trusted-public-ca.pem')

    def test_failed_build_preserves_existing_runtime_pin_and_does_not_probe(self):
        result, _, probes, pin = self.run_setup(
            failure=subprocess.CalledProcessError(1, ['docker', 'build']), existing_pin='previous-pin\n')
        self.assertEqual(result, 1)
        self.assertEqual(probes, 0)
        self.assertEqual(pin, 'previous-pin\n')

    def test_failed_compiler_probe_does_not_publish_a_partial_runtime(self):
        result, _, probes, pin = self.run_setup(probe_statuses=['passed', 'compile_error'])
        self.assertEqual(result, 1)
        self.assertEqual(probes, 2)
        self.assertIsNone(pin)

    def test_existing_image_skips_build_but_still_requires_all_probes(self):
        result, calls, probes, pin = self.run_setup(['--use-existing-image'])
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertEqual(probes, 3)
        self.assertIsNotNone(pin)
