"""Typed, source-independent calling conventions for compiled-language exercises."""
import json
import math
import re
from structures import STRUCTURE_TYPES, STRUCTURE_GUIDE, validate_structure

LABELS = {'python': 'Python', 'java': 'Java', 'c': 'C', 'cpp': 'C++'}
BASIC_TYPES = ('int', 'long', 'double', 'bool', 'string', 'int_array')
TYPES = BASIC_TYPES + STRUCTURE_TYPES

def return_types(language):
    return BASIC_TYPES[:-1] if language == 'c' else BASIC_TYPES

NATIVE = ('java', 'c', 'cpp')


def signature_schema(language):
    return {'type': 'object', 'additionalProperties': False,
        'properties': {'parameters': {'type': 'array', 'minItems': 0, 'maxItems': 5,
                                      'items': {'type': 'string', 'enum': list(TYPES)}},
                       'returns': {'type': 'string', 'enum': list(return_types(language))}},
        'required': ['parameters', 'returns']}


def validate_signature(language, signature):
    if language not in NATIVE or not isinstance(signature, dict):
        raise ValueError('A compiled exercise needs a typed signature.')
    parameters, returns = signature.get('parameters'), signature.get('returns')
    if not isinstance(parameters, list) or len(parameters) > 5 or any(
            not isinstance(value, str) or value not in TYPES for value in parameters):
        raise ValueError('Signature needs zero to five supported parameter types.')
    if not isinstance(returns, str) or returns not in return_types(language):
        raise ValueError('Unsupported return type for this language; C array returns are not supported.')
    return {'parameters': list(parameters), 'returns': returns}


def typed_value(value, kind):
    if kind in STRUCTURE_TYPES:
        return validate_structure(value, kind)
    if kind in ('int', 'long'):
        limit = 2**31 - 1 if kind == 'int' else 2**63 - 1
        lower = -(2**31) if kind == 'int' else -(2**63)
        if type(value) is not int or not lower <= value <= limit:
            raise ValueError(f'{kind} requires an integer in [{lower}, {limit}].')
    elif kind == 'double':
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('double requires a finite number.')
        return float(value)
    elif kind == 'bool':
        if type(value) is not bool:
            raise ValueError('bool requires a JSON boolean.')
    elif kind == 'string':
        if not isinstance(value, str) or len(value) > 1000 or any(
                not (' ' <= char <= '~' or char in '\n\r\t') for char in value):
            raise ValueError('Compiled string inputs/expected outputs use ASCII text (up to 1000 characters; newline/tab allowed).')
    elif kind == 'int_array':
        if not isinstance(value, list) or len(value) > 100:
            raise ValueError('int_array requires an array of at most 100 integers.')
        for item in value:
            typed_value(item, 'int')
    else:
        raise ValueError('Unsupported value type.')
    return value


def typed_cases(signature, tests):
    output = []
    for case in tests:
        if len(case['args']) != len(signature['parameters']):
            raise ValueError(f"{case['name']}: test argument count differs from the signature.")
        output.append({**case,
            'args': [typed_value(value, kind) for value, kind in zip(case['args'], signature['parameters'])],
            'expected': typed_value(case['expected'], signature['returns'])})
    return output


def native_type(language, kind):
    if kind in STRUCTURE_TYPES:
        name = {'linked_list':'ListNode', 'tree':'TreeNode', 'graph':'Graph'}[kind]
        return name if language == 'java' else ('const '+name+' *')
    return {'java': {'int': 'int', 'long': 'long', 'double': 'double', 'bool': 'boolean',
                     'string': 'String', 'int_array': 'int[]'},
            'c': {'int': 'int', 'long': 'long long', 'double': 'double', 'bool': 'bool',
                  'string': 'const char *', 'int_array': 'const int *'},
            'cpp': {'int': 'int', 'long': 'long long', 'double': 'double', 'bool': 'bool',
                    'string': 'std::string', 'int_array': 'std::vector<int>'}}[language][kind]


