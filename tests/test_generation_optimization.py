"""Regression coverage for compact requests and C logical argument contracts."""
import json
import unittest
from unittest.mock import patch

from ai_exercises import DraftRejected, OllamaExerciseGenerator
from language_contracts import language_instruction, review_test_schema, typed_cases
from test_ai_exercises import NOTES, draft, review, response, FixtureRunner
from test_multilanguage_generation import native_draft, native_review, NativeFixtureRunner, reply


class GenerationOptimizationTests(unittest.TestCase):
    def test_c_and_cpp_count_questions_keep_two_logical_inputs_through_review_and_validation(self):
        for language in ('c','cpp'):
            header = ('int solve(const int *arg0, int arg0_len, int arg1)' if language == 'c' else
                      'int solve(const std::vector<int>& arg0, int arg1)')
            length = 'arg0_len' if language == 'c' else 'arg0.size()'
            correct = header+' { int count=0; for(int i=0;i<'+length+';i++) if(arg0[i]==arg1) count++; return count; }'
            starter = correct.replace('count=0','count=1')
            authored = native_draft(language)
            authored.update(signature={'parameters':['int_array','int'],'returns':'int'},
                instructions='Count occurrences of the target. Empty arrays return zero; do not mutate inputs.',
                constraints=['Array length 0 to 100. Values and target are signed 32-bit integers.'],
                starter_code=starter,reference_solution=correct,hints=['Consider repeated matches.'],
                tests=[{'name':'repeated','args':[[2,5,2,2],2],'expected':3},
                       {'name':'negative','args':[[-1,0,-1],-1],'expected':2},
                       {'name':'empty','args':[[],7],'expected':0}])
            checked = native_review(language)
            checked.update(reference_solution=correct,tests=[
                {'name':'absent','args':[[1,3],9],'expected':0},
                {'name':'single','args':[[5],5],'expected':1},
                {'name':'all','args':[[2,2],2],'expected':2}])
            class CountRunner:
                def with_signature(self,signature):return self
                def run(self,source,entrypoint,args):
                    if source not in (correct,starter):raise AssertionError('Unexpected fixture source')
                    return {'status':'ok','value':args[0].count(args[1])+(source==starter),'args_after':args}
            generator=OllamaExerciseGenerator(CountRunner(),language=language)
            with self.subTest(language=language),patch('ai_exercises.api',side_effect=[reply(authored),reply(checked)]) as api:
                lessons,_,_=generator.build('count occurrences','', 'introductory',1)
            self.assertEqual(len(lessons[0]['tests']),6)
            schema=api.call_args_list[1].args[1]['format']['properties']['tests']['items']['properties']['args']
            self.assertEqual(schema['maxItems'],2)
            self.assertEqual([item['type'] for item in schema['prefixItems']],['array','integer'])

    def test_small_requests_use_low_reasoning_and_do_not_repeat_explanatory_metadata(self):
        generator = OllamaExerciseGenerator(FixtureRunner())
        with patch('ai_exercises.api',side_effect=[response(draft()),response(review())]) as api:
            generator.build('factorial',NOTES, 'introductory',1)
        for call in api.call_args_list:
            payload = call.args[1]
            self.assertEqual(payload['think'],'low')
            self.assertEqual(payload['options']['num_predict'],8000)
            self.assertEqual(payload['format']['properties']['tests']['maxItems'],5)
        task = json.loads(api.call_args_list[1].args[1]['messages'][1]['content'])['exercise']
        self.assertNotIn('focus_plan',task)
        self.assertNotIn('skills',task)

    def test_c_review_schema_bounds_array_values_and_logical_arity(self):
        runner = NativeFixtureRunner('c')
        generator = OllamaExerciseGenerator(runner,language='c')
        with patch('ai_exercises.api',side_effect=[reply(native_draft('c')),reply(native_review('c'))]) as api:
            generator.build('maximum','', 'introductory',1)
        schema = api.call_args_list[1].args[1]['format']['properties']['tests']['items']['properties']
        self.assertEqual(schema['args']['minItems'],1)
        self.assertEqual(schema['args']['maxItems'],1) # pointer + length is ONE JSON argument
        self.assertEqual(schema['args']['prefixItems'][0]['maxItems'],100)
        self.assertEqual(schema['expected']['type'],'integer')
        self.assertNotIn('C++',language_instruction('c'))
        self.assertNotIn('Java',language_instruction('c'))

    def test_native_review_tuple_schema_is_ollama_compatible_and_arity_stays_checked(self):
        # Ollama rejects boolean `items` schemas even though JSON Schema allows them.
        # Cover every supported parameter type and empty/mixed parameter lists.
        for parameters in ([], ['int_array'], ['int_array', 'int'],
                           ['long', 'double', 'bool', 'string', 'int']):
            signature = {'parameters': parameters, 'returns': 'int'}
            schema = review_test_schema(signature)
            def check_items(node):
                if isinstance(node, dict):
                    if 'items' in node:
                        self.assertIsInstance(node['items'], dict)
                    for value in node.values():
                        check_items(value)
                elif isinstance(node, list):
                    for value in node:
                        check_items(value)
            check_items(schema)
            args = schema['items']['properties']['args']
            self.assertEqual(args['minItems'], len(parameters))
            self.assertEqual(args['maxItems'], len(parameters))
            with self.assertRaisesRegex(ValueError, 'argument count'):
                typed_cases(signature, [{'name': 'extra input',
                    'args': [0] * (len(parameters) + 1), 'expected': 0}])
        with self.assertRaisesRegex(ValueError, 'requires an integer'):
            typed_cases({'parameters': ['int'], 'returns': 'int'},
                        [{'name': 'wrong type', 'args': ['code expression'], 'expected': 0}])

    def test_starter_crash_after_wrong_answer_is_rejected_with_repair_evidence(self):
        generator = OllamaExerciseGenerator(FixtureRunner())
        lesson = {'starter_code': 'fixture', 'entrypoint': 'solve', 'tests': [
            {'name': 'wrong answer', 'args': [[2]], 'expected': 2},
            {'name': 'empty array', 'args': [[]], 'expected': 0}]}
        with patch('ai_exercises.grade_case', side_effect=[
                {'status': 'failed'},
                {'status': 'runtime_error', 'message': 'load of null pointer'}]) as grade:
            with self.assertRaises(DraftRejected) as caught:
                generator.check_starter(lesson)
        self.assertEqual(grade.call_count, 2)
        self.assertIn('empty array', str(caught.exception))
        self.assertIn('"args": [[]]', str(caught.exception))
        self.assertIn('Preserve the task and valid input domain', str(caught.exception))
        self.assertEqual(lesson['tests'][0]['name'], 'wrong answer')

    def test_safe_wrong_answer_is_moved_first_after_all_starter_cases_are_checked(self):
        generator = OllamaExerciseGenerator(FixtureRunner())
        lesson = {'starter_code': 'fixture', 'entrypoint': 'solve', 'tests': [
            {'name': 'passes', 'args': [[2]], 'expected': 2},
            {'name': 'wrong answer', 'args': [[]], 'expected': 0},
            {'name': 'also passes', 'args': [[3]], 'expected': 3}]}
        with patch('ai_exercises.grade_case', side_effect=[
                {'status': 'passed'}, {'status': 'failed'}, {'status': 'passed'}]) as grade:
            generator.check_starter(lesson)
        self.assertEqual(grade.call_count, 3)
        self.assertEqual(lesson['tests'][0]['name'], 'wrong answer')

    def test_truncation_metadata_records_counts_without_hidden_reasoning(self):
        generator = OllamaExerciseGenerator(FixtureRunner())
        truncated = {'done':True,'done_reason':'length','eval_count':8000,
                     'message':{'content':'','thinking':'PRIVATE_HIDDEN_REASONING'}}
        with patch('ai_exercises.api',return_value=truncated):
            with self.assertRaises(DraftRejected):
                generator.ask(generator.model,'test',{}, {})
        self.assertEqual(generator.last_response_metadata['eval_count'],8000)
        self.assertGreater(generator.last_response_metadata['thinking_characters'],0)
        self.assertNotIn('PRIVATE_HIDDEN_REASONING',json.dumps(generator.last_response_metadata))
