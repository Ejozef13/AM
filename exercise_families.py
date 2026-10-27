"""Reviewed Python exercise families. No model-generated code or answer keys."""

import random

CATALOG = [
    {"id": "extrema", "title": "Minimum and maximum", "description":
     "Find a minimum or maximum in a nonempty integer list; initialization and boundary bugs."},
    {"id": "counting", "title": "Counting with loops", "description":
     "Count even numbers, positive numbers, or occurrences of a target; loop and counter bugs."},
    {"id": "first-index", "title": "First matching index", "description":
     "Linear search for a target; zero-based indexes, duplicate values, and absent targets."},
]
LEVELS = ("introductory", "standard", "challenging")


def generate_lesson(family, difficulty, seed):
    """Build prose, code, and tests from reviewed templates and independent oracles."""
    if family not in {item["id"] for item in CATALOG} or difficulty not in LEVELS:
        raise ValueError("Unsupported family or difficulty.")
    rng = random.Random(seed)
    bound = {"introductory": 9, "standard": 50, "challenging": 1000}[difficulty]
    size = {"introductory": 4, "standard": 8, "challenging": 18}[difficulty]
    tests = []

    def case(name, args, expected):
        tests.append({"name": name, "args": args, "expected": expected})

    if family == "extrema":
        largest = rng.choice((True, False))
        entrypoint = "largest_value" if largest else "smallest_value"
        adjective = "largest" if largest else "smallest"
        operator = ">" if largest else "<"
        oracle = max if largest else min
        bug = "zero-initialization" if difficulty == "introductory" else rng.choice(
            ("zero-initialization", "skip-last"))
        initialization = "0" if bug == "zero-initialization" else "numbers[0]"
        traversal = "numbers" if bug == "zero-initialization" else "numbers[:-1]"
        starter = (f"def {entrypoint}(numbers):\n    best = {initialization}\n"
                   f"    for number in {traversal}:\n        if number {operator} best:\n"
                   "            best = number\n    return best\n")
        reference = (f"def {entrypoint}(numbers):\n    best = numbers[0]\n"
                     f"    for number in numbers[1:]:\n        if number {operator} best:\n"
                     "            best = number\n    return best\n")
        arrays = [[-5, -2, -8], [5, 2, 8], [-7], [7], [0], [-3, 0, 4],
                  [2, 2], [3, 1, 9] if largest else [3, 9, 1],
                  [rng.randint(-bound, bound) for _ in range(size)]]
        names = ("All negative", "All positive", "Single negative", "Single positive",
                 "Zero", "Mixed signs", "Repeated values", "Extreme at the end", "Generated mixed list")
        for name, numbers in zip(names, arrays):
            case(name, [numbers], oracle(numbers))
        instructions = f"Repair {entrypoint}(numbers) to return the {adjective} integer."
        constraints = ["numbers contains 1 to 100 integers between -1000000 and 1000000.",
                       "Return the value, not its index. Do not print it or modify the input."]
        hints = ["Trace a one-element input and a list whose extreme value is last.",
                 "Check both the initial best value and the elements the loop visits.",
                 "Initialize from the first input element, then compare every remaining element."]
        regression = 0 if bug == "zero-initialization" and largest else (
            1 if bug == "zero-initialization" else 7)
        title = f"Find the {adjective} value"
        skills = ["loops", "initialization", "list boundaries"]

    elif family == "counting":
        task = rng.choice(("even", "positive", "target"))
        entrypoint = {"even": "count_even", "positive": "count_positive",
                      "target": "count_occurrences"}[task]
        signature = "numbers, target" if task == "target" else "numbers"
        condition = {"even": "number % 2 == 0", "positive": "number > 0",
                     "target": "number == target"}[task]
        bug = "initial-count" if difficulty == "introductory" else rng.choice(
            ("initial-count", "early-return", "skip-last"))
        initial = "1" if bug == "initial-count" else "0"
        traversal = "numbers[:-1]" if bug == "skip-last" else "numbers"
        starter = (f"def {entrypoint}({signature}):\n    count = {initial}\n"
                   f"    for number in {traversal}:\n        if {condition}:\n"
                   "            count += 1\n")
        if bug == "early-return":
            starter += "        return count\n"
        starter += "    return count\n"
        reference = (f"def {entrypoint}({signature}):\n    count = 0\n"
                     f"    for number in numbers:\n        if {condition}:\n"
                     "            count += 1\n    return count\n")
        target = rng.randint(-3, 3)
        matched = {"even": 2, "positive": 1, "target": target}[task]
        unmatched = {"even": 1, "positive": -1, "target": target + 1}[task]
        arrays = [[], [matched], [unmatched], [unmatched, matched],
                  [matched, matched, matched], [unmatched, unmatched],
                  [-2, -1, 0, 1, 2], [rng.randint(-bound, bound) for _ in range(size)]]
        names = ("Empty list", "Single match", "Single nonmatch", "Match at the end",
                 "Several matches", "No matches", "Negatives and zero", "Generated mixed list")
        for name, numbers in zip(names, arrays):
            args = [numbers, target] if task == "target" else [numbers]
            expected = sum(1 for n in numbers if (
                n % 2 == 0 if task == "even" else n > 0 if task == "positive" else n == target))
            case(name, args, expected)
        description = {"even": "even integers (including zero and negative evens)",
                       "positive": "strictly positive integers (zero does not count)",
                       "target": "integers equal to target"}[task]
        instructions = f"Repair {entrypoint}({signature}) to count {description}."
        constraints = ["numbers contains 0 to 100 integers between -1000000 and 1000000.",
                       "target, when supplied, is an integer in the same range.",
                       "Return an integer count. Do not print it or modify the input."]
        hints = ["Work through an empty list and a list containing several matches.",
                 "Check the initial count, the loop range, and when the function returns.",
                 "Start at zero, visit every element, and return after the loop finishes."]
        regression = 0 if bug == "initial-count" else 3
        title = {"even": "Count the even numbers", "positive": "Count positive numbers",
                 "target": "Count matching values"}[task]
        skills = ["loops", "conditions", "counters"]

    else:
        entrypoint = "first_index"
        bug = "absent-sentinel" if difficulty == "introductory" else rng.choice(
            ("absent-sentinel", "last-match", "skip-last"))
        if bug == "last-match":
            starter = ("def first_index(numbers, target):\n    found = -1\n"
                       "    for index, number in enumerate(numbers):\n"
                       "        if number == target:\n            found = index\n    return found\n")
        else:
            loop = "range(len(numbers) - 1)" if bug == "skip-last" else "range(len(numbers))"
            missing = "0" if bug == "absent-sentinel" else "-1"
            starter = (f"def first_index(numbers, target):\n    for index in {loop}:\n"
                       "        if numbers[index] == target:\n            return index\n"
                       f"    return {missing}\n")
        reference = ("def first_index(numbers, target):\n"
                     "    for index, number in enumerate(numbers):\n"
                     "        if number == target:\n            return index\n    return -1\n")
        target = rng.randint(-bound, bound)
        other = target + 1
        examples = [([], target), ([other], target), ([target], target),
                    ([target, other, target], target), ([other, target], target),
                    ([other, other], target), ([-4, 0, -4], -4),
                    ([other] * size + [target], target)]
        names = ("Empty list", "Target absent", "Single match", "Duplicate matches",
                 "Match at the end", "Repeated nonmatches", "Negative target", "Longer search")
        for name, (numbers, wanted) in zip(names, examples):
            expected = next((i for i, n in enumerate(numbers) if n == wanted), -1)
            case(name, [numbers, wanted], expected)
        instructions = "Repair first_index(numbers, target) to return the first zero-based matching index, or -1 if absent."
        constraints = ["numbers contains 0 to 100 integers between -1000000 and 1000000.",
                       "target is an integer in the same range; duplicates are allowed.",
                       "Return an index or -1. Do not print it or modify the input."]
        hints = ["Trace an absent target, a target at the final position, and duplicate matches.",
                 "Check the absent-value return, loop endpoint, and first-versus-last behavior.",
                 "Visit every index, return immediately on the first match, and return -1 after the loop."]
        regression = {"absent-sentinel": 0, "last-match": 3, "skip-last": 4}[bug]
        title, skills = "Find the first match", ["linear search", "indexes", "early return"]

    # Put a known bug-revealing case first, for a bounded starter sanity check.
    tests.insert(0, tests.pop(regression))
    return {
        "schema_version": 1, "id": f"python-{family}-{seed}", "title": title,
        "language": "python", "kind": "debugging", "difficulty": difficulty,
        "skills": skills, "instructions": instructions, "constraints": constraints,
        "entrypoint": entrypoint, "grading": {"forbid_input_mutation": True},
        "starter_code": starter, "reference_solution": reference, "hints": hints,
        "tests": tests, "generation": {"family": family, "seed": seed, "bug": bug},
    }
