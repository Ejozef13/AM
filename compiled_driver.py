"""Trusted container entrypoint for compiling and running one native test.

This file is passed to Python INSIDE Docker. Never run uploaded source on the host.
"""
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import time


class Limit(Exception):
    pass


def child_limits(cpu_seconds):
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_bounded(command, cwd, seconds, ceiling, cpu):
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
        preexec_fn=lambda: child_limits(cpu), env={**os.environ,
            'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
            'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=0', 'TMPDIR': str(cwd)})
    output = bytearray(); deadline = time.monotonic() + seconds
    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise TimeoutError('Time limit reached.')
                for key, _ in selector.select(0.05):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output) > ceiling:
                            raise Limit('Output limit reached.')
        return process.wait(timeout=max(0.01, deadline-time.monotonic())), output.decode('utf-8', errors='replace')
    finally:
        # Kill all descendants, even if the program exited with a pipe held open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.stdout.close()
        process.wait(timeout=2)


def execute(data):
    language = data['language']
    with tempfile.TemporaryDirectory(prefix='am-native-', dir='/tmp') as directory:
        work = Path(directory)
        if language == 'java':
            (work/'Solution.java').write_text(data['source'], encoding='utf-8')
            (work/'AMHarness.java').write_text(data['harness'], encoding='utf-8')
            vm = ['-Xmx64m', '-Xss256k', '-XX:MaxMetaspaceSize=96m', '-XX:ReservedCodeCacheSize=32m',
                  '-XX:CompressedClassSpaceSize=32m', '-XX:ActiveProcessorCount=1', '-XX:+UseSerialGC', '-XX:-UsePerfData']
            compile_command = ['javac', *['-J'+option for option in vm], '-encoding', 'UTF-8',
                               '--release', '21', 'Solution.java', 'AMHarness.java']
            run_command = ['java', *vm, '-cp', str(work), 'AMHarness']
        elif language in ('c', 'cpp'):
            filename = 'submission.c' if language == 'c' else 'submission.cpp'
            harness = data['harness']
            (work/filename).write_text(harness['prelude'] + '\n#line 1 "student_source"\n' +
                data['source'] + '\n#line 1 "am_harness"\n' + harness['after'], encoding='utf-8')
            compile_command = ['gcc' if language == 'c' else 'g++',
                '-std=c17' if language == 'c' else '-std=c++17', '-O0', '-g', '-Wall', '-Wextra',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', filename, '-o', 'program']
            run_command = [str(work/'program')]
        else:
            raise ValueError('Unsupported compiled language.')
        try:
            code, log = run_bounded(compile_command, work, 30, 8192, 8)
        except TimeoutError:
            return {'status': 'compile_error', 'message': 'Compiler time limit reached.'}
        except Limit:
            return {'status': 'compile_error', 'message': 'Compiler diagnostics exceeded the output limit.'}
        if code:
            return {'status': 'compile_error', 'message': log[-2500:] or f'Compiler exited with status {code}.'}
        try:
            code, log = run_bounded(run_command, work, 3, 12000, 2)
        except TimeoutError:
            return {'status': 'timeout', 'message': 'Program time limit reached.'}
        except Limit:
            return {'status': 'output_limit', 'message': 'Program output limit reached.'}
        if code:
            return {'status': 'runtime_error', 'message': log[-2000:] or f'Program exited with status {code}.'}
        printed, marker, record = log.rpartition('\nAM_RESULT:')
        if not marker:
            return {'status': 'runtime_error', 'message': 'Program ended without returning a function result.', 'output': log[:2000]}
        if len(printed) > 2000:
            return {'status': 'output_limit', 'message': 'Submission printed too much output.'}
        try:
            result = json.loads(record)
            if not isinstance(result, dict) or not {'value', 'args_after'} <= result.keys():
                raise ValueError('Missing typed result.')
            signature = data['signature']
            if signature['returns'] == 'double' and type(result['value']) in (int, float):
                result['value'] = float(result['value'])
            for index, kind in enumerate(signature['parameters']):
                if kind == 'double':
                    result['args_after'][index] = float(result['args_after'][index])
            json.dumps(result, allow_nan=False)
        except (ValueError, TypeError, IndexError, KeyError, OverflowError):
            return {'status': 'runtime_error', 'message': 'Program produced an invalid JSON return value.'}
        return {'status': 'ok', 'value': result['value'], 'args_after': result['args_after'], 'output': printed}


if __name__ == '__main__':
    try:
        # Docker attach can delay forwarding EOF. The host sends one JSON line,
        # so preparation need not wait for the input stream to close.
        result = execute(json.loads(sys.stdin.readline()))
    except BaseException as error:
        result = {'status': 'runtime_error', 'message': f'Compiled driver: {type(error).__name__}: {str(error)[:400]}'}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
