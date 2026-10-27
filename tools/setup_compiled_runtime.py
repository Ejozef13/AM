"""Build and probe one local compiler image for Java, C and C++ practice."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_runner import RunnerError, grade_case
from compiled_runner import CompiledRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker-direct', action='store_true', help='Use only when already authorized for direct Docker access')
    parser.add_argument('--build-network', choices=('default', 'host'), default='default',
                        help='Dependency-build networking only; student runs always have no network')
    parser.add_argument('--ca-bundle', type=Path, help='Optional trusted corporate/proxy CA bundle; requires BuildKit')
    parser.add_argument('--use-existing-image', action='store_true', help='Probe the already-built local compiler image without rebuilding')
    args = parser.parse_args()
    command = ['docker'] if args.docker_direct else ['sudo', '-n', 'docker']
    runtime = ROOT / '.am-runtime'
    runtime.mkdir(mode=0o700, exist_ok=True)
    config = runtime / 'docker-config'; config.mkdir(mode=0o700, exist_ok=True)
    build = [*command, '--config', str(config), 'build', '--pull=false',
             '--network=' + args.build_network, '--build-arg', 'HTTP_PROXY', '--build-arg', 'HTTPS_PROXY',
             '--build-arg', 'NO_PROXY', '--build-arg', 'http_proxy', '--build-arg', 'https_proxy',
             '--build-arg', 'no_proxy', '-t', 'am-compiled-practice:local',
             str(ROOT / 'infrastructure/compiled-runtime')]
    if args.ca_bundle:
        # Only the optional custom-CA build needs BuildKit secret mounts.
        # The normal Dockerfile also works with Docker's legacy builder.
        build[-1:-1] = ['--file', str(ROOT / 'infrastructure/compiled-runtime/Dockerfile.buildkit'),
                       '--secret', 'id=am_ca_bundle,src=' + str(args.ca_bundle.resolve())]
    try:
        if not args.use_existing_image:
            print('Building compiler dependencies. This is a one-time image build; no student code is used.', flush=True)
            subprocess.run(build, check=True, timeout=900)
        image = subprocess.check_output([*command, 'image', 'inspect', 'am-compiled-practice:local',
                                         '--format', '{{.Id}}'], text=True, timeout=10).strip()
        signature = {'parameters': ['int'], 'returns': 'int'}
        sources = {'java': 'public class Solution { public static int solve(int arg0) { return arg0 + 1; } }',
                   'c': 'int solve(int arg0) { return arg0 + 1; }',
                   'cpp': 'int solve(int arg0) { return arg0 + 1; }'}
        for language, source in sources.items():
            runner = CompiledRunner(image, language, signature, command)
            result = grade_case(runner, source, 'solve', {'name': 'compiler probe', 'args': [41], 'expected': 42}, True)
            if result['status'] != 'passed':
                raise RunnerError(f'{language} probe failed: {result}')
            print(f'PASS {language}: compiled and executed as an unprivileged user in a restricted container.', flush=True)
        temporary = runtime / 'compiled-image.tmp'
        temporary.write_text(image + '\n', encoding='utf-8')
        temporary.replace(runtime / 'compiled-image.txt')
    except (OSError, ValueError, RunnerError, subprocess.SubprocessError) as error:
        print(f'Compiler setup failed: {error}\nNo new runtime pin was saved. Check Docker and sudo -v.', file=sys.stderr)
        return 1
    print('Compiler runtime ready. Restart python practice_web.py to enable Java, C, and C++.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
