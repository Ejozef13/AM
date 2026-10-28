"""A mistyped AI expected string must not discard two correct executable solutions."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from ai_exercises import AuthorDraftError, OllamaExerciseGenerator
from code_runner import RunnerError
from test_multilanguage_generation import native_draft, native_review, reply

REFERENCE='public class Solution { public static String solve(String arg0) { return new StringBuilder(arg0).reverse().toString(); } }'
REVIEWER='public class Solution { public static String solve(String arg0) { char[] a=arg0.toCharArray(); for(int i=0,j=a.length-1;i<j;i++,j--){char c=a[i];a[i]=a[j];a[j]=c;} return new String(a); } }'
STARTER='public class Solution { public static String solve(String arg0) { return arg0; } }'


class ReverseRunner:
    def __init__(self): self.calls=[]
    def with_signature(self, signature): return self
    def run(self,source,entrypoint,args):
        if source not in (REFERENCE,REVIEWER,STARTER): raise RunnerError('Unknown fixture source')
        self.calls.append((source,deepcopy(args)))
        return {'status':'ok','value':args[0] if source==STARTER else args[0][::-1],'args_after':deepcopy(args)}


def draft():
    raw=native_draft('java')
    raw.update(title='Reverse text',instructions='Return the entire input string in reverse order, preserving spaces.',
        constraints=['Accept one ASCII string, including empty text.'],focus='Text order',
        starter_code=STARTER,reference_solution=REFERENCE,signature={'parameters':['string'],'returns':'string'},
        tests=[{'name':'empty','args':[''],'expected':''},
               {'name':'word','args':['abc'],'expected':'cba'},
               {'name':'spaces','args':['Hello World'],'expected':'drloW olleH'}])
    return raw


def review():
    raw=native_review('java'); raw.update(reference_solution=REVIEWER,
        tests=[{'name':'single','args':['x'],'expected':'x'},
               {'name':'spaces','args':[' x '],'expected':' x '},
               {'name':'another word','args':['abcd'],'expected':'dcba'}])
    return raw


class AuthorExpectationTests(unittest.TestCase):
    def test_uploaded_failure_recovers_after_semantic_approval_without_changing_code_or_input(self):
        runner=ReverseRunner(); generator=OllamaExerciseGenerator(runner,language='java')
        approval={'approved':True,'feedback':'The observed order matches the stated reversal.','confirmed_indices':[2]}
        with patch('ai_exercises.api',side_effect=[reply(draft()),reply(review()),reply(approval)]) as api:
            lessons,_,_=generator.build('text output','','standard',1)
        lesson=lessons[0]; fixed=next(case for case in lesson['tests'] if case['args']==['Hello World'])
        self.assertEqual(fixed['expected'],'dlroW olleH')
        self.assertEqual(lesson['starter_code'],STARTER)
        self.assertEqual(lesson['reference_solution'],REFERENCE)
        self.assertEqual(lesson['quality']['review_test_repairs'],1)
        request=json.loads(api.call_args_list[2].args[1]['messages'][1]['content'])
        evidence=request['inconsistent_tests'][0]
        self.assertEqual(evidence['owner'],'author')
        self.assertEqual(evidence['expected'],'drloW olleH')
        self.assertEqual(evidence['observed_by_both'],'dlroW olleH')
        self.assertEqual(sum(source!=STARTER and args==['Hello World'] for source,args in runner.calls),4)
        self.assertEqual(api.call_count,3)

    def test_disagreement_between_programs_cannot_be_corrected_as_a_typo(self):
        class Disagree(ReverseRunner):
            def run(self,source,entrypoint,args):
                result=super().run(source,entrypoint,args)
                if source==REFERENCE: result['value']='wrong'
                return result
        generator=OllamaExerciseGenerator(Disagree(),language='java')
        lesson={'entrypoint':'solve','reference_solution':REFERENCE,
                'tests':[{'name':'case','args':['abc'],'expected':'cba'}]}
        with self.assertRaises(AuthorDraftError): generator.check_references(lesson,REVIEWER,1)

# Opt in for the uploaded failure through actual Java compilation/execution.
import os
from pathlib import Path
from compiled_runner import CompiledRunner
from ai_exercises import TestExpectationMismatch


@unittest.skipUnless(os.environ.get('AM_EXPECTATION_TESTS')=='1','Set AM_EXPECTATION_TESTS=1 for the Java typo regression.')
class JavaExpectationContainerTests(unittest.TestCase):
    def test_real_program_agreement_and_approval_recover_the_uploaded_expected_typo(self):
        root=Path(__file__).resolve().parents[1]
        command=('docker',) if os.environ.get('AM_DOCKER_DIRECT')=='1' else ('sudo','-n','docker')
        runner=CompiledRunner((root/'.am-runtime/compiled-image.txt').read_text().strip(),'java',
                             {'parameters':['string'],'returns':'string'},command,wall_seconds=180)
        generator=OllamaExerciseGenerator(runner,language='java')
        lesson={'entrypoint':'solve','reference_solution':REFERENCE,'starter_code':STARTER,
                'tests':[{'name':'spaces','args':['Hello World'],'expected':'drloW olleH'}]}
        with self.assertRaises(TestExpectationMismatch) as caught:
            generator.check_references(lesson,REVIEWER,1)
        self.assertEqual(caught.exception.problems[0]['observed_by_both'],'dlroW olleH')
        approved={'approved':True,'feedback':'The observed character order agrees with the task.','confirmed_indices':[0]}
        patched=generator.apply_corrections({'tests':lesson['tests']},approved,caught.exception.problems)
        lesson['tests']=patched['tests']
        generator.check_references(lesson,REVIEWER,1)
        generator.check_starter(lesson)
        self.assertEqual(lesson['tests'][0]['args'],['Hello World'])
