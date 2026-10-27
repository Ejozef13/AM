"""Typed, source-independent calling conventions for compiled-language exercises."""
import json
import math
import re

LABELS = {'python': 'Python', 'java': 'Java', 'c': 'C', 'cpp': 'C++'}
TYPES = ('int', 'long', 'double', 'bool', 'string', 'int_array')
NATIVE = ('java', 'c', 'cpp')


def signature_schema(language):
    return {'type': 'object', 'additionalProperties': False,
        'properties': {'parameters': {'type': 'array', 'minItems': 0, 'maxItems': 5,
                                      'items': {'type': 'string', 'enum': list(TYPES)}},
                       'returns': {'type': 'string', 'enum': list(TYPES[:-1] if language == 'c' else TYPES)}},
        'required': ['parameters', 'returns']}


def validate_signature(language, signature):
    if language not in NATIVE or not isinstance(signature, dict):
        raise ValueError('A compiled exercise needs a typed signature.')
    parameters, returns = signature.get('parameters'), signature.get('returns')
    if not isinstance(parameters, list) or len(parameters) > 5 or any(
            not isinstance(value, str) or value not in TYPES for value in parameters):
        raise ValueError('Signature needs zero to five supported parameter types.')
    if not isinstance(returns, str) or returns not in (TYPES[:-1] if language == 'c' else TYPES):
        raise ValueError('Unsupported return type for this language; C array returns are not supported.')
    return {'parameters': list(parameters), 'returns': returns}


def typed_value(value, kind):
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


def language_instruction(language):
    if language == 'python':
        return ''
    shape = ('Provide a complete public class Solution with a public static solve method, no package or main. '
             if language == 'java' else 'Provide a free solve function, without main. Standard headers may be included. ')
    return (f'Generate {LABELS[language]} code, not Python. ' + shape +
        'Select signature.parameters and signature.returns before writing code. '
        'The application requires this type mapping: int=signed 32-bit integer, long=signed 64-bit integer, double=finite number, '
        'bool=boolean, string=ASCII text up to 1000 chars (newline/tab allowed), int_array=0..100 32-bit integers. '
        'Test args contains one JSON value for each declared parameter; nested arrays are one argument. '
        'C int_array parameters expand to const int *argN, int argN_len; strings are const char *. '
        'C cannot return an array in this version. C++ strings/arrays use const std::string& / const std::vector<int>&. '
        'Java uses String and int[]. Other scalar mappings are standard. '
        'Use arg0, arg1, ... for argument names in your code. entrypoint is always solve. '
        'Return values, never print results or parse stdin; the trusted harness handles I/O. '
        'Do not mutate inputs, access files/network, spawn processes, or use third-party dependencies. '
        'List valid input bounds and all edge-case behavior in the question. '
        'Source fields are plain code, without Markdown fences. No decorators or Python syntax. ')
