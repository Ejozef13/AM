"""Offline tests for terminal commands, history, and model lifecycle."""

import contextlib
import io
import unittest
from unittest.mock import patch

import am
import chat
from am_core import AMError


def reply(text="OK", reason="stop"):
    """Create a completed fake Ollama response."""

    return {
        "done": True,
        "message": {
            "role": "assistant",
            "content": text,
        },
        "done_reason": reason,
        "prompt_eval_count": 10,
        "eval_count": 5,
        "eval_duration": 1000000000,
        "total_duration": 2000000000,
    }


class ChatTests(unittest.TestCase):
    def session(self, inputs, responses=None, **settings):
        """Run the real chat loop with simulated input and API responses."""

        output = io.StringIO()

        with (
            patch("builtins.input", side_effect=inputs),
            patch("chat.api", side_effect=responses or []) as mocked,
            contextlib.redirect_stdout(output),
        ):
            chat.run_chat(**settings)

        return mocked, output.getvalue()

    def test_local_commands_do_not_generate(self):
        mocked, text = self.session(["", "/help", "/unknown", "/clear", "/bye"])

        mocked.assert_not_called()
        self.assertIn("Unknown command", text)
        self.assertIn("history cleared", text)

    def test_status_queries_loaded_models(self):
        mocked, text = self.session(
            ["/status", "/bye"],
            [{"models": []}],
        )

        self.assertEqual(mocked.call_args.args[0], "/api/ps")
        self.assertIn("Loaded models: none", text)

    def test_history_and_clear(self):
        mocked, _ = self.session(
            ["first", "second", "/clear", "third", "/bye"],
            [reply("one"), reply("two"), reply("three")],
        )

        second = mocked.call_args_list[1].args[1]["messages"]
        self.assertEqual(
            [message["content"] for message in second[1:]],
            ["first", "one", "second"],
        )

        self.assertEqual(second[0]["role"], "system")
        self.assertIn("Never mock intelligence", second[0]["content"])
        third = mocked.call_args_list[2].args[1]["messages"]
        self.assertEqual(
            third[1:],
            [{"role": "user", "content": "third"}],
        )

    def test_failure_recovery_preserves_history(self):
        mocked, text = self.session(
            ["failed", "good", "/bye"],
            [AMError("offline"), reply()],
        )

        recovered = mocked.call_args_list[1].args[1]["messages"]
        self.assertEqual(
            recovered[1:],
            [{"role": "user", "content": "good"}],
        )
        self.assertIn("not added", text)

    def test_malformed_response_is_not_saved(self):
        mocked, _ = self.session(
            ["bad", "good", "/bye"],
            [{"done": True}, reply()],
        )

        recovered = mocked.call_args_list[1].args[1]["messages"]
        self.assertEqual([item["role"] for item in recovered], ["system", "user"])
        self.assertEqual(recovered[-1]["content"], "good")

    def test_turn_limit_and_reset(self):
        mocked, text = self.session(
            ["one", "blocked", "/clear", "two", "/bye"],
            [reply(), reply()],
            max_turns=1,
        )

        self.assertEqual(mocked.call_count, 2)
        self.assertIn("turn limit", text)

    def test_text_budget(self):
        mocked, text = self.session(
            ["too long", "/bye"],
            char_budget=3,
        )

        mocked.assert_not_called()
        self.assertIn("Text budget exceeded", text)

    def test_context_boundary(self):
        large = reply()
        large["prompt_eval_count"] = 7000

        mocked, text = self.session(
            ["one", "blocked", "/bye"],
            [large],
        )

        self.assertEqual(mocked.call_count, 1)
        self.assertIn("approached context", text)

    def test_output_limit_warning(self):
        _, text = self.session(
            ["one", "/bye"],
            [reply(reason="length")],
        )

        self.assertIn("answer may be incomplete", text)

    def test_interrupted_request_is_not_saved(self):
        mocked, text = self.session(
            ["interrupted", "good", "/bye"],
            [KeyboardInterrupt(), reply()],
        )

        recovered = mocked.call_args_list[1].args[1]["messages"]
        self.assertEqual([item["role"] for item in recovered], ["system", "user"])
        self.assertEqual(recovered[-1]["content"], "good")
        self.assertIn("interrupted", text)

    def test_eof_exits(self):
        mocked, text = self.session([EOFError()])

        mocked.assert_not_called()
        self.assertIn("Session ended", text)


class LifecycleTests(unittest.TestCase):
    def test_on_reuses_running_service(self):
        with (
            patch("am.api", return_value={}),
            patch("am.subprocess.run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            am.start()

        run.assert_not_called()

    def test_on_starts_service_then_checks_api(self):
        with (
            patch("am.api", side_effect=[AMError("offline"), {}]),
            patch("am.subprocess.run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            am.start()

        run.assert_called_once_with(
            ["sudo", "systemctl", "start", "ollama"],
            check=True,
        )

    def test_off_unloads_only_selected_model(self):
        responses = [
            {
                "models": [
                    {"name": "gpt-oss:20b"},
                    {"name": "other"},
                ],
            },
            {},
            {"models": [{"name": "other"}]},
        ]

        with (
            patch("am.api", side_effect=responses) as mocked,
            patch("am.subprocess.run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            am.unload("gpt-oss:20b")

        run.assert_not_called()

        payload = mocked.call_args_list[1].args[1]
        self.assertEqual(payload["model"], "gpt-oss:20b")
        self.assertEqual(payload["keep_alive"], 0)

    def test_off_is_repeatable(self):
        with (
            patch("am.api", return_value={"models": []}) as mocked,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            am.unload("gpt-oss:20b")

        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
