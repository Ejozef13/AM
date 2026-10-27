"""Draft boundaries, blind review, retry policy, and publication contracts."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_exercises import (DRAFT_SCHEMA, REVIEW_SCHEMA, DraftRejected, OllamaExerciseGenerator,
                          bind_evidence, note_excerpts, source_contract, validate_draft)
from am_core import AMError
from code_runner import RunnerError
from practice_planner import KeywordPlanner
from practice_sessions import SessionStore

NOTES = "Factorial multiplies the integers from 1 through n. The factorial of zero is 1."
REFERENCE = "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n"
REVIEWER = "def factorial(n):\n    result = 1\n    for number in range(1, n + 1):\n        result *= number\n    return result\n"
STARTER = REVIEWER.replace("result = 1", "result = 0 if n == 0 else 1")


def case(name, n, expected=None):
    return {"name": name, "args_json": json.dumps([n]),
            "expected_json": json.dumps(math.factorial(n) if expected is None else expected)}


def draft():
    return {"title": "Repair factorial", "instructions": "Return n factorial for integer n from 0 to 8.",
            "constraints": ["n is an integer from 0 to 8. Return an integer; do not print."],
            "skills": ["recursion", "base cases"], "entrypoint": "factorial",
            "starter_code": STARTER, "reference_solution": REFERENCE,
            "hints": ["Check the base case.", "What is zero factorial?"],
            "tests": [case("zero", 0), case("one", 1), case("five", 5)],
            "focus": "Factorial base cases", "reason": "The notes define zero factorial.",
            "evidence_id": "note-1", "notes_quote": NOTES}


def review():
    return {"approved": True, "feedback": "Task and hints agree with the supplied notes.",
            "reference_solution": REVIEWER,
            "tests": [case("two", 2), case("four", 4), case("six", 6)]}


def response(value):
    return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(value)}}


class FixtureRunner:
    """Simulate ONLY explicit fixtures; never eval model or student source."""
    def __init__(self):
        self.calls = []

    def run(self, source, entrypoint, args):
        self.calls.append((source, entrypoint, deepcopy(args)))
        if source not in (REFERENCE, REVIEWER, STARTER):
            raise RunnerError("Unknown fixture is not executable in this test double.")
        value = math.factorial(args[0])
        if source == STARTER and args[0] == 0:
            value = 0
        return {"status": "ok", "value": value, "args_after": deepcopy(args)}


class GeneratedTests(unittest.TestCase):
    def setUp(self):
        self.runner = FixtureRunner()
        self.generator = OllamaExerciseGenerator(self.runner)

    def build(self):
        return self.generator.build("factorial", NOTES, "standard", 1)

    def test_complete_blind_review_and_execution(self):
        with patch("ai_exercises.api", side_effect=[response(draft()), response(review())]) as api:
            lessons, plan, label = self.build()
        self.assertEqual(len(lessons[0]["tests"]), 6)
        self.assertEqual(lessons[0]["quality"]["reference_runs"], 12)
        self.assertFalse(lessons[0]["quality"]["distinct_models"])
        self.assertEqual(len(self.runner.calls), 13)
        payload = api.call_args_list[1].args[1]
        exercise = json.loads(payload["messages"][1]["content"])["exercise"]
        self.assertNotIn("reference_solution", exercise)
        self.assertNotIn("tests", exercise)
        self.assertNotIn("tools", payload)
        self.assertEqual(plan["notes_quote"], NOTES)

    def test_generated_quote_cannot_block_or_replace_original_evidence(self):
        raw = draft() | {"notes_quote": "A model paraphrase that is not present in the notes."}
        with patch("ai_exercises.api", side_effect=[response(raw), response(review())]) as api:
            lessons, plan, _ = self.build()
        self.assertEqual(api.call_count, 2)
        self.assertEqual(plan["notes_quote"], NOTES)
        payload = api.call_args_list[0].args[1]
        self.assertEqual(payload["format"]["properties"]["evidence_id"]["enum"], ["note-1"])
        self.assertNotIn("notes_quote", payload["format"]["properties"])
        author_data = json.loads(payload["messages"][1]["content"])
        self.assertEqual(author_data["note_excerpts"], {"note-1": NOTES})
        self.assertNotIn("notes", author_data)
        reviewer_data = json.loads(api.call_args_list[1].args[1]["messages"][1]["content"])
        self.assertEqual(reviewer_data["exercise"]["focus_plan"]["notes_quote"], NOTES)

    def test_excerpt_ids_preserve_original_unicode_whitespace_and_long_notes(self):
        notes = ("Line one.\nLine two uses ‘quotes’ and  double spaces.\n" * 400)[:12000]
        excerpts = note_excerpts(notes)
        self.assertEqual(len(excerpts), 20)
        for identifier, quote in excerpts.items():
            self.assertIn(quote, notes)
            self.assertLessEqual(len(quote), 600)
            bound = bind_evidence(draft() | {"evidence_id": identifier}, excerpts)
            self.assertEqual(bound["notes_quote"], quote)
        bound = bind_evidence(draft(), note_excerpts("abc"))
        validate_draft(bound, "abc", "standard")

    def test_no_notes_requires_no_selected_evidence(self):
        raw = draft() | {"evidence_id": ""}
        with patch("ai_exercises.api", side_effect=[response(raw), response(review())]) as api:
            _, plan, _ = self.generator.build("factorial", "", "standard", 1)
        self.assertEqual(plan["notes_quote"], "")
        self.assertEqual(api.call_args_list[0].args[1]["format"]["properties"]["evidence_id"]["enum"], [""])

    def test_invented_evidence_id_is_not_replaced_with_unrelated_material(self):
        for value in ("note-99", "", ["note-1"], None):
            with self.subTest(value=value), self.assertRaises(DraftRejected):
                bind_evidence(draft() | {"evidence_id": value}, note_excerpts(NOTES))

    def test_distinct_reviewer_is_configurable(self):
        self.generator.review_model = "other-installed-model"
        with patch("ai_exercises.api", side_effect=[response(draft()), response(review())]) as api:
            lessons, _, _ = self.build()
        self.assertEqual(api.call_args_list[1].args[1]["model"], "other-installed-model")
        self.assertTrue(lessons[0]["quality"]["distinct_models"])

    def test_model_schema_includes_local_field_limits(self):
        fields = DRAFT_SCHEMA["properties"]
        for name in ("constraints", "skills", "hints"):
            self.assertEqual(fields[name]["type"], "array")
            self.assertEqual(fields[name]["minItems"], 1)
            self.assertEqual(fields[name]["maxItems"], 6)
            self.assertEqual(fields[name]["items"]["maxLength"], 600)
        self.assertEqual(fields["title"]["maxLength"], 160)
        self.assertEqual(fields["reference_solution"]["maxLength"], 8000)
        self.assertNotIn("notes_quote", fields)
        self.assertEqual(fields["evidence_id"]["minLength"], 0)
        self.assertEqual(REVIEW_SCHEMA["properties"]["feedback"]["maxLength"], 1200)

    def test_list_limits_accept_boundaries_and_explain_rejections(self):
        for field in ("constraints", "skills", "hints"):
            for count in (1, 6):
                raw = draft() | {field: ["Valid entry"] * count}
                validate_draft(raw, NOTES, "standard")
            for value, diagnostic in (([], "0 items"), (["Entry"] * 7, "7 items"),
                                      ("One string", "str"), (None, "NoneType")):
                with self.subTest(field=field, value=value), self.assertRaises(DraftRejected) as caught:
                    validate_draft(draft() | {field: value}, NOTES, "standard")
                self.assertIn(field, str(caught.exception))
                self.assertIn(diagnostic, str(caught.exception))

    def test_constraints_retry_receives_actual_count_and_schema_bounds(self):
        bad = draft() | {"constraints": ["Requirement"] * 7}
        with patch("ai_exercises.api", side_effect=[response(bad), response(draft()), response(review())]) as api:
            self.assertEqual(len(self.build()[0]), 1)
        retry = api.call_args_list[1].args[1]
        self.assertEqual(retry["format"]["properties"]["constraints"]["maxItems"], 6)
        self.assertIn("7 items", json.loads(retry["messages"][1]["content"])["previous_failure"])
        self.assertIn("1–6", retry["messages"][0]["content"])
        self.assertEqual(json.loads(retry["messages"][1]["content"])["previous_draft"], bad)

    def test_entrypoint_metadata_is_derived_without_rewriting_code(self):
        for supplied in ("factorial(n)", "def factorial(n):", "`factorial`", " factorial ", "A factorial function", None):
            with self.subTest(supplied=supplied):
                raw = draft() | {"entrypoint": supplied}
                lesson = validate_draft(raw, NOTES, "standard")
                self.assertEqual(lesson["entrypoint"], "factorial")
                self.assertEqual(lesson["starter_code"], STARTER)
                self.assertEqual(lesson["reference_solution"], REFERENCE)

    def test_ambiguous_entrypoint_reports_actual_metadata_and_definitions(self):
        raw = draft() | {"entrypoint": "not a name",
                         "starter_code": STARTER + "\ndef helper(): return 0\n",
                         "reference_solution": REFERENCE + "\ndef helper(): return 0\n"}
        with self.assertRaises(DraftRejected) as caught:
            validate_draft(raw, NOTES, "standard")
        self.assertIn("not a name", str(caught.exception))
        self.assertIn("starter definitions=['factorial', 'helper']", str(caught.exception))

    def test_mismatched_entrypoint_definitions_are_not_guessed(self):
        raw = draft() | {"entrypoint": "factorial(n)", "starter_code": "def other(n): return 0"}
        with self.assertRaises(DraftRejected):
            validate_draft(raw, NOTES, "standard")

    def test_signature_style_metadata_completes_review_and_execution(self):
        raw = draft() | {"entrypoint": "factorial(n)"}
        with patch("ai_exercises.api", side_effect=[response(raw), response(review())]) as api:
            lessons, _, _ = self.build()
        self.assertEqual(lessons[0]["entrypoint"], "factorial")
        reviewer_input = json.loads(api.call_args_list[1].args[1]["messages"][1]["content"])
        self.assertEqual(reviewer_input["exercise"]["entrypoint"], "factorial")

    def test_optional_diagnostics_exclude_full_notes_and_source(self):
        events = []
        self.generator.diagnostics = events.append
        raw = draft() | {"constraints": []}
        with patch("ai_exercises.api", side_effect=[response(raw), response(draft()), response(review())]):
            self.build()
        self.assertEqual(events[0]["lists"]["constraints"]["count"], 0)
        self.assertEqual(events[0]["author_functions"], ["factorial"])
        self.assertNotIn("notes", events[0])
        self.assertNotIn(REFERENCE, events[0].values())

    def test_signature_errors_identify_role_and_exact_unsupported_feature(self):
        for source, feature in (
                ("@staticmethod\ndef factorial(n): return 1", "decorators: staticmethod"),
                ("def factorial(*, n): return 1", "required keyword-only parameters: n"),
                ("def factorial(*numbers): return 1", "*numbers"),
                ("def factorial(**options): return 1", "**options")):
            with self.subTest(source=source), self.assertRaises(DraftRejected) as caught:
                source_contract(source, "factorial", "reviewer solution")
            self.assertIn("reviewer solution", str(caught.exception))
            self.assertIn(feature, str(caught.exception))
            self.assertIn("def factorial(", str(caught.exception))

    def test_callable_positional_signatures_are_accepted(self):
        for signature in ("n", "n: int", "n, /", "n=0", "n, *, debug=False"):
            with self.subTest(signature=signature):
                self.assertEqual(source_contract(f"def factorial({signature}): return 1", "factorial"), 1)

    def test_bad_signature_retry_receives_actionable_feedback(self):
        bad = draft() | {"reference_solution": "def factorial(*, n): return 1"}
        with patch("ai_exercises.api", side_effect=[response(bad), response(draft()), response(review())]) as api:
            self.assertEqual(len(self.build()[0]), 1)
        retry = json.loads(api.call_args_list[1].args[1]["messages"][1]["content"])
        self.assertIn("author solution", retry["previous_failure"])
        self.assertIn("required keyword-only parameters: n", retry["previous_failure"])
        for call in (api.call_args_list[0], api.call_args_list[2]):
            self.assertIn("Do not use decorators", call.args[1]["messages"][0]["content"])

    def test_reviewer_signature_error_survives_to_final_diagnostic(self):
        bad = review() | {"reference_solution": "@staticmethod\n" + REVIEWER}
        with patch("ai_exercises.api", side_effect=[response(draft()), response(bad)] * 2):
            with self.assertRaisesRegex(AMError, "reviewer solution.*decorators: staticmethod"):
                self.build()

    def test_disagreement_retries_then_rejects(self):
        bad = review(); bad["tests"][0]["expected_json"] = "123"
        with patch("ai_exercises.api", side_effect=[response(draft()), response(bad)] * 2) as api:
            with self.assertRaisesRegex(AMError, "after two drafts"):
                self.build()
        retry = json.loads(api.call_args_list[2].args[1]["messages"][1]["content"])
        self.assertIn("disagree", retry["previous_failure"])

    def test_review_rejection_can_be_repaired(self):
        rejected = review() | {"approved": False, "feedback": "Clarify the zero case."}
        with patch("ai_exercises.api", side_effect=[response(draft()), response(rejected),
                                                    response(draft()), response(review())]):
            self.assertEqual(len(self.build()[0]), 1)

    def test_unreachable_model_does_not_retry_or_publish(self):
        store = SessionStore(KeywordPlanner(), self.runner, self.generator)
        with patch("ai_exercises.api", side_effect=AMError("Cannot reach Ollama")) as api:
            with self.assertRaises(AMError):
                store.create({"language": "python", "topic": "factorial", "notes": NOTES, "count": 1})
        self.assertEqual(api.call_count, 1)
        self.assertFalse(store.sessions)

    def test_runner_infrastructure_error_does_not_retry(self):
        with patch("ai_exercises.api", side_effect=[response(draft()), response(review())]) as api:
            with patch.object(self.runner, "run", side_effect=RunnerError("Docker unavailable")):
                with self.assertRaises(RunnerError):
                    self.build()
        self.assertEqual(api.call_count, 2)

    def test_no_bug_is_not_published(self):
        raw = draft() | {"starter_code": REFERENCE}
        with patch("ai_exercises.api", side_effect=[response(raw), response(review())] * 2):
            with self.assertRaisesRegex(AMError, "no intended bug"):
                self.build()

    def test_malformed_evidence_and_json_are_rejected_before_execution(self):
        for change in ({"notes_quote": "invented quote"}, {"starter_code": "bad syntax !"},
                       {"hints": []}, {"tests": []}):
            with self.subTest(change=change), self.assertRaises(DraftRejected):
                validate_draft(draft() | change, NOTES, "standard")
        for encoded in ("NaN", "Infinity", "[" * 20 + "0" + "]" * 20):
            raw = draft(); raw["tests"][0]["expected_json"] = encoded
            with self.assertRaises(DraftRejected):
                validate_draft(raw, NOTES, "standard")
        self.assertFalse(self.runner.calls)

    def test_parsing_never_executes_reference_on_host(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            raw = draft() | {"reference_solution":
                f"from pathlib import Path\nPath({str(marker)!r}).touch()\n" + REFERENCE}
            validate_draft(raw, NOTES, "standard")
            self.assertFalse(marker.exists())

    def test_incomplete_generation_has_bounded_retries(self):
        with patch("ai_exercises.api", return_value={"done": True, "done_reason": "length"}) as api:
            with self.assertRaises(AMError):
                self.build()
        self.assertEqual(api.call_count, 2)

    def test_partial_session_not_published_when_later_question_fails(self):
        store = SessionStore(KeywordPlanner(), self.runner, self.generator)
        with patch("ai_exercises.api", side_effect=[response(draft()), response(review()),
                                                    response({}), response({})]):
            with self.assertRaises(AMError):
                store.create({"language": "python", "topic": "factorial", "notes": NOTES, "count": 2})
        self.assertFalse(store.sessions)


if __name__ == "__main__":
    unittest.main()
