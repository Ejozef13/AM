"""Planner contracts, session isolation, and HTTP routing. No live model needed."""

from copy import deepcopy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

from am_core import AMError
from code_runner import RunnerError
from exercise_families import CATALOG, LEVELS, generate_lesson
from practice_planner import KeywordPlanner, OllamaPlanner, study_input, validate_plan
from practice_sessions import SessionStore
from practice_web import PracticeApp, make_server
from run_submission import load_lesson

ROOT = Path(__file__).resolve().parents[1]
NOTES = "A counter starts at zero. Count matching elements and return after the loop."
INPUT = {"language": "python", "topic": "counting", "notes": NOTES,
         "difficulty": "standard", "count": 2}


class AuthorTemplateRunner:
    """Only execute a known set of trusted author templates in this test double."""
    def __init__(self):
        self.allowed = set()
        for family in CATALOG:
            for level in LEVELS:
                for seed in range(80):
                    lesson = generate_lesson(family["id"], level, seed)
                    self.allowed.update((lesson["reference_solution"], lesson["starter_code"]))

    def run(self, source, entrypoint, args):
        if source not in self.allowed:
            return {"status": "runtime_error", "message": "Unknown test fixture; not executed."}
        namespace = {}
        exec(source, namespace)
        actual_args = deepcopy(args)
        return {"status": "ok", "value": namespace[entrypoint](*actual_args), "args_after": actual_args}


class PlannerTests(unittest.TestCase):
    def test_input_rejects_unimplemented_languages(self):
        for language in ("java", "c", "cpp"):
            with self.assertRaises(ValueError):
                study_input(INPUT | {"language": language})

    def test_input_limits(self):
        for changes in ({"notes": "x" * 12001}, {"count": True}, {"count": 6},
                        {"topic": "", "notes": ""}, {"difficulty": "expert"}):
            with self.assertRaises(ValueError):
                study_input(INPUT | changes)

    def test_unsupported_topic_is_not_substituted(self):
        with self.assertRaises(ValueError):
            KeywordPlanner().plan("Dijkstra and shortest paths", "")

    def test_exact_quote_required(self):
        plan = {"supported": True, "family": "counting", "focus": "Counters",
                "reason": "Relevant to the notes.", "notes_quote": NOTES[:26]}
        self.assertEqual(validate_plan(plan, NOTES)["family"], "counting")
        with self.assertRaises(AMError):
            validate_plan(plan | {"notes_quote": "invented material"}, NOTES)
        with self.assertRaises(AMError):
            validate_plan(plan | {"family": "shell-execution"}, NOTES)

    def test_model_plan_contract_has_no_execution_tools(self):
        response = {"done": True, "done_reason": "stop", "message": {"content": json.dumps({
            "supported": True, "family": "counting", "focus": "Counters",
            "reason": "Counters are in the supplied notes.", "notes_quote": NOTES[:26]})}}
        with patch("practice_planner.api", return_value=response) as api:
            self.assertEqual(OllamaPlanner().plan("counting", NOTES)["family"], "counting")
        payload = api.call_args.args[1]
        self.assertNotIn("tools", payload)
        self.assertEqual(payload["options"]["num_ctx"], 32768)

    def test_model_failures_do_not_become_offline_success(self):
        with patch("practice_planner.api", side_effect=AMError("offline")):
            with self.assertRaises(AMError):
                OllamaPlanner().plan("counting", NOTES)
        with patch("practice_planner.api", return_value={"done": True, "done_reason": "length"}):
            with self.assertRaises(AMError):
                OllamaPlanner().plan("counting", NOTES)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.runner = AuthorTemplateRunner()
        self.store = SessionStore(KeywordPlanner(), self.runner)

    def test_multiple_sessions_are_isolated(self):
        first, a = self.store.create(INPUT)
        second, b = self.store.create(INPUT | {"topic": "maximum", "notes": "", "count": 1})
        self.assertNotEqual(first, second)
        self.store.next({"session_id": first, "lesson_index": 0}, lambda lesson: {"title": lesson["title"]})
        self.assertEqual(a.index, 1)
        self.assertEqual(b.index, 0)

    def test_failed_reference_is_not_published(self):
        self.store.runner = Mock()
        self.store.runner.run.return_value = {"status": "runtime_error", "message": "fixture failed"}
        with self.assertRaises(RunnerError):
            self.store.create(INPUT)
        self.assertFalse(self.store.sessions)

    def test_undetected_starter_is_not_published(self):
        # An inert-bug fixture makes the starter match the reference.
        lesson = generate_lesson("counting", "introductory", 42)
        lesson["starter_code"] = lesson["reference_solution"]
        with patch("practice_sessions.generate_lesson", return_value=lesson):
            with self.assertRaises(RunnerError):
                self.store.create(INPUT | {"count": 1})
        self.assertFalse(self.store.sessions)

    def test_summary_and_expiration(self):
        key, session = self.store.create(INPUT | {"count": 1})
        session.attempts[0] = {"attempts": 2, "passed": len(session.lessons[0]["tests"])}
        result = self.store.next({"session_id": key, "lesson_index": 0}, lambda lesson: {})
        self.assertEqual(result["summary"]["completed"], 1)
        self.assertNotIn(key, self.store.sessions)
        key, session = self.store.create(INPUT | {"count": 1})
        session.created -= 7201
        with self.assertRaises(ValueError):
            self.store.get({"session_id": key, "lesson_index": 0})