def function_header(language, signature):
    signature = validate_signature(language, signature)
    params = []
    for index, kind in enumerate(signature['parameters']):
        ctype = native_type(language, kind)
        if language == 'cpp' and kind in ('string', 'int_array'):
            ctype = 'const ' + ctype + '&'
        params.append(f'{ctype} arg{index}')
        if language == 'c' and kind == 'int_array':
            params.append(f'int arg{index}_len')
    if language == 'c' and not params:
        params = ['void']
    prefix = 'public static ' if language == 'java' else ''
    return prefix + native_type(language, signature['returns']) + ' solve(' + ', '.join(params) + ')'


def value_schema(kind):
    if kind in STRUCTURE_TYPES:
        key = 'adjacency' if kind == 'graph' else 'values'
        items = ({'type':'array','maxItems':24,'items':{'type':'integer','minimum':0,'maximum':23}}
                 if kind == 'graph' else {'anyOf':[value_schema('int'),{'type':'null'}]} if kind == 'tree' else value_schema('int'))
        return {'type':'object','required':['__type',key], 'additionalProperties':False,
                'properties':{'__type':{'type':'string','enum':[kind]}, key:{'type':'array',
                    'maxItems':24 if kind=='graph' else 127 if kind=='tree' else 100, 'items':items}}}
    if kind in ('int', 'long'):
        bits = 32 if kind == 'int' else 64
        return {'type':'integer', 'minimum':-(2**(bits-1)), 'maximum':2**(bits-1)-1}
    if kind == 'int_array':
        return {'type':'array', 'maxItems':100, 'items':value_schema('int')}
    if kind == 'string':
        return {'type':'string', 'maxLength':1000}
    return {'type': {'double':'number', 'bool':'boolean'}[kind]}


def review_test_schema(signature):
    """Constrain model tests to logical arguments, not the expanded C ABI."""
    parameters = signature['parameters']
    # Ollama's grammar converter requires object schemas for items. Do not add
    # items:false after the tuple: maxItems already forbids extra arguments.
    return {'type':'array', 'minItems':3, 'maxItems':5, 'items':{
        'type':'object', 'additionalProperties':False, 'required':['name','args','expected'],
        'properties':{'name':{'type':'string','minLength':1,'maxLength':100},
            'args':{'type':'array','minItems':len(parameters),'maxItems':len(parameters),
                    'prefixItems':[value_schema(kind) for kind in parameters]},
            'expected':value_schema(signature['returns'])}}}


def language_instruction(language):
    if language == 'python':
        return ''
    shape = {
        'java':'Submit public class Solution with a public static solve method; no package or main. Use String and int[]. ',
        'c':'Submit a free solve function without main. int_array expands to const int *argN, int argN_len. '
            'The runner supplies lengths: never include them as extra JSON arguments. string is const char *. No array returns. ',
        'cpp':'Submit a free solve function without main. Use const std::string& and const std::vector<int>& inputs. '
              'Array returns use std::vector<int>. ',
    }[language]
    return (f'Generate {LABELS[language]} code. ' + shape +
        'Select signature.parameters and signature.returns before writing code. '
        'The application requires this type mapping: int=signed 32-bit integer, long=signed 64-bit integer, double=finite number, '
        'bool=boolean, string=ASCII text up to 1000 chars (newline/tab allowed), int_array=0..100 32-bit integers. '
        'Test args contains one JSON value for each declared parameter; nested arrays are one argument. '
        'Use arg0, arg1, ... for argument names in your code. entrypoint is always solve. '
        'Return values, never print results or parse stdin; the trusted harness handles I/O. '
        'Do not mutate inputs, access files/network, spawn processes, or use third-party dependencies. '
        'List valid input bounds and all edge-case behavior in the question. '
        'Source fields are plain code, without Markdown fences. ' + STRUCTURE_GUIDE +
        'Native structured types are input-only; return a scalar or an allowed int_array. ' +
        {'c':'Graph has size, degree[24], adj[24][24]. ', 'java':'Graph has int[][] adj. ',
         'cpp':'Graph has std::vector<std::vector<int>> adj. '}[language] +
        'Nodes have int val and next/left/right fields. Types are supplied by the harness. ')
