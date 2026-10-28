"""Runner checks. Docker tests require explicit opt-in."""

import os
from pathlib import Path
import unittest
import subprocess
import tempfile
import threading
import sys
from unittest.mock import Mock, patch

from code_runner import DockerAuthorizationError, DockerRunner, RunnerError, equivalent, grade_case

ROOT = Path(__file__).resolve().parents[1]
RUN_DOCKER = os.environ.get("AM_DOCKER_TESTS") == "1"


class ComparisonTests(unittest.TestCase):
    def test_cancel_waits_for_late_container_creation_before_finishing_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory)/'fake-docker'
            command.write_text('#!'+sys.executable+'\nimport sys,time\n'
                               'if sys.argv[1]=="create": print("fake-id")\n'
                               'else: time.sleep(30)\n')
            command.chmod(0o700)
            runner = DockerRunner('python@sha256:'+'a'*64,command=(str(command),),wall_seconds=3)
            runner.cancel_event = threading.Event()
            timer = threading.Timer(0.1, runner.cancel_event.set);timer.start()
            try:
                with patch.object(runner,'remove',side_effect=[False,False,True]) as remove:
                    with self.assertRaisesRegex(RunnerError,'canceled'):
                        runner.run('def f(): return 1','f',[])
                self.assertEqual(remove.call_count,3)
                self.assertEqual(len({call.args[0] for call in remove.call_args_list}),1)
            finally:
                timer.cancel();timer.join()
    def test_expired_sudo_exit_one_is_infrastructure_failure_not_a_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            sudo = Path(directory) / 'sudo'
            sudo.write_text("#!/bin/sh\nprintf '%s\\n' 'sudo: a password is required' >&2\nexit 1\n")
            sudo.chmod(0o700)
            runner = DockerRunner('python@sha256:'+'a'*64, command=(str(sudo), '-n', 'docker'))
            with self.assertRaises(DockerAuthorizationError):
                runner.run('def f(): return 42', 'f', [])

    def test_only_sudo_authorization_messages_receive_auth_classification(self):
        direct = DockerRunner('python@sha256:'+'a'*64, command=('docker',))
        direct.check_authorization('sudo: a password is required')
        via_sudo = DockerRunner('python@sha256:'+'a'*64)
        via_sudo.check_authorization('Docker daemon is unavailable')
        with patch('code_runner.subprocess.run', return_value=Mock(
                returncode=1, stderr='sudo: a password is required')):
            with self.assertRaises(DockerAuthorizationError):
                via_sudo.remove('am-case-auth-check')

    def test_json_comparison(self):
        # Avoid accidentally accepting True or 1.0 for an integer answer.
        self.assertFalse(equivalent(True, 1))
        self.assertFalse(equivalent(1.0, 1))
        self.assertTrue(equivalent({"a": [1]}, {"a": [1]}))

    def test_cleanup_retries_the_same_container_after_daemon_timeout(self):
        runner = DockerRunner('python@sha256:' + 'a' * 64, command=('docker',))
        with patch('code_runner.subprocess.run', side_effect=[
                subprocess.TimeoutExpired(['docker'], 10), Mock(returncode=1, stderr='No such container: am-case-test')]) as run:
            self.assertFalse(runner.remove('am-case-test'))
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all(call.args[0] == ['docker', 'rm', '-f', 'am-case-test'] for call in run.call_args_list))


@unittest.skipUnless(
    RUN_DOCKER,
    "Set AM_DOCKER_TESTS=1 to run Docker integration tests.",
)
class ContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = (
            (ROOT / "infrastructure/python-runner-image.txt").read_text().strip()
        )

    def setUp(self):
        command = ('docker',) if os.environ.get('AM_DOCKER_DIRECT') == '1' else ('sudo', '-n', 'docker')
        self.runner = DockerRunner(self.image, command=command)

    def test_correct_return(self):
        result = grade_case(
            self.runner,
            "def f(xs): return max(xs)",
            "f",
            {
                "name": "negative values",
                "args": [[-8, -3]],
                "expected": -3,
            },
            forbid_mutation=True,
        )
        self.assertEqual(result["status"], "passed")

    def test_incorrect_return(self):
        result = grade_case(
            self.runner,
            "def f(xs): return 0",
            "f",
            {
                "name": "negative values",
                "args": [[-8, -3]],
                "expected": -3,
            },
            forbid_mutation=True,
        )
        self.assertEqual(result["status"], "failed")

    def test_mutation_fails(self):
        result = grade_case(
            self.runner,
            "def f(xs): xs.sort(); return xs[-1]",
            "f",
            {
                "name": "input mutation",
                "args": [[2, 1]],
                "expected": 2,
            },
            forbid_mutation=True,
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["input_modified"])

    def test_syntax_error(self):
        result = self.runner.run("def f(:", "f", [])
        self.assertEqual(result["status"], "syntax_error")

    def test_runtime_error(self):
        result = self.runner.run(
            "def f(): return 1 / 0",
            "f",
            [],
        )
        self.assertEqual(result["status"], "runtime_error")

    def test_output_limit(self):
        result = self.runner.run(
            "def f(): print('x' * 10000)",
            "f",
            [],
        )
        self.assertEqual(result["status"], "output_limit")

    def test_low_level_output_limit(self):
        # os.write bypasses Python's redirected print stream.
        source = (
            "import os\ndef f():\n    while True:\n        os.write(1, b'x' * 4096)\n"
        )
        result = self.runner.run(source, "f", [])
        self.assertEqual(result["status"], "output_limit")

    def test_wall_timeout(self):
        runner = DockerRunner(
            self.image,
            command=self.runner.command,
            wall_seconds=2,
        )
        result = runner.run(
            "import time\ndef f(): time.sleep(30)\n",
            "f",
            [],
        )
        self.assertEqual(result["status"], "timeout")

    def test_infinite_loop_stops(self):
        result = self.runner.run(
            "def f():\n    while True:\n        pass\n",
            "f",
            [],
        )
        self.assertIn(
            result["status"],
            {"execution_error", "timeout"},
        )

    def test_root_write_denied(self):
        result = self.runner.run(
            "def f():\n    open('/test-file', 'w').write('x')\n",
            "f",
            [],
        )
        self.assertEqual(result["status"], "runtime_error")

    def test_missing_function(self):
        result = self.runner.run("x = 1", "f", [])
        self.assertEqual(result["status"], "runtime_error")

    def test_answer_key_not_in_submission_globals(self):
        result = self.runner.run(
            "def f(): return sorted(globals().keys())",
            "f",
            [],
        )
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("expected", result["value"])


if __name__ == "__main__":
    unittest.main()
