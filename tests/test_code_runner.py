"""Runner checks. Docker tests require explicit opt-in."""

import os
from pathlib import Path
import unittest

from code_runner import DockerRunner, equivalent, grade_case

ROOT = Path(__file__).resolve().parents[1]
RUN_DOCKER = os.environ.get("AM_DOCKER_TESTS") == "1"


class ComparisonTests(unittest.TestCase):
    def test_json_comparison(self):
        # Avoid accidentally accepting True or 1.0 for an integer answer.
        self.assertFalse(equivalent(True, 1))
        self.assertFalse(equivalent(1.0, 1))
        self.assertTrue(equivalent({"a": [1]}, {"a": [1]}))


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
        self.runner = DockerRunner(self.image)

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
