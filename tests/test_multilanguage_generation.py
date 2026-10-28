"""All generation/review routes with fixed native fixtures, never host compilation."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from ai_exercises import DraftRejected, OllamaExerciseGenerator, validate_draft
from code_runner import RunnerError
from language_contracts import function_header, validate_signature
from practice_sessions import SessionStore
from practice_web import PracticeApp
from pathlib import Path

SIGNATURE = {'parameters': ['int_array'], 'returns': 'int'}
SOURCES = {
 'c': 'int solve(const int *arg0, int arg0_len) { int best=arg0[0]; for(int i=1;i<arg0_len;i++) if(arg0[i]>best) best=arg0[i]; return best; }',
 'cpp': 'int solve(const std::vector<int>& arg0) { int best=arg0[0]; for(int value:arg0) if(value>best) best=value; return best; }',
 'java': 'public class Solution { public static int solve(int[] arg0) { int best=arg0[0]; for(int value:arg0) if(value>best) best=value; return best; } }',
}


def native_draft(language):
 source = SOURCES[language]
 return {'title': 'Find the largest value', 'instructions': 'Return the largest value of a nonempty integer array.',
    'constraints': ['The array has 1 to 100 integers. Return a value without changing the array.'],
    'skills': ['arrays', 'initialization'], 'hints': ['Try all-negative inputs.'],
    'focus': 'Array traversal', 'reason': 'Practice maximum finding.', 'evidence_id': '',
    'entrypoint': 'solve', 'signature': SIGNATURE, 'starter_code': source.replace('best=arg0[0]', 'best=0'),
    'reference_solution': source, 'tests': [
        {'name': 'negative', 'args': [[-8, -3]], 'expected': -3},
        {'name': 'single', 'args': [[-7]], 'expected': -7},
        {'name': 'positive', 'args': [[3, 8, 2]], 'expected': 8}]}


def native_review(language):
 return {'approved': True, 'feedback': 'The nonempty-array specification is clear.', 'reference_solution': SOURCES[language],
    'tests': [{'name': 'zero', 'args': [[0]], 'expected': 0},
              {'name': 'duplicates', 'args': [[4,4]], 'expected': 4},
              {'name': 'last', 'args': [[2,9]], 'expected': 9}]}


def reply(value):
 return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(value)}}


class NativeFixtureRunner:
 def __init__(self, language):
  self.language = language; self.signature = None; self.calls = []
 def with_signature(self, signature):
  self.signature = validate_signature(self.language, signature); return self
 def run(self, source, entrypoint, args):
  self.calls.append((source, entrypoint, deepcopy(args)))
  draft = native_draft(self.language)
  if source not in (draft['starter_code'], draft['reference_solution']):
   return {'status': 'compile_error', 'message': 'Fixture source is not compiled on this host.'}
  value = max(args[0]) if source == draft['reference_solution'] else max(0, *args[0])
  return {'status': 'ok', 'value': value, 'args_after': deepcopy(args)}


class NativeGenerationTests(unittest.TestCase):
 def test_every_native_language_routes_through_generation_review_and_grading(self):
  for language in SOURCES:
   with self.subTest(language=language):
    py = Mock(); native = NativeFixtureRunner(language)
    runtimes = {'python': py, language: native}
    generator = OllamaExerciseGenerator(py, runtimes=runtimes)
    store = SessionStore(generator)
    with patch('ai_exercises.api', side_effect=[reply(native_draft(language)), reply(native_review(language))]) as api:
     key, session = store.create({'language': language, 'topic': 'array maximum', 'notes': '', 'count': 1})
    lesson = session.lessons[0]
    self.assertEqual(lesson['language'], language)
    self.assertEqual(lesson['required_signature'], function_header(language, SIGNATURE))
    self.assertIn('signature', api.call_args_list[0].args[1]['format']['required'])
    review_task = json.loads(api.call_args_list[1].args[1]['messages'][1]['content'])['exercise']
    self.assertEqual(review_task['signature'], SIGNATURE)
    self.assertNotIn('reference_solution', review_task)
    app = PracticeApp(py, generator=generator, runtimes=runtimes)
    app.sessions = store
    result = app.run(lesson['reference_solution'], {'session_id': key, 'lesson_index': 0})
    self.assertEqual(result['passed'], 6)
    wrong = app.run('invalid native source', {'session_id': key, 'lesson_index': 0})
    self.assertEqual(wrong['passed'], 0)
    self.assertEqual(wrong['results'][0]['status'], 'compile_error')
    py.run.assert_not_called()

 def test_native_cases_cannot_smuggle_wrong_types_into_harness(self):
  for language in SOURCES:
   bad = native_draft(language)
   bad['tests'][0]['args'] = ['not an array']
   with self.subTest(language=language), self.assertRaises(DraftRejected):
    validate_draft({**bad, 'notes_quote': ''}, '', 'standard', language)



if __name__ == '__main__':
 unittest.main()
