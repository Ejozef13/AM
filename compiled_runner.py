"""Compiled-language adapter using the existing restricted Docker transport."""
from pathlib import Path
import re

from code_runner import DockerRunner, RunnerError
from language_contracts import validate_signature
from native_harness import build_harness

DRIVER = (Path(__file__).resolve().parent / 'compiled_driver.py').read_text(encoding='utf-8')


class CompiledRunner(DockerRunner):
    # Typed literals expand when escaped into C/C++ harnesses and then JSON.
    # Source and input-value limits remain independently enforced.
    payload_limit = 128000
    driver = DRIVER
    memory = '512m'
    pids = '64'
    nofile = '128:128'
    cpu_limit = '12:12'
    # Native binaries must be executable; no host directories are mounted.
    temporary_filesystem = '/tmp:rw,exec,nosuid,nodev,size=64m'

    def valid_image(self, image):
        return re.fullmatch(r'sha256:[0-9a-f]{64}', image)

    # Allow daemon startup/compilation overhead separately from the inner
    # 3-second student-program limit enforced by the trusted driver.
    def __init__(self, image, language, signature=None, command=('sudo', '-n', 'docker'), wall_seconds=60):
        super().__init__(image, command, wall_seconds)
        if language not in ('java', 'c', 'cpp'):
            raise RunnerError('Unsupported compiler language.')
        self.language = language
        self.signature = validate_signature(language, signature) if signature is not None else None

    def with_signature(self, signature):
        return CompiledRunner(self.image, self.language, signature, self.command, self.wall_seconds)

    def run(self, source, entrypoint, args):
        result = super().run(source, entrypoint, args)
        # The trusted driver bounds both compilation and student execution.
        # A transport deadline therefore indicates a stalled container/daemon,
        # not evidence that the student's function is incorrect or too slow.
        if result.get('status') == 'timeout' and result.get('message') == 'Wall-time limit reached.':
            raise RunnerError('Compiler container preparation exceeded its wall-time allowance. '
                              'No student grade was produced. Check Docker and retry the run.')
        return result

    def request_payload(self, source, entrypoint, args):
        if entrypoint != 'solve' or self.signature is None:
            raise RunnerError('Compiled exercises require a solve function and typed signature.')
        try:
            harness = build_harness(self.language, self.signature, args)
        except ValueError as error:
            raise RunnerError(str(error)) from error
        return {**super().request_payload(source, entrypoint, args), 'language': self.language,
                'signature': self.signature, 'harness': harness}
