"""Validate an authored Python lesson and optionally check its trusted code."""

import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path


def require(condition, message):
    """Stop with an actionable validation error."""
    if not condition:
        raise ValueError(message)


def validate_lesson(data):
    """Check lesson structure without executing its code."""
    require(isinstance(data, dict), "Lesson must be a JSON object.")
    require(data.get("schema_version") == 1, "Expected schema_version 1.")
    require(data.get("language") == "python", "This validator supports Python.")

    for field in (
        "id",
        "title",
        "instructions",
        "entrypoint",
        "starter_code",
        "reference_solution",
    ):
        value = data.get(field)
        require(
            isinstance(value, str) and bool(value.strip()),
            f"{field} must be nonempty text.",
        )

    require(
        data["entrypoint"].isidentifier(),
        "entrypoint must be a valid function name.",
    )

    for field in ("constraints", "hints", "skills"):
        value = data.get(field)
        require(
            isinstance(value, list)
            and bool(value)
            and all(isinstance(item, str) and item.strip() for item in value),
            f"{field} must be a nonempty list of strings.",
        )

    # Parse syntax and confirm the named function exists.
    # Parsing does not execute the source.
    for field in ("starter_code", "reference_solution"):
        tree = ast.parse(data[field], filename=field)
        functions = [
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        ]
        require(
            data["entrypoint"] in functions,
            f"{field} must define {data['entrypoint']}.",
        )

    tests = data.get("tests")
    require(isinstance(tests, list) and bool(tests), "Add at least one test.")

    names = set()
    for number, case in enumerate(tests, start=1):
        require(isinstance(case, dict), f"Test {number} must be an object.")
        name = case.get("name")
        require(
            isinstance(name, str) and bool(name.strip()),
            f"Test {number} needs a name.",
        )
        require(name not in names, f"Duplicate test name: {name}")
        names.add(name)

        require(
            isinstance(case.get("args"), list),
            f"{name}: args must be a list of function arguments.",
        )
        require("expected" in case, f"{name}: missing expected result.")


def equivalent(actual, expected):
    """Compare JSON-compatible values without treating True as integer 1."""
    try:
        return json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(
            expected, sort_keys=True, allow_nan=False
        )
    except (TypeError, ValueError):
        return False


def check_trusted_code(data, field):
    """Execute reviewed author code. This provides NO execution isolation."""
    namespace = {}
    exec(compile(data[field], field, "exec"), namespace)
    function = namespace[data["entrypoint"]]
    passed = 0

    print(f"\n{field}:")

    for case in data["tests"]:
        # Give each case fresh input objects.
        arguments = deepcopy(case["args"])
        original_arguments = deepcopy(arguments)

        try:
            actual = function(*arguments)
            correct_result = equivalent(actual, case["expected"])

            # This particular lesson prohibits modifying its input.
            mutation_ok = True
            if data["id"] == "python-largest-value":
                mutation_ok = equivalent(arguments, original_arguments)

            success = correct_result and mutation_ok

            print(
                f"  {'PASS' if success else 'FAIL'} {case['name']}: "
                f"expected={case['expected']!r}, actual={actual!r}"
            )

            if not mutation_ok:
                print("    Input was modified, violating the lesson contract.")

        except Exception as error:
            success = False
            print(f"  FAIL {case['name']}: {type(error).__name__}: {error}")

        passed += int(success)

    print(f"  Result: {passed}/{len(data['tests'])}")
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson", type=Path)
    parser.add_argument(
        "--check-trusted-code",
        action="store_true",
        help="Execute reviewed author code locally; NOT student submissions",
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.lesson.read_text(encoding="utf-8"))
        validate_lesson(data)
    except (OSError, ValueError, SyntaxError) as error:
        print(f"Invalid lesson: {error}")
        return 1

    print(f"Lesson structure valid: {data['title']}")
    print(f"Test cases: {len(data['tests'])}")

    if not args.check_trusted_code:
        print("Code was parsed but not executed.")
        return 0

    print("Executing trusted author code locally; no sandbox is provided.")

    try:
        reference_passes = check_trusted_code(data, "reference_solution")
        starter_passes = check_trusted_code(data, "starter_code")
    except Exception as error:
        print(f"Could not load author code: {type(error).__name__}: {error}")
        return 1

    total = len(data["tests"])

    if reference_passes != total:
        print("\nReference solution failed. Repair the lesson before publishing.")
        return 1

    if starter_passes == total:
        print("\nStarter passed everything. The tests do not expose its bug.")
        return 1

    print("\nAuthor checks passed: reference passes; starter bug is detected.")
    print("Passing these cases does not prove correctness for every input.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
