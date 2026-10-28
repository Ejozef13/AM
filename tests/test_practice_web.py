"""HTTP and grading-service tests. Docker calls are simulated here."""

import json
import io
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

from code_runner import RunnerError
from practice_web import PracticeApp, make_server
from ai_exercises import validate_draft
from test_multilanguage_generation import native_draft

ROOT = Path(__file__).resolve().parents[1]


class PracticeWebTests(unittest.TestCase):
    def setUp(self):
        # Fixed service fixture: never shipped or offered as an app question.
        raw = native_draft('c')
        raw.pop('signature')
        raw['notes_quote'] = ''
        raw.update(entrypoint='solve', starter_code='def solve(values): return 0',
                   reference_solution='def solve(values): return max(values)')
        self.lesson = validate_draft(raw, '', 'standard')
        self.lesson['quality'] = dict(source='ai-generated', separate_review=True,
                                      distinct_models=False, reference_runs=6)
        self.runner = Mock()
        self.runner.run.side_effect = lambda source, entrypoint, args: {
            "status": "ok", "value": max(args[0]), "args_after": args, "output": "",
        }
        self.app = PracticeApp(self.runner, Mock())
        key, _ = self.app.sessions.publish([self.lesson], {}, 'Test fixture')
        self.fields = {'session_id': key, 'lesson_index': 0}
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
        if data is not None:
            data = self.fields | data
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
        lesson = self.app.public_lesson(self.lesson)
        self.assertNotIn("reference_solution", lesson)
        self.assertNotIn("tests", lesson)
        self.assertNotIn("hints", lesson)
        self.assertEqual(lesson["test_count"], 3)
        self.assertEqual(self.request('/api/lesson')[0], 404)

    def test_grading_and_hints_require_a_generated_session(self):
        self.fields = {}
        self.assertEqual(self.request('/api/run', {'source': 'fixture'})[0], 400)
        self.assertEqual(self.request('/api/hint', {'index': 0})[0], 400)
        self.runner.run.assert_not_called()

    def test_reply_tolerates_a_browser_disconnecting_during_headers_or_body(self):
        for field, error in [('end_headers', ConnectionResetError()), ('write', BrokenPipeError())]:
            with self.subTest(field=field):
                handler = object.__new__(self.server.RequestHandlerClass)
                handler.send_response = Mock()
                handler.send_header = Mock()
                handler.end_headers = Mock()
                handler.wfile = Mock()
                target = handler.wfile.write if field == 'write' else handler.end_headers
                target.side_effect = error
                handler.reply(200, {'complete': True})
                self.assertTrue(handler.close_connection)

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
        self.assertEqual((result["passed"], result["total"]), (3, 3))
        self.assertTrue(result["complete"])
        self.assertEqual(self.runner.run.call_count, 3)
        self.assertEqual(self.runner.run.call_args_list[0].args[2], [[-8, -3]])
        self.assertEqual(result["results"][0]["args"], [[-8, -3]])

    def test_syntax_error_is_a_test_result(self):
        self.runner.run.side_effect = None
        self.runner.run.return_value = {"status": "syntax_error", "message": "Invalid syntax"}
        status, raw, _ = self.request("/api/run", {"source": "bad code"})
        result = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["results"][0]["status"], "syntax_error")
        self.assertEqual(result["results"][0]["args"], [[-8, -3]])

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
        result = self.app.run("fixture submission", self.fields)
        result["results"][0]["args"][0].append(999)
        self.assertEqual(self.lesson["tests"][0]["args"], [[-8, -3]])

    def test_display_evidence_preserves_large_integers_and_float_types(self):
        self.lesson['tests'] = [{'name':'precision', 'args':[2**63-1], 'expected':1.0}]
        self.runner.run.side_effect = lambda source, entrypoint, args: {'status':'ok','value':1,'args_after':args}
        result = self.app.run('fixture', self.fields)['results'][0]
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

    def test_execution_diagnostics_report_the_cause_without_submission_data(self):
        self.app.diagnostics = True
        self.runner.run.side_effect = RunnerError('Compiler container preparation exceeded its wall-time allowance.')
        stream = io.StringIO()
        with patch('practice_web.sys.stderr', stream):
            status, raw, _ = self.request('/api/run', {'source':'PRIVATE_SUBMISSION_MARKER'})
        result = json.loads(raw)
        self.assertEqual(status, 503)
        self.assertEqual(result['error_code'], 'runner_unavailable')
        self.assertIn('preparation exceeded', result['error'])
        self.assertIn('retained', result['error'])
        self.assertIn('AM execution diagnostic:', stream.getvalue())
        self.assertIn('preparation exceeded', stream.getvalue())
        self.assertNotIn('PRIVATE_SUBMISSION_MARKER', stream.getvalue())
        self.assertNotIn('args', stream.getvalue())
        self.assertFalse(self.app.busy.locked())

    def test_wrong_answers_are_not_infrastructure_failures(self):
        self.runner.run.side_effect = lambda source, entrypoint, args: {
            "status": "ok", "value": 0, "args_after": args,
        }
        status, raw, _ = self.request("/api/run", {"source": "code"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["passed"], 0)

    def test_hint_sequence_and_invalid_indexes(self):
        for index, expected in enumerate(self.lesson["hints"]):
            status, raw, _ = self.request("/api/hint", {"index": index})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["hint"], expected)
        for index in (-1, 1, True, "0"):
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
