"""HTTP and grading-service tests. Docker calls are simulated here."""

import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock
import urllib.error
import urllib.request

from code_runner import RunnerError
from practice_web import PracticeApp, make_server
from run_submission import load_lesson

ROOT = Path(__file__).resolve().parents[1]


class PracticeWebTests(unittest.TestCase):
    def setUp(self):
        self.lesson = load_lesson(ROOT / "exercises/python/largest_value.json")
        self.runner = Mock()
        self.runner.run.side_effect = lambda source, entrypoint, args: {
            "status": "ok", "value": max(args[0]), "args_after": args, "output": "",
        }
        self.app = PracticeApp(self.lesson, self.runner)
        self.server = make_server(self.app, 0)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path, data=None, headers=None):
        supplied = {"Origin": self.origin, "Content-Type": "application/json"}
        if headers:
            supplied.update(headers)
        request = urllib.request.Request(
            self.origin + path,
            data=None if data is None else json.dumps(data).encode(), headers=supplied,
        )
        try:
            with self.client.open(request, timeout=3) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def test_public_lesson_has_no_reference_key_or_hints(self):
        status, raw, _ = self.request("/api/lesson")
        lesson = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertNotIn("reference_solution", lesson)
        self.assertNotIn("tests", lesson)
        self.assertNotIn("hints", lesson)
        self.assertEqual(lesson["test_count"], 8)

    def test_assets_and_no_path_traversal(self):
        for path in ("/", "/app.js", "/app.css"):
            status, raw, headers = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(raw)
            self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.request("/../infrastructure/.env.openwebui")[0], 404)

    def test_grade_all_cases_and_pass_inputs_only(self):
        status, raw, _ = self.request("/api/run", {"source": "def largest_value(xs): return max(xs)"})
        result = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual((result["passed"], result["total"]), (8, 8))
        self.assertTrue(result["complete"])
        self.assertEqual(self.runner.run.call_count, 8)
        self.assertEqual(self.runner.run.call_args_list[0].args[2], [[3, 8, 2]])
        self.assertEqual(result["results"][0]["args"], [[3, 8, 2]])

    def test_syntax_error_is_a_test_result(self):
        self.runner.run.side_effect = None
        self.runner.run.return_value = {"status": "syntax_error", "message": "Invalid syntax"}
        status, raw, _ = self.request("/api/run", {"source": "bad code"})
        result = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["results"][0]["status"], "syntax_error")
        self.assertEqual(result["results"][0]["args"], [[3, 8, 2]])

    def test_result_inputs_distinguish_empty_strings_quotes_and_newlines(self):
        inputs = ["", "''", "\n", r"\n"]
        self.lesson["tests"] = [
            {"name": f"Source {i}: empty string", "args": [value], "expected": value == value[::-1]}
            for i, value in enumerate(inputs)]
        self.runner.run.side_effect = lambda source, entrypoint, args: {
            "status": "ok", "value": args[0] == args[0][:-1][::-1], "args_after": args}
        status, raw, _ = self.request("/api/run", {"source": "fixture starter"})
        self.assertEqual(status, 200)
        results = json.loads(raw)["results"]
        self.assertEqual([result["args"] for result in results], [[value] for value in inputs])
        self.assertEqual(results[0]["status"], "passed")
        self.assertEqual(results[1]["status"], "failed")

    def test_result_inputs_do_not_alias_authored_tests(self):
        result = self.app.run("fixture submission")
        result["results"][0]["args"][0].append(999)
        self.assertEqual(self.lesson["tests"][0]["args"], [[3, 8, 2]])

    def test_display_evidence_preserves_large_integers_and_float_types(self):
        self.lesson['tests'] = [{'name':'precision', 'args':[2**63-1], 'expected':1.0}]
        self.runner.run.side_effect = lambda source, entrypoint, args: {'status':'ok','value':1,'args_after':args}
        result = self.app.run('fixture')['results'][0]
        self.assertEqual(result['args_json'], '[9223372036854775807]')
        self.assertEqual(result['expected_json'], '1.0')
        self.assertEqual(result['actual_json'], '1')
        self.assertEqual(result['status'], 'failed')

    def test_infrastructure_failure_produces_no_grade(self):
        self.runner.run.side_effect = RunnerError("sudo unavailable")
        status, raw, _ = self.request("/api/run", {"source": "code"})
        self.assertEqual(status, 503)
        self.assertNotIn("passed", json.loads(raw))
        self.assertFalse(self.app.busy.locked())

    def test_wrong_answers_are_not_infrastructure_failures(self):
        self.runner.run.side_effect = lambda source, entrypoint, args: {
            "status": "ok", "value": 0, "args_after": args,
        }
        status, raw, _ = self.request("/api/run", {"source": "code"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["passed"], 1)

    def test_hint_sequence_and_invalid_indexes(self):
        for index, expected in enumerate(self.lesson["hints"]):
            status, raw, _ = self.request("/api/hint", {"index": index})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["hint"], expected)
        for index in (-1, 3, True, "0"):
            self.assertEqual(self.request("/api/hint", {"index": index})[0], 400)
        self.runner.run.assert_not_called()

    def test_untrusted_origin_rejected_before_execution(self):
        self.assertEqual(self.request("/api/run", {"source": "code"},
                                      {"Origin": "https://unrelated.example"})[0], 403)
        self.runner.run.assert_not_called()

    def test_unknown_host_rejected(self):
        self.assertEqual(self.request("/api/lesson", headers={"Host": "unrelated.example"})[0], 403)

    def test_empty_and_oversized_source_rejected(self):
        for source in ("", "   ", "x" * 16001, "é" * 9000):
            self.assertEqual(self.request("/api/run", {"source": source})[0], 400)
        self.runner.run.assert_not_called()

    def test_busy_request_rejected(self):
        self.app.busy.acquire()
        try:
            self.assertEqual(self.request("/api/run", {"source": "code"})[0], 429)
        finally:
            self.app.busy.release()
        self.runner.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
