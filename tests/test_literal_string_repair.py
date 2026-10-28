"""Literal string failures must carry actual input evidence into author repair."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from ai_exercises import AuthorDraftError, OllamaExerciseGenerator
from language_contracts import validate_signature
from test_multilanguage_generation import native_draft, native_review, reply

REFERENCE = 'public class Solution { public static int solve(String arg0) { return arg0.length(); } }'
REVIEWER = 'public class Solution { public static int solve(String arg0) { return arg0.toCharArray().length; } }'
STARTER = REFERENCE.replace('arg0.length()', 'arg0.length()+1')


class LengthRunner:
    def with_signature(self, signature):
        self.signature = validate_signature('java', signature)
        return self

    def run(self, source, entrypoint, args):
        if source not in (REFERENCE, REVIEWER, STARTER):
            raise AssertionError('Unexpected fixture source')
        return {'status':'ok','value':len(args[0])+(source==STARTER),'args_after':deepcopy(args)}


def author():
    raw=native_draft('java')
    raw.update(title='String length',instructions='Return the number of literal characters in a string.',
               constraints=['Accept one ASCII string, including the empty string.'],
               hints=['Check how the return value changes for empty input.'],
               signature={'parameters':['string'],'returns':'int'},starter_code=STARTER,reference_solution=REFERENCE,
               tests=[{'name':'empty string','args':['""'],'expected':0},
                      {'name':'one','args':['a'],'expected':1},
                      {'name':'several','args':['abc'],'expected':3}])
    return raw


def review():
    checked=native_review('java')
    checked.update(reference_solution=REVIEWER,tests=[
        {'name':'empty','args':[''],'expected':0},
        {'name':'literal quotes','args':['""'],'expected':2},
        {'name':'literal backslash n','args':[r'\n'],'expected':2}])
    return checked


class LiteralRepairTests(unittest.TestCase):
    def test_empty_and_literal_quotes_are_not_normalized_and_retry_receives_character_evidence(self):
        runner=LengthRunner(); events=[]
        generator=OllamaExerciseGenerator(runner,language='java',diagnostics=events.append)
        broken=author(); repaired=deepcopy(broken); repaired['tests'][0]['args']=['']
        with patch('ai_exercises.api',side_effect=[reply(broken),reply(review()),reply(repaired),reply(review())]) as api:
            lessons,_,_=generator.build('String handling','','standard',1)
        request=json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        self.assertEqual(request['previous_draft']['tests'][0]['args'],['""'])
        self.assertIn('"length": 2',request['previous_failure'])
        self.assertIn('"codepoints": [34, 34]',request['previous_failure'])
        self.assertIn('"expected": 0',request['previous_failure'])
        self.assertIn('"actual": 2',request['previous_failure'])
        self.assertTrue(any(case['args']==[''] and case['expected']==0 for case in lessons[0]['tests']))
        self.assertTrue(any(case['args']==['""'] and case['expected']==2 for case in lessons[0]['tests']))
        self.assertEqual(api.call_count,4)
        self.assertIsInstance(next(event for event in events if event['stage']=='author')['error'],str)