class SessionHttpTests(unittest.TestCase):
    def setUp(self):
        self.app = PracticeApp(load_lesson(ROOT / "exercises/python/largest_value.json"),
                               AuthorTemplateRunner(), KeywordPlanner())
        self.server = make_server(self.app, 0)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

    def request(self, path, data=None):
        request = urllib.request.Request(self.origin + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Origin": self.origin, "Content-Type": "application/json"})
        try:
            with self.client.open(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_setup_availability(self):
        status, data = self.request("/api/setup")
        self.assertEqual(status, 200)
        self.assertEqual([x["id"] for x in data["languages"] if x["available"]], ["python"])

    def test_generated_session_routes_and_public_fields(self):
        from ai_exercises import OllamaExerciseGenerator
        from test_ai_exercises import FixtureRunner, NOTES, draft, review, response
        self.app.runner = FixtureRunner()
        generator = OllamaExerciseGenerator(self.app.runner)
        self.app.sessions.generator = generator
        status, setup = self.request("/api/setup")
        self.assertEqual(setup["mode"], "ai-generated")
        self.assertEqual(self.request("/api/progress")[1]["busy"], False)
        with patch("ai_exercises.api", side_effect=[response(draft()), response(review())]):
            status, view = self.request("/api/session", INPUT | {"topic": "factorial", "notes": NOTES, "count": 1})
        self.assertEqual(status, 201)
        self.assertEqual(view["lesson"]["quality"]["source"], "ai-generated")
        for field in ("reference_solution", "tests", "hints", "review_feedback"):
            self.assertNotIn(field, view["lesson"])
        fields = {"session_id": view["session_id"], "lesson_index": 0}
        self.assertEqual(self.request("/api/hint", fields | {"index": 0})[0], 200)
        status, result = self.request("/api/run", fields | {"source": draft()["reference_solution"]})
        self.assertEqual(result["passed"], 6)
        status, summary = self.request("/api/session/next", fields)
        self.assertEqual(summary["summary"]["completed"], 1)

    def test_complete_generated_workflow(self):
        status, view = self.request("/api/session", INPUT)
        self.assertEqual(status, 201)
        self.assertNotIn("reference_solution", view["lesson"])
        self.assertNotIn("tests", view["lesson"])
        fields = {"session_id": view["session_id"], "lesson_index": 0}
        session = self.app.sessions.sessions[view["session_id"]]
        self.assertEqual(self.request("/api/hint", fields | {"index": 0})[0], 200)
        source = session.lessons[0]["reference_solution"]
        status, result = self.request("/api/run", fields | {"source": source})
        self.assertEqual(status, 200)
        self.assertEqual(result["passed"], result["total"])
        status, next_view = self.request("/api/session/next", fields)
        self.assertEqual(next_view["number"], 2)
        self.assertEqual(self.request("/api/run", fields | {"source": source})[0], 400)
        status, summary = self.request("/api/session/finish", fields | {"lesson_index": 1})
        self.assertEqual(summary["summary"]["completed"], 1)
        self.assertEqual(summary["summary"]["items"][1]["passed"], None)

    def test_unsupported_languages_and_topics_leave_no_session(self):
        self.assertEqual(self.request("/api/session", INPUT | {"language": "java"})[0], 400)
        self.assertEqual(self.request("/api/session", INPUT | {"topic": "graphs", "notes": ""})[0], 400)
        self.assertFalse(self.app.sessions.sessions)

    def test_model_unavailable_does_not_silently_fallback(self):
        self.app.sessions.planner = Mock()
        self.app.sessions.planner.plan.side_effect = AMError("Ollama unavailable")
        status, result = self.request("/api/session", INPUT)
        self.assertEqual(status, 503)
        self.assertIn("No session was created", result["error"])
        self.assertFalse(self.app.sessions.sessions)


if __name__ == "__main__":
    unittest.main()
