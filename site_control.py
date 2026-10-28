"""Foreground website lifecycle with private ownership records and graceful stop."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from am_core import AMError, PRACTICE_MODEL, api

ROOT = Path(__file__).resolve().parent


def runtime_dir():
    directory = Path(os.environ.get('AM_RUNTIME_DIR', ROOT / '.am-runtime'))
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    return directory


def identity(pid):
    """Linux start ticks distinguish our process from a reused PID."""
    try:
        directory = Path('/proc') / str(pid)
        if directory.stat().st_uid != os.getuid():
            return None
        fields = (directory/'stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (OSError, IndexError, ValueError):
        return None


def read_state():
    try:
        state = json.loads((runtime_dir()/'website.json').read_text())
        if (state.get('root') != str(ROOT) or type(state.get('pid')) is not int
                or state['pid'] <= 1 or not isinstance(state.get('start'), str)):
            return None
        return state
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def running(state):
    return bool(state and identity(state['pid']) == state['start'])


def save_state(state):
    temporary = runtime_dir()/'website.tmp'
    with open(temporary, 'w', encoding='utf-8', opener=lambda name, flags:os.open(name,flags,0o600)) as output:
        json.dump(state, output)
    temporary.replace(runtime_dir()/'website.json')


@contextmanager
def ownership():
    with open(runtime_dir()/'website.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AMError('AM website is already starting or running. Use: python am.py status') from error
        try:
            yield
        finally:
            state = read_state()
            if state and state['pid'] == os.getpid():
                (runtime_dir()/'website.json').unlink(missing_ok=True)


def port_busy(port):
    if not port:
        return False
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):
            return True
    except OSError:
        return False


def docker_access(direct=False):
    """Prefer existing direct access; otherwise authorize in the launch terminal."""
    try:
        result = subprocess.run(['docker','info'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10)
        if result.returncode == 0:
            return True
        if direct:
            raise AMError('Direct Docker access is unavailable. Start Docker or omit --docker-direct.')
        subprocess.run(['sudo','-v'],check=True)
        result = subprocess.run(['sudo','-n','docker','info'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10)
        if result.returncode:
            subprocess.run(['sudo','systemctl','start','docker'],check=True)
        subprocess.run(['sudo','-n','docker','info'],check=True,stdout=subprocess.DEVNULL,timeout=10)
        return False
    except (OSError, subprocess.SubprocessError) as error:
        raise AMError('Docker is not ready. Check its installation and terminal authorization.') from error


def model_description(model):
    result = api('/api/show', {'model':model}, timeout=30)
    details = result.get('details', {})
    details = details if isinstance(details,dict) else {}
    return f"{model} | family: {details.get('family','unknown')} | parameters: {details.get('parameter_size','unknown')}"


def serve(args, start_ollama, unload_model):
    import practice_web
    state = read_state()
    if running(state):
        print(f"AM website already {state['phase']}: http://127.0.0.1:{state['port']}")
        return
    with ownership():
        if port_busy(args.port):
            raise AMError(f'Port {args.port} is in use. Stop the old website in its launch terminal first.')
        state = {'root':str(ROOT),'pid':os.getpid(),'start':identity(os.getpid()),
                 'port':args.port,'phase':'starting','models':[],'offline':args.offline}
        save_state(state)
        try:
            direct = docker_access(args.docker_direct)
            if not args.offline:
                start_ollama()
                models = list(dict.fromkeys([args.model, args.review_model or args.model]))
                if args.templates:
                    models = [args.model]
                for model in models:
                    print('AI:', model_description(model), flush=True)
                state['models'] = models
                save_state(state)
                print('Loading the practice model…', flush=True)
                api('/api/generate', {'model':args.model,'stream':False,'keep_alive':'5m',
                                     'options':{'num_ctx':32768}}, timeout=180)
            flags = ['--port',str(args.port),'--model',args.model]
            for enabled, flag in [(direct,'--docker-direct'), (args.offline,'--offline'),
                                  (args.templates,'--templates'), (args.diagnostics,'--diagnostics')]:
                if enabled:
                    flags.append(flag)
            if args.review_model:
                flags.extend(['--review-model',args.review_model])
            def ready(port, server):
                state.update(port=port,phase='running')
                save_state(state)
                print('Website ON. Ctrl+C switches it off; another terminal can run: python am.py off',flush=True)
            practice_web.main(flags, on_ready=ready)
        finally:
            # Website cleanup finishes before unloading only its selected models.
            errors = []
            for model in state['models']:
                try:
                    unload_model(model)
                except AMError as error:
                    errors.append(str(error))
            if errors:
                raise AMError('Website stopped, but model unloading could not be confirmed: '+'; '.join(errors))


def stop(unload_model, model=PRACTICE_MODEL):
    state = read_state()
    if running(state):
        descriptor = os.pidfd_open(state['pid']) if hasattr(os,'pidfd_open') else None
        try:
            if not running(state):
                return
            if descriptor is not None and hasattr(signal,'pidfd_send_signal'):
                signal.pidfd_send_signal(descriptor,signal.SIGINT)
            else:
                os.kill(state['pid'],signal.SIGINT)
        except ProcessLookupError:
            return
        finally:
            if descriptor is not None:
                os.close(descriptor)
        print('Stopping the website, canceling active work, and releasing its model…',flush=True)
        deadline = time.monotonic()+90
        while running(state) and time.monotonic()<deadline:
            time.sleep(0.2)
        if running(state):
            raise AMError('AM is still cleaning up. No process was forcibly killed; check its launch terminal.')
        if state['models']:
            loaded = api('/api/ps',timeout=10).get('models',[])
            if any(item.get('name',item.get('model')) in state['models'] for item in loaded):
                raise AMError('Website stopped, but a practice model remains loaded. Check its launch terminal and other AI clients.')
        print('Website OFF. Its selected models are unloaded. Docker and Ollama services remain available.')
        return
    if port_busy(8090):
        raise AMError('An unmanaged website uses port 8090. Stop it with Ctrl+C in its launch terminal.')
    try:
        api('/api/ps',timeout=5)
    except AMError:
        print('Website OFF. Local Ollama is not responding; model unloading could not be checked.')
        return
    unload_model(model)
    print('Website OFF.')


def status():
    state = read_state()
    if running(state):
        print(f"Website {state['phase'].upper()}: http://127.0.0.1:{state['port']}")
        for model in state['models']:
            print('Configured AI:',model)
    else:
        print('Managed website OFF.')
    return state if running(state) else None
