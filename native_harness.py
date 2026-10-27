"""Trusted serializers and typed calls; no expected answers enter compiled code."""
import json
from language_contracts import function_header, native_type, typed_value, validate_signature

C_HEADERS = '#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <math.h>\n#include <stdlib.h>\n'
C_QUOTE = r'''
static void am_quote_n(const char *s, size_t n) {
    if (!s) { printf("null"); return; }
    putchar('"');
    for (size_t i=0; i<n; i++) {
        unsigned char c=(unsigned char)s[i];
        if (c=='"' || c=='\\') { putchar('\\'); putchar(c); }
        else if (c<32) printf("\\u%04x", c);
        else putchar(c);
    }
    putchar('"');
}
'''
JAVA_JSON = r'''
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Integer || value instanceof Long) return value.toString();
        if (value instanceof Double) {
            if (!Double.isFinite((Double)value)) throw new IllegalArgumentException("Nonfinite return value");
            return value.toString();
        }
        if (value instanceof int[]) {
            StringBuilder out=new StringBuilder("[");
            int[] values=(int[])value;
            for(int i=0;i<values.length;i++) { if(i>0) out.append(','); out.append(values[i]); }
            return out.append(']').toString();
        }
        if (!(value instanceof String)) throw new IllegalArgumentException("Unsupported return type");
        StringBuilder out=new StringBuilder("\"");
        for(char c:((String)value).toCharArray()) {
            if(c=='"' || c=='\\') { out.append('\\'); out.append(c); }
            else if(c<32 || c>126) out.append(String.format("\\u%04x", (int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
'''


def c_literal(value):
    # Every byte is an exactly-three-digit octal escape; source values cannot
    # terminate the literal or absorb a following hex digit into an escape.
    return '"' + ''.join('\\%03o' % byte for byte in value.encode('ascii')) + '"'


def scalar_literal(language, kind, value):
    if kind == 'string':
        return json.dumps(value, ensure_ascii=True) if language == 'java' else c_literal(value)
    if kind == 'bool':
        return 'true' if value else 'false'
    if kind == 'long':
        if value == -(2**63) and language != 'java':
            return '(-9223372036854775807LL - 1LL)'
        return str(value) + ('L' if language == 'java' else 'LL')
    if kind == 'double':
        return repr(float(value))
    return str(value)


def emit_c(kind, expression, length=None, cpp=False):
    if kind == 'int_array':
        size = f'{expression}.size()' if cpp else length
        return (f'printf("["); for(size_t am_i=0;am_i<(size_t)({size});am_i++) {{ '
                f'if(am_i) printf(","); printf("%d", {expression}[am_i]); }} printf("]");')
    if kind == 'string':
        return (f'am_quote_n({expression}.data(), {expression}.size());' if cpp else
                f'am_quote_n({expression}, {expression} ? strlen({expression}) : 0);')
    if kind == 'bool':
        return f'printf("%s", {expression} ? "true" : "false");'
    if kind == 'double':
        return f'if(!isfinite({expression})) return 3; printf("%.17g", (double){expression});'
    return f'printf("%lld", (long long){expression});'


def build_harness(language, signature, args):
    signature = validate_signature(language, signature)
    if len(args) != len(signature['parameters']):
        raise ValueError('Argument count differs from typed signature.')
    args = [typed_value(value, kind) for value, kind in zip(args, signature['parameters'])]
    declarations, calls = [], []
    for index, (kind, value) in enumerate(zip(signature['parameters'], args)):
        name = f'am_arg{index}'
        if kind == 'int_array':
            values = ','.join(map(str, value))
            if language == 'java':
                declarations.append(f'int[] {name} = new int[]{{{values}}};')
            elif language == 'cpp':
                declarations.append(f'std::vector<int> {name} = {{{values}}};')
            else:
                declarations.append(f'int {name}_storage[{max(1, len(value))}] = {{{values or "0"}}};')
                declarations.append(f'int *{name} = ' + (f'{name}_storage;' if value else 'NULL;'))
                declarations.append(f'int {name}_len = {len(value)};')
            calls.append(name)
            if language == 'c':
                calls.append(f'{name}_len')
        else:
            declarations.append(f'{native_type(language, kind)} {name} = {scalar_literal(language, kind, value)};')
            calls.append(name)
    call = ', '.join(calls)
    result_type = native_type(language, signature['returns'])
    if language == 'java':
        after = ' + "," + '.join(f'json(am_arg{i})' for i in range(len(args))) or '""'
        return ('public class AMHarness {\n' + JAVA_JSON + '\npublic static void main(String[] ignored) throws Exception {\n' +
                '\n'.join(declarations) + f'\n{result_type} am_result = Solution.solve({call});\n' +
                'System.out.println("\\nAM_RESULT:{\\"value\\":" + json(am_result) + '
                f'",\\"args_after\\":[" + {after} + "]}}");\n' + '}}\n')
    is_cpp = language == 'cpp'
    headers = C_HEADERS + ('#include <vector>\n#include <string>\n#include <cstddef>\n' if is_cpp else '')
    prototype = function_header(language, signature)
    # Type-check the student definition against the expected native signature.
    prelude = headers + prototype + ';\n'
    after = []
    for index, kind in enumerate(signature['parameters']):
        if index:
            after.append('printf(",");')
        after.append(emit_c(kind, f'am_arg{index}', f'am_arg{index}_len', is_cpp))
    result = emit_c(signature['returns'], 'am_result', cpp=is_cpp)
    main = ('\n' + C_QUOTE + '\nint main(void) {\n' + '\n'.join(declarations) +
            f'\n{result_type} am_result = solve({call});\n' +
            'printf("\\nAM_RESULT:{\\"value\\":");\n' + result +
            '\nprintf(",\\"args_after\\":[");\n' + '\n'.join(after) + '\nprintf("]}\\n"); return 0;\n}\n')
    return {'prelude': prelude, 'after': main}
