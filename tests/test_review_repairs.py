"""Minimal regressions distilled from the uploaded live palindrome failure."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from ai_exercises import (AuthorDraftError, DraftRejected, OllamaExerciseGenerator, ReviewerTestMismatch,
                          bind_evidence, cases, note_excerpts, validate_draft)
from am_core import AMError
from code_runner import RunnerError

NOTES = ('A palindrome reads the same forward and backward. Compare all characters '
         'without changing capitalization, spaces, or punctuation. Empty and single-character strings are palindromes.')
REFERENCE = 'def is_palindrome(s: str) -> bool:\n    return s == s[::-1]\n'
REVIEWER = REFERENCE.rstrip()
STARTER = 'def is_palindrome(s: str) -> bool:\n    return s == s[::-1][1:]\n'
LITERAL = r'a\n a'


def authored():
    return {'title': 'Detect palindromes', 'instructions': NOTES, 'entrypoint': 'is_palindrome',
        'starter_code': STARTER, 'reference_solution': REFERENCE,
        'focus': 'Literal string comparison', 'reason': 'Practice the supplied palindrome definition.',
        'evidence_id': 'note-1', 'constraints': ['Accept one string and return a boolean.'],
        'skills': ['slicing'], 'hints': ['Compare the string with its reverse.'],
        'tests': [{'name': 'level', 'args': ['level'], 'expected': True},
                  {'name': 'empty', 'args': [''], 'expected': True},
                  {'name': 'case', 'args': ['Level'], 'expected': False}]}


def reviewed(wrong=True):
    return {'approved': True, 'feedback': 'Compare every literal character.', 'reference_solution': REVIEWER,
        'tests': [{'name': 'nonpalindrome', 'args': ['python'], 'expected': False},
                  {'name': 'unicode', 'args': ['😊😊'], 'expected': True},
                  {'name': 'newline symmetry', 'args': [LITERAL], 'expected': wrong}]}


def correction(value=False):
    return {'approved': True, 'feedback': 'The literal backslash, n, and space are not symmetric.',
            'corrections': [{'test_index': 2, 'expected': value}]}


def response(value):
    return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(value)}}


class PalindromeFixtureRunner:
    """Evaluate only the three explicit fixture behaviors, never exec source."""
    def __init__(self):
        self.calls = []

    def run(self, source, entrypoint, args):
        self.calls.append((source, entrypoint, deepcopy(args)))
        if source not in (REFERENCE, REVIEWER, STARTER):
            raise RunnerError('Unknown fixture source is not executable here.')
        value = args[0] == (args[0][::-1][1:] if source == STARTER else args[0][::-1])
        return {'status': 'ok', 'value': value, 'args_after': deepcopy(args)}


class ReviewRepairTests(unittest.TestCase):
    def setUp(self):
        self.runner = PalindromeFixtureRunner()
        self.generator = OllamaExerciseGenerator(self.runner)

    def build(self):
        return self.generator.build('palindromes', NOTES, 'introductory', 1)

    def test_reproduces_actual_reviewer_wrong_expected_value(self):
        lesson = validate_draft(bind_evidence(authored(), note_excerpts(NOTES)), NOTES, 'introductory')
        count = len(lesson['tests']); lesson['tests'].extend(cases(reviewed()['tests'], 'Review'))
        with self.assertRaises(ReviewerTestMismatch) as caught:
            self.generator.check_references(lesson, REVIEWER, count)
        problem = caught.exception.problems[0]
        self.assertEqual(problem['test_index'], 2)
        self.assertEqual(problem['args'], [LITERAL])
        self.assertTrue(problem['expected'])
        self.assertFalse(problem['observed_by_both'])
        self.assertEqual(problem['strings'][0]['codepoints'], [97, 92, 110, 32, 97])

    def test_bad_test_is_corrected_without_reauthoring_or_changing_source_inputs(self):
        events = []; self.generator.diagnostics = events.append
        with patch('ai_exercises.api', side_effect=[response(authored()), response(reviewed()), response(correction())]) as api:
            lessons, _, _ = self.build()
        lesson = lessons[0]
        self.assertEqual(api.call_count, 3)
        self.assertEqual(lesson['reference_solution'], REFERENCE)
        self.assertEqual(lesson['starter_code'], STARTER)
        self.assertEqual(len(lesson['tests']), 6)
        repaired = next(case for case in lesson['tests'] if 'newline symmetry' in case['name'])
        self.assertEqual(repaired['args'], [LITERAL])
        self.assertIs(repaired['expected'], False)
        self.assertEqual(lesson['quality']['review_test_repairs'], 1)
        repair_request = json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        self.assertNotIn('reference_solution', repair_request['exercise'])
        self.assertNotIn('tests', repair_request['exercise'])
        self.assertEqual(events[0]['stage'], 'review-tests')
        allowed = api.call_args_list[2].args[1]['format']['properties']['corrections']
        self.assertEqual(allowed['items']['properties']['test_index']['enum'], [2])
        self.assertEqual(allowed['minItems'], 1)
        self.assertEqual(allowed['maxItems'], 1)
        # Two failed observations, followed by two new runs with the corrected expected value.
        self.assertEqual(sum(args == [LITERAL] and source != STARTER for source, _, args in self.runner.calls), 4)

    def test_malformed_reviewer_code_repairs_only_review(self):
        bad = reviewed(False) | {'reference_solution': 'A man, a plan, a canal, Panama'}
        events = []; self.generator.diagnostics = events.append
        with patch('ai_exercises.api', side_effect=[response(authored()), response(bad), response(reviewed(False))]) as api:
            self.assertEqual(len(self.build()[0]), 1)
        followup = json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        self.assertEqual(followup['previous_review'], bad)
        self.assertIn('reviewer solution Python syntax error at line 1', followup['previous_failure'])
        self.assertEqual(events[0]['artifacts']['review']['reference_solution'], bad['reference_solution'])
        self.assertEqual(followup['exercise']['starter_code'], STARTER)
        self.assertNotIn('previous_draft', followup)

    def test_wrong_patch_cannot_bypass_execution_or_trigger_author_regeneration(self):
        with patch('ai_exercises.api', side_effect=[response(authored()), response(reviewed()), response(correction(True)),
                                                  response(reviewed()), response(correction(True))]) as api:
            with self.assertRaisesRegex(AMError, 'reviewer could not produce a consistent review'):
                self.build()
        author_calls = [call for call in api.call_args_list if 'evidence_id' in call.args[1]['format']['properties']]
        self.assertEqual(len(author_calls), 1)

    def test_declined_patch_cannot_publish(self):
        declined = correction() | {'approved': False}
        with patch('ai_exercises.api', side_effect=[response(authored()), response(reviewed()), response(declined),
                                                  response(reviewed()), response(declined)]) as api:
            with self.assertRaises(AMError):
                self.build()
        self.assertEqual(api.call_count, 3)

    def test_validation_cache_preserves_dictionary_input_order(self):
        class OrderedFixtureRunner:
            def run(self, source, entrypoint, args):
                return {'status': 'ok', 'value': list(args[0]), 'args_after': deepcopy(args)}
        self.generator.runner = OrderedFixtureRunner()
        lesson = {'entrypoint': 'keys', 'reference_solution': 'author fixture', 'tests': [
            {'name': 'Draft 1', 'args': [{'a': 1, 'b': 2}], 'expected': ['a', 'b']},
            {'name': 'Draft 2', 'args': [{'b': 2, 'a': 1}], 'expected': ['a', 'b']}]}
        with self.assertRaises(AuthorDraftError):
            self.generator.check_references(lesson, 'reviewer fixture', 2)

    def test_patch_cannot_remove_cases_change_inputs_or_correct_other_indices(self):
        problems = [{'test_index': 2}]
        for changes in ([], [{'test_index': 0, 'expected': False}],
                        [{'test_index': 2, 'expected': False, 'args': ['another input']}],
                        [{'test_index': True, 'expected': False}],
                        [{'test_index': 2, 'expected': float('nan')}]):
            with self.subTest(changes=changes), self.assertRaises(DraftRejected):
                self.generator.apply_corrections(reviewed(), correction() | {'corrections': changes}, problems)
        original = reviewed()
        fixed = self.generator.apply_corrections(original, correction(), problems)
        self.assertEqual(len(fixed['tests']), len(original['tests']))
        self.assertEqual(fixed['reference_solution'], original['reference_solution'])
        self.assertTrue(original['tests'][2]['expected'])


if __name__ == '__main__':
    unittest.main()
