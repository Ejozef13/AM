"""Uploaded failure regression; fixtures are never used by the application."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_exercises import DraftRejected, OllamaExerciseGenerator, validate_draft
from code_runner import RunnerError
from test_multilanguage_generation import native_draft, reply

REFERENCE = 'public class Solution { public static int solve(int[] arg0) { int sum=0; for(int i=0;i<arg0.length;i++) if(arg0[i]%2==0) sum+=arg0[i]; return sum; } }'
CRASH = REFERENCE.replace('i<arg0.length','i<=arg0.length')
SAFE_BUG = REFERENCE.replace('sum=0','sum=1')
REVIEWER = 'public class Solution { public static int solve(int[] arg0) { int result=0; for(int item:arg0) if(item%2==0) result+=item; return result; } }'
CASES = [{'name':'empty','args':[[]],'expected':0},
         {'name':'mixed','args':[[1,2,3,4]],'expected':6},
         {'name':'odd','args':[[7]],'expected':0}]
APPROVAL = {'approved':True,'feedback':'The safe logic bug and refreshed hints match the unchanged task.'}


def draft():
    return native_draft('java') | {
        'title':'Sum even values','instructions':'Sum all even array elements. Empty arrays return zero. Do not mutate inputs.',
        'constraints':['0 to 100 signed 32-bit integers; the sum fits a signed 32-bit integer.'],
        'focus':'Loops','reason':'Practice array traversal and conditions.',
        'starter_code':CRASH,'reference_solution':REFERENCE,
        'hints':['Consider loop boundaries.'],'tests':deepcopy(CASES)}


def reviewed():
    return {'approved':True,'feedback':'The return contract and valid domain are clear.',
            'reference_solution':REVIEWER,'tests':[
                {'name':'negative even','args':[[-2,4,5]],'expected':2},
                {'name':'single even','args':[[8]],'expected':8},
                {'name':'zeros','args':[[0,0]],'expected':0}]}


def repaired(source=SAFE_BUG):
    return {'starter_code':source,'hints':['Trace the accumulator before the first iteration.'],
            'reason':'Practice tracing a running sum through a loop.'}


class ArrayRunner:
    def __init__(self): self.calls=[]
    def with_signature(self,signature): return self
    def run(self,source,entrypoint,args):
        self.calls.append((source,deepcopy(args)))
        if source==CRASH: return {'status':'runtime_error','message':'Index 0 out of bounds for length 0'}
        if source not in (REFERENCE,REVIEWER,SAFE_BUG): raise AssertionError('Unexpected fixture source')
        return {'status':'ok','value':sum(item for item in args[0] if item%2==0)+(source==SAFE_BUG),
                'args_after':deepcopy(args)}


class FocusedRepairTests(unittest.TestCase):
    def test_wrong_test_types_then_crashing_starter_recover_without_rewriting_task(self):
        raw=draft()
        raw['tests'][0]['args']=[{'__am_text__':[]}]
        runner=ArrayRunner(); events=[]
        generator=OllamaExerciseGenerator(runner,language='java',diagnostics=events.append)
        answers=[raw,{'tests':CASES},reviewed(),repaired(),APPROVAL]
        with patch('ai_exercises.api',side_effect=[reply(value) for value in answers]) as api:
            lessons,_,_=generator.build('loops','','introductory',1)
        lesson=lessons[0]
        self.assertEqual(api.call_count,5)
        for field in ('instructions','constraints','reference_solution','signature'):
            self.assertEqual(lesson[field],raw[field])
        self.assertEqual(lesson['starter_code'],SAFE_BUG)
        self.assertEqual(lesson['quality']['starter_repairs'],1)
        self.assertEqual(len(lesson['tests']),6)
        self.assertEqual([event['stage'] for event in events],['author-tests','starter'])
        test_schema=api.call_args_list[1].args[1]['format']['properties']['tests']['items']['properties']
        self.assertEqual(test_schema['args']['prefixItems'][0]['type'],'array')
        self.assertEqual(test_schema['expected']['type'],'integer')
        repair_data=json.loads(api.call_args_list[3].args[1]['messages'][1]['content'])
        self.assertIn('empty',repair_data['failure'])
        recheck_data=json.loads(api.call_args_list[4].args[1]['messages'][1]['content'])
        self.assertNotIn('reference_solution',recheck_data['exercise'])
        self.assertNotIn('tests',recheck_data['exercise'])
        safe_calls=[args for source,args in runner.calls if source==SAFE_BUG]
        self.assertEqual(len(safe_calls),6)
        self.assertIn([[]],safe_calls)

    def test_starter_gets_two_focused_repairs_without_regenerating_references_or_tests(self):
        runner=ArrayRunner(); generator=OllamaExerciseGenerator(runner,language='java')
        answers=[draft(),reviewed(),repaired(CRASH),APPROVAL,repaired(),APPROVAL]
        with patch('ai_exercises.api',side_effect=[reply(value) for value in answers]) as api:
            lessons,_,_=generator.build('loops','','standard',1)
        self.assertEqual(api.call_count,6)
        self.assertEqual(lessons[0]['quality']['starter_repairs'],2)
        self.assertEqual(sum(source in (REFERENCE,REVIEWER) for source,_ in runner.calls),12)

    def test_focused_test_repair_cannot_change_source_or_task(self):
        raw=draft(); raw['tests'][0]['args']=['wrong type']
        generator=OllamaExerciseGenerator(ArrayRunner(),language='java')
        with patch.object(generator,'ask',return_value={'tests':CASES,'instructions':'changed'}):
            with self.assertRaisesRegex(DraftRejected,'only tests'):
                generator.repair_native_tests(raw,'run',1,1)
        self.assertEqual(raw['starter_code'],CRASH)

    def test_starter_infrastructure_failure_does_not_trigger_model_repair(self):
        class Offline(ArrayRunner):
            def run(self,source,entrypoint,args):
                if source==CRASH: raise RunnerError('Docker unavailable')
                return super().run(source,entrypoint,args)
        generator=OllamaExerciseGenerator(Offline(),language='java')
        with patch('ai_exercises.api',side_effect=[reply(draft()),reply(reviewed())]) as api:
            with self.assertRaisesRegex(RunnerError,'Docker unavailable'):
                generator.build('loops','','standard',1)
        self.assertEqual(api.call_count,2)

    def test_unapproved_or_scope_changing_starter_repair_cannot_be_accepted(self):
        for changes,approval,expected in (
                (repaired(),{'approved':False,'feedback':'The hints do not match.'},'rejected repair'),
                (repaired()|{'reference_solution':'changed'},APPROVAL,'only starter_code')):
            raw=draft(); generator=OllamaExerciseGenerator(ArrayRunner(),language='java')
            lesson=validate_draft(raw|{'notes_quote':''},'','standard','java')
            with self.subTest(expected=expected), patch.object(generator,'review_lesson',return_value=(reviewed(),0)),patch.object(
                    generator,'ask',side_effect=[changes,approval]):
                with self.assertRaisesRegex(DraftRejected,expected):
                    generator.verify_with_starter_repairs(lesson,raw,'loops','','standard',{},'run',1,1,1)
            self.assertEqual(raw['reference_solution'],REFERENCE)


@unittest.skipUnless(os.environ.get('AM_STARTER_TESTS')=='1','Set AM_STARTER_TESTS=1 for real Java starter repair checks.')
class JavaStarterRepairTests(unittest.TestCase):
    def test_real_empty_array_crash_is_replaced_by_ai_fixture_then_every_case_runs(self):
        from compiled_runner import CompiledRunner
        root=Path(__file__).resolve().parents[1]
        command=('docker',) if os.environ.get('AM_DOCKER_DIRECT')=='1' else ('sudo','-n','docker')
        runner=CompiledRunner((root/'.am-runtime/compiled-image.txt').read_text().strip(),'java',
                             draft()['signature'],command,wall_seconds=180)
        generator=OllamaExerciseGenerator(runner,language='java')
        raw=draft(); raw['tests']=deepcopy(CASES)
        lesson=validate_draft(raw|{'notes_quote':''},'','standard','java')
        # Check the two distinct references against the actual empty and mixed cases.
        generator.check_references({**lesson,'tests':lesson['tests'][:2]},REVIEWER,2)
        with patch.object(generator,'review_lesson',return_value=(reviewed(),0)),patch.object(
                generator,'ask',side_effect=[repaired(),APPROVAL]):
            accepted,_,_,_,count=generator.verify_with_starter_repairs(
                lesson,raw,'loops','','standard',{},'container-regression',1,1,1)
        self.assertEqual(count,1)
        self.assertEqual(accepted['starter_code'],SAFE_BUG)
        self.assertEqual(accepted['reference_solution'],REFERENCE)
        self.assertEqual(accepted['tests'][0]['args'],[[]])
