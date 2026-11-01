"""Regression-only model fixtures for the uploaded C contract/starter failures."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from ai_exercises import DraftRejected, OllamaExerciseGenerator, bind_evidence, note_excerpts, validate_draft
from code_runner import RunnerError
from test_ai_exercises import FixtureRunner, NOTES, REFERENCE, STARTER, draft, response
from test_multilanguage_generation import NativeFixtureRunner, native_draft, native_review, reply


class RecoveryTests(unittest.TestCase):
    def test_model_repairs_array_object_and_overflow_without_changing_task(self):
        for malformed in ({'arg0': [3], 'arg0_len': 1}, [3]):
            with self.subTest(malformed=malformed):
                raw = native_draft('c')
                original = deepcopy(raw)
                raw['tests'][0]['args'] = [malformed]
                if isinstance(malformed, list):
                    raw['tests'][0]['expected'] = 2147483648
                generator = OllamaExerciseGenerator(NativeFixtureRunner('c'), language='c')
                with patch('ai_exercises.api', return_value=reply({'tests': original['tests']})) as api:
                    result = generator.prepare_native_tests(raw, 'run', 1, 1)
                self.assertEqual(result, original)
                self.assertNotEqual(raw, original)
                request = json.loads(api.call_args.args[1]['messages'][1]['content'])
                self.assertEqual(request['previous_tests'], raw['tests'])
                self.assertNotIn('reference_solution', request)
                self.assertEqual(api.call_args.args[1]['format']['properties']['tests']['items']['properties']['args']['maxItems'], 1)

    def test_ambiguous_length_inside_array_is_never_silently_removed(self):
        raw = native_draft('c')
        raw['tests'][0]['args'] = [[42, 1]]
        generator = OllamaExerciseGenerator(NativeFixtureRunner('c'), language='c')
        with patch('ai_exercises.api') as api:
            result = generator.prepare_native_tests(raw, 'run', 1, 1)
        self.assertEqual(result['tests'][0]['args'], [[42, 1]])
        api.assert_not_called()  # Shape alone cannot establish what the user/model intended.

    def test_invalid_test_repair_is_bounded_and_cannot_publish(self):
        raw = native_draft('c')
        raw['tests'][0]['args'] = [{'arg0': [], 'arg0_len': 0}]
        generator = OllamaExerciseGenerator(NativeFixtureRunner('c'), language='c')
        with patch('ai_exercises.api', return_value=reply({'tests': raw['tests']})) as api:
            with self.assertRaisesRegex(DraftRejected, 'Native test repair failed'):
                generator.prepare_native_tests(raw, 'run', 1, 1)
        self.assertEqual(api.call_count, 1)

    def test_repaired_native_tests_still_run_both_references_and_starter(self):
        original = native_draft('c')
        raw = deepcopy(original)
        raw['tests'][0]['args'] = [{'arg0': [-8, -3], 'arg0_len': 2}]
        runner = NativeFixtureRunner('c')
        generator = OllamaExerciseGenerator(runner, language='c')
        with patch('ai_exercises.api', side_effect=[reply(raw), reply({'tests': original['tests']}), reply(native_review('c'))]):
            lessons, _, _ = generator.build('arrays', '', 'standard', 1)
        self.assertEqual(len(lessons), 1)
        # Identical author/reviewer source shares the existing execution cache.
        self.assertEqual(len(runner.calls), 12)
        self.assertEqual(sum(source == original['reference_solution'] for source, _, _ in runner.calls), 6)
        self.assertEqual(sum(source == original['starter_code'] for source, _, _ in runner.calls), 6)
        self.assertEqual(lessons[0]['starter_code'], original['starter_code'])
        self.assertEqual(lessons[0]['reference_solution'], original['reference_solution'])

    def starter_setup(self):
        raw = draft()
        raw['starter_code'] = REFERENCE  # A repaired starter with no bug must be rejected.
        lesson = validate_draft(bind_evidence(raw, note_excerpts(NOTES)), NOTES, 'standard')
        generator = OllamaExerciseGenerator(FixtureRunner())
        return raw, lesson, generator

    def test_correct_starter_is_rejected_then_safe_bug_gets_blind_review(self):
        raw, lesson, generator = self.starter_setup()
        patches = [response({'starter_code': REFERENCE, 'hints': raw['hints']}),
                   response({'starter_code': STARTER, 'hints': raw['hints']}),
                   response({'approved': True, 'feedback': 'The starter has a safe semantic bug.'})]
        with patch('ai_exercises.api', side_effect=patches) as api:
            generator.prepare_starter(lesson, 'recursion', NOTES, raw, None, 'run', 1, 1)
        self.assertEqual(lesson['starter_code'], STARTER)
        second = json.loads(api.call_args_list[1].args[1]['messages'][1]['content'])
        self.assertIn('passed every test', second['previous_failure'])
        blind = json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        self.assertNotIn('reference_solution', blind)
        self.assertNotIn('tests', blind)
        self.assertEqual(raw['starter_code'], REFERENCE)

    def test_crashing_starter_repair_requires_a_remaining_bug(self):
        raw, lesson, generator = self.starter_setup()
        original_run = generator.runner.run
        crash_source = raw['starter_code'] + '# simulated unsafe starter\n'
        raw['starter_code'] = crash_source
        lesson['starter_code'] = crash_source
        def run(source, entrypoint, args):
            if source == crash_source:
                return {'status': 'runtime_error', 'message': 'out-of-bounds access'}
            return original_run(source, entrypoint, args)
        generator.runner.run = run
        with patch('ai_exercises.api', side_effect=[
                response({'starter_code': REFERENCE, 'hints': raw['hints']}),
                response({'starter_code': STARTER, 'hints': raw['hints']}),
                response({'approved': True, 'feedback': 'Safe semantic bug and matching hints.'})]) as api:
            generator.prepare_starter(lesson, 'recursion', NOTES, raw, None, 'run', 1, 1)
        first = json.loads(api.call_args_list[0].args[1]['messages'][1]['content'])
        second = json.loads(api.call_args_list[1].args[1]['messages'][1]['content'])
        self.assertIn('runtime_error', first['previous_failure'])
        self.assertIn('passed every test', second['previous_failure'])
        self.assertEqual(lesson['starter_code'], STARTER)

    def test_blind_rejection_is_fed_back_and_repair_exhaustion_rejects(self):
        raw, lesson, generator = self.starter_setup()
        candidate = response({'starter_code': STARTER, 'hints': raw['hints']})
        rejection = response({'approved': False, 'feedback': 'Hints are inconsistent.'})
        with patch('ai_exercises.api', side_effect=[candidate, rejection, candidate, rejection]) as api:
            with self.assertRaisesRegex(DraftRejected, 'Starter repair exhausted'):
                generator.prepare_starter(lesson, 'recursion', NOTES, raw, None, 'run', 1, 1)
        second = json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        self.assertIn('Hints are inconsistent', second['previous_failure'])
        self.assertEqual(lesson['starter_code'], REFERENCE)

    def test_infrastructure_errors_abort_without_model_repair(self):
        raw, lesson, generator = self.starter_setup()
        with patch.object(generator, 'check_starter', side_effect=RunnerError('Docker unavailable')), patch('ai_exercises.api') as api:
            with self.assertRaises(RunnerError):
                generator.prepare_starter(lesson, 'recursion', NOTES, raw, None, 'run', 1, 1)
        api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
