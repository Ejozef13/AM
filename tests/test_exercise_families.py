"""Reviewed author-template checks. Never execute student/model code here."""

from copy import deepcopy
import unittest

from exercise_families import CATALOG, LEVELS, generate_lesson


class FamilyTests(unittest.TestCase):
    def test_generated_reference_and_bug_regressions(self):
        # These are fixed, reviewed author templates; student source always uses Docker.
        for family in CATALOG:
            for difficulty in LEVELS:
                for seed in range(30):
                    with self.subTest(family=family["id"], difficulty=difficulty, seed=seed):
                        lesson = generate_lesson(family["id"], difficulty, seed)
                        namespace = {}
                        exec(lesson["reference_solution"], namespace)
                        function = namespace[lesson["entrypoint"]]
                        for case in lesson["tests"]:
                            args = deepcopy(case["args"])
                            self.assertEqual(function(*args), case["expected"])
                            self.assertEqual(args, case["args"])
                        starter = {}
                        exec(lesson["starter_code"], starter)
                        case = lesson["tests"][0]
                        self.assertNotEqual(starter[lesson["entrypoint"]](*deepcopy(case["args"])), case["expected"])

    def test_seed_reproduces_lesson(self):
        self.assertEqual(generate_lesson("counting", "standard", 42),
                         generate_lesson("counting", "standard", 42))

    def test_catalog_produces_distinct_tasks_and_bugs(self):
        lessons = [generate_lesson("counting", "standard", seed) for seed in range(50)]
        self.assertEqual(len({lesson["entrypoint"] for lesson in lessons}), 3)
        self.assertEqual(len({lesson["generation"]["bug"] for lesson in lessons}), 3)

    def test_rejects_unknown_family_and_difficulty(self):
        for family, level in (("graphs", "standard"), ("counting", "expert")):
            with self.assertRaises(ValueError):
                generate_lesson(family, level, 42)
