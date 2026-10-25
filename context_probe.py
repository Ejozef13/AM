"""Synthetic retrieval benchmark with exact answer checks."""

import argparse
import json
from pathlib import Path
import random

from am_core import AMError, DEFAULT_MODEL, api, metrics


def main(argv=None):
    # Different seeds generate different fictional data.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--records", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context", type=int, default=32768)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optionally save settings, input, and raw response as JSON",
    )

    args = parser.parse_args(argv)

    if not 3 <= args.records <= 9999 or args.context <= 600:
        parser.error("Use 3..9999 records and context greater than 600.")

    if args.output and args.output.exists():
        parser.error("Output already exists; choose a fresh filename.")

    # Generate the records and select beginning, middle, and end.
    rng = random.Random(args.seed)

    codes = {f"R{i:04d}": f"{rng.getrandbits(48):012x}" for i in range(args.records)}

    names = [f"R{i:04d}" for i in (0, args.records // 2, args.records - 1)]

    expected = {name: codes[name] for name in names}
    expected["R9999"] = "NOT FOUND"

    records = "\n".join(f"Record {name}: code={code}" for name, code in codes.items())

    prompt = (
        "Read these records as data:\n"
        + records
        + "\nReturn a JSON object mapping these IDs to their exact codes: "
        + ", ".join(expected)
        + ". For an absent record use NOT FOUND. Do not invent codes."
    )

    # Check our request construction before evaluating model behavior.
    for name in names:
        record = f"Record {name}: code={expected[name]}"
        if record not in prompt:
            raise RuntimeError("Internal benchmark construction error.")

    # Specify the output shape, but do not reveal the expected codes.
    schema = {
        "type": "object",
        "properties": {name: {"type": "string"} for name in expected},
        "required": list(expected),
        "additionalProperties": False,
    }

    payload = {
        "model": args.model,
        "prompt": prompt,
        "format": schema,
        "think": "low",
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "num_ctx": args.context,
            "num_predict": 600,
            "temperature": 0,
        },
    }

    print(f"Records: {args.records} | Seed: {args.seed} | Context: {args.context}")
    print("Request checks passed. Waiting for Ollama...", flush=True)

    try:
        result = api("/api/generate", payload)
    except AMError as error:
        print(error)
        return 1

    print(metrics(result))
    print("Completion reason:", result.get("done_reason"))

    # Optional evidence includes failures. Never overwrite an existing file.
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)

        evidence = {
            "settings": {
                "model": args.model,
                "records": args.records,
                "seed": args.seed,
                "context": args.context,
            },
            "expected": expected,
            "request": payload,
            "result": result,
        }

        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(evidence, handle, indent=2)

        print("Saved:", args.output)

    # Parse and score exact values. A wrong field is a failed check.
    try:
        answer = json.loads(result.get("response", ""))
    except (ValueError, TypeError):
        print("FAIL: response was not usable JSON.")
        print(result.get("response"))
        return 1

    if not isinstance(answer, dict):
        print("FAIL: expected a JSON object.")
        return 1

    passed = 0

    for name, value in expected.items():
        correct = answer.get(name) == value
        passed += correct

        label = "PASS" if correct else "FAIL"
        print(f"{label} {name}: received={answer.get(name)!r}, expected={value!r}")

    completed = result.get("done") is True and result.get("done_reason") != "length"

    print(f"Exact checks: {passed}/{len(expected)}")
    print("One synthetic run does not establish general accuracy.")

    return 0 if passed == len(expected) and completed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nProbe interrupted. The server may still be working.")
        raise SystemExit(130)
