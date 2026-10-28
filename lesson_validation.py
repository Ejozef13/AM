"""Structural checks and strict JSON comparisons; never execute generated code."""

import ast
import json


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
