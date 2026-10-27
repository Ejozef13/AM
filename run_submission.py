"""Grade a Python submission in Docker, never in this host process."""

import argparse
import json
from pathlib import Path

from code_runner import DockerRunner, RunnerError, grade_case

ROOT = Path(__file__).resolve().parent


def load_lesson(path):
    """Validate the fields needed by this runner."""
    lesson = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(lesson, dict) or lesson.get("language") != "python":
        raise ValueError("Expected a Python lesson object.")

    entrypoint = lesson.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.isidentifier():
        raise ValueError("Lesson needs a valid entrypoint.")

    tests = lesson.get("tests")
    if not isinstance(tests, list) or not 1 <= len(tests) <= 32:
        raise ValueError("Expected 1 to 32 reviewed test cases.")

    for case in tests:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("name"), str)
            or not isinstance(case.get("args"), list)
            or "expected" not in case
        ):
            raise ValueError("Malformed test case.")

    grading = lesson.get("grading")
    if (
        not isinstance(grading, dict)
        or type(grading.get("forbid_input_mutation")) is not bool
    ):
        raise ValueError('Add grading: {"forbid_input_mutation": true} to this lesson.')

    return lesson


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson", type=Path)
    parser.add_argument("submission", type=Path)
    args = parser.parse_args()

    try:
        lesson = load_lesson(args.lesson)

        image = (ROOT / "infrastructure/python-runner-image.txt").read_text().strip()

        runner = DockerRunner(image)
        source = args.submission.read_text(encoding="utf-8")
        passed = 0

        print(
            "Each test runs in a fresh restricted container. No AI grading.",
            flush=True,
        )

        for case in lesson["tests"]:
            result = grade_case(
                runner,
                source,
                lesson["entrypoint"],
                case,
                lesson["grading"]["forbid_input_mutation"],
            )

            print(
                f"{result['status'].upper()} {case['name']}",
                flush=True,
            )

            if result["status"] in {"passed", "failed"}:
                print(
                    f"  Expected: {result['expected']!r}; actual: {result['actual']!r}"
                )

                if result["input_modified"]:
                    print("  Submission modified its input.")

            else:
                print(
                    " ",
                    result.get("message", "Execution failed."),
                )

            if result.get("output"):
                print(
                    "  Submission output:",
                    repr(result["output"]),
                )

            passed += result["status"] == "passed"

        total = len(lesson["tests"])
        print(f"\nPassed {passed}/{total} reviewed cases.")
        print("Passing this suite is not a proof for every possible input.")

        return 0 if passed == total else 1

    except (OSError, ValueError, RunnerError) as error:
        print("RUNNER ERROR:", error)
        print("No overall submission grade is available.")
        return 2

    except KeyboardInterrupt:
        print("\nInterrupted. Runner cleanup was attempted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
