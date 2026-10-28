"""Regressions distilled from the uploaded Java printable-ASCII diagnostic."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_exercises import OllamaExerciseGenerator, cases
from code_runner import RunnerError, grade_case
from compiled_runner import CompiledRunner
from language_contracts import review_test_schema, typed_value
from test_multilanguage_generation import native_draft, native_review, reply
from text_protocol import decode_text, text_schema

REFERENCE = '''public class Solution {
 public static int solve(String arg0) {
  int count=0;
  for(int i=0;i<arg0.length();i++) {
   char c=arg0.charAt(i); if(c>=32 && c<=126) count++;
  }
  return count;
 }
}'''
STARTER = REFERENCE.replace('c>=32','c>32')


def encoded(value):
    return {'__am_text__':[ord(char) for char in value]}


def author():
    value=native_draft('java')
    value.update(title='Printable ASCII',instructions='Count characters with codes 32 through 126, inclusive. Accept ASCII 0 through 127.',
        constraints=['The input has 0 to 1000 ASCII characters.'],focus='ASCII character classification',
        signature={'parameters':['string'],'returns':'int'},starter_code=STARTER,reference_solution=REFERENCE,
        tests=[{'name':'Empty string','args':[encoded('')],'expected':0},
               {'name':'All printable','args':[encoded('Hello, World! 123')],'expected':17},
               {'name':'Boundaries','args':[encoded(' \t\n~')],'expected':2},
               {'name':'Non-printable','args':[encoded('\0\x1f\x7f')],'expected':0},
               {'name':'Mixed','args':[encoded('A\nB\tC~')],'expected':4}])
    return value


def review():
    value=native_review('java')
    value.update(reference_solution=REFERENCE,tests=[
        {'name':'Literal quotes','args':[encoded('""')],'expected':2},
        {'name':'Literal slash n','args':[encoded(r'\n')],'expected':2},
        {'name':'NUL and space','args':[encoded('\0 ')],'expected':1}])
    return value


class AsciiRunner:
    def with_signature(self, signature): return self
    def run(self, source, entrypoint, args):
        if source not in (REFERENCE,STARTER): raise RunnerError('Unknown regression fixture')
        value=sum((32 if source==REFERENCE else 33)<=ord(char)<=126 for char in args[0])
        return {'status':'ok','value':value,'args_after':deepcopy(args)}


class TextProtocolTests(unittest.TestCase):
    def test_explicit_encoding_and_raw_legacy_strings_preserve_different_meanings(self):
        for value in ('','""','\t\n',r'\t\n','\0\x1f\x7f',r'\u0000'):
            self.assertEqual(decode_text(encoded(value)),value)
            self.assertEqual(decode_text(value),value)
        self.assertNotEqual(decode_text(encoded('\n')),decode_text(encoded(r'\n')))
        for invalid in ({'__am_text__':[True]}, {'__am_text__':[-1]}, {'__am_text__':[0xd800]},
                        {'__am_text__':[0x110000]}, {'__am_text__':'[]'}, {'__am_text__':[],'extra':0}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError): decode_text(invalid)

    def test_generated_pipeline_accepts_actual_controls_without_reinterpreting_literal_escapes(self):
        generator=OllamaExerciseGenerator(AsciiRunner(),language='java')
        with patch('ai_exercises.api',side_effect=[reply(author()),reply(review())]) as api:
            lessons,_,_=generator.build('printing','','standard',1)
        tests=lessons[0]['tests']
        self.assertTrue(any(case['args']==['\0\x1f\x7f'] for case in tests))
        self.assertTrue(any(case['args']==[r'\n'] and case['expected']==2 for case in tests))
        schema=api.call_args_list[1].args[1]['format']['properties']['tests']['items']['properties']['args']['prefixItems'][0]
        self.assertEqual(schema['required'],['__am_text__'])
        self.assertEqual(schema['properties']['__am_text__']['items']['maximum'],127)
        public=json.loads(api.call_args_list[1].args[1]['messages'][1]['content'])['exercise']
        self.assertEqual(public['focus'],'ASCII character classification')
        self.assertNotIn('reference_solution',public)
        self.assertNotIn('tests',public)

    def test_string_returns_and_nested_values_are_decoded_before_comparison(self):
        raw=[{'name':str(i),'args':[encoded(value)],'expected':encoded(value)} for i,value in enumerate(('','\0',r'\n'))]
        parsed=cases(raw,'Review')
        self.assertEqual([case['expected'] for case in parsed],['','\0',r'\n'])
        self.assertEqual(text_schema('c')['properties']['__am_text__']['items']['minimum'],1)
        self.assertEqual(typed_value('\0','string','cpp'),'\0')
        with self.assertRaises(ValueError): typed_value('\0','string','c')


@unittest.skipUnless(os.environ.get('AM_ASCII_TESTS')=='1','Set AM_ASCII_TESTS=1 for real ASCII container checks.')
class AsciiContainerTests(unittest.TestCase):
    def test_all_ascii_bytes_survive_java_cpp_and_supported_c_boundaries(self):
        root=Path(__file__).resolve().parents[1]; image=(root/'.am-runtime/compiled-image.txt').read_text().strip()
        command=('docker',) if os.environ.get('AM_DOCKER_DIRECT')=='1' else ('sudo','-n','docker')
        for language in ('java','cpp','c'):
            # String-return round trips (C exposes null-terminated scalar strings).
            source=('public class Solution { public static String solve(String arg0) { return arg0; } }' if language=='java' else
                    'std::string solve(const std::string& arg0) { return arg0; }' if language=='cpp' else
                    'const char *solve(const char *arg0) { return arg0; }')
            value=''.join(chr(i) for i in range(1 if language=='c' else 0,128))
            runner=CompiledRunner(image,language,{'parameters':['string'],'returns':'string'},command,wall_seconds=180)
            result=grade_case(runner,source,'solve',{'name':'all ASCII','args':[value],'expected':value},True)
            self.assertEqual(result['status'],'passed',result)
        runner=CompiledRunner(image,'java',{'parameters':['string'],'returns':'int'},command,wall_seconds=180)
        for source,expected in ((REFERENCE,95),(STARTER,94)):
            result=runner.run(source,'solve',[''.join(chr(i) for i in range(128))])
            self.assertEqual(result['status'],'ok',result)
            self.assertEqual(result['value'],expected)
