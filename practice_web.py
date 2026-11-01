"""Local browser lesson backed by the existing Docker runner. No AI grading."""

import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading

from code_runner import DockerAuthorizationError, DockerRunner, RunnerError, grade_case
from am_core import AMError, PRACTICE_MODEL
from ai_exercises import OllamaExerciseGenerator
from generation_diagnostics import DiagnosticRecorder
from compiled_runner import CompiledRunner
from study_input import LANGUAGES
from practice_sessions import SessionStore
from progress_store import ProgressStore
from note_retrieval import extract_pdf
from structures import STRUCTURE_GUIDE
import os

ROOT = Path(__file__).resolve().parent


class PracticeApp:
    def __init__(self, runner, generator, runtimes=None, diagnostics=False, persistence=None, authorization=None):
        self.runner = runner
        self.runtimes = runtimes or {'python': runner}
        self.busy = threading.Lock()
        self.sessions = SessionStore(generator, persistence)
        self.persistence = persistence
        self.authorization = authorization
        self.progress = "Ready"
        self.diagnostics = diagnostics
        self.stop_event = threading.Event()
        for runtime in self.runtimes.values():
            runtime.cancel_event = self.stop_event
        if generator is not None:
            generator.progress = self.set_progress
            generator.cancel_event = self.stop_event

    def set_progress(self, message):
        if self.stop_event.is_set():
            raise AMError('Session preparation canceled because the website is stopping.')
        self.progress = message

    def execution_diagnostic(self, operation, error):
        if self.diagnostics:
            # JSON quoting keeps terminal control characters escaped. Do not
            # log submissions, test inputs, answer keys, or note contents here.
            print('AM execution diagnostic: ' + json.dumps({
                'operation': operation, 'error_type': type(error).__name__,
                'detail': str(error)[:1200]}), file=sys.stderr, flush=True)

    def public_lesson(self, lesson):
        # Explicit allowlist: reference solution, hints and answer keys stay off
        # the initial response. Hints are disclosed only when requested.
        keys = ("id", "title", "language", "difficulty", "instructions",
                "constraints", "skills", "starter_code")
        return {**{key: lesson[key] for key in keys},
                **({"required_signature": lesson['required_signature']} if 'required_signature' in lesson else {}),
                "quality": {key: lesson["quality"][key] for key in
                            ("source", "separate_review", "distinct_models", "reference_runs")}
                           | {"review_test_repairs": lesson["quality"].get("review_test_repairs", 0)},
                "test_count": len(lesson["tests"]),
                "hint_count": len(lesson["hints"]),
                "structure_help": STRUCTURE_GUIDE + ("Graph has size, degree[24], adj[24][24]." if lesson["language"] == "c" else "Graph.adj holds adjacency rows.")}

    def run(self, source, session_data):
        # Source is passed only to the container, never exec'd on the host.
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Enter some code first.")
        if len(source.encode("utf-8")) > 16000:
            raise ValueError("Keep the submission below 16,000 UTF-8 bytes.")
        key, session = self.sessions.get(session_data)
        lesson = session.lessons[session.index]
        runner = self.runner
        if lesson['language'] != 'python':
            if lesson['language'] not in self.runtimes:
                raise RunnerError('Compiler runtime is not configured.')
            runner = self.runtimes[lesson['language']].with_signature(lesson['signature'])
        results = []
        for case in lesson["tests"]:
            # Keep the authored input as evidence even on errors or input mutation.
            arguments = deepcopy(case["args"])
            result = grade_case(runner, source, lesson["entrypoint"], case,
                                lesson["grading"]["forbid_input_mutation"])
            evidence = {"args": arguments, "args_json": json.dumps(arguments, ensure_ascii=False)}
            for value_key in ('expected', 'actual'):
                if value_key in result:
                    evidence[value_key + '_json'] = json.dumps(result[value_key], ensure_ascii=False)
            results.append({**result, **evidence})
        response = {"results": results, "passed": sum(r["status"] == "passed" for r in results),
                    "total": len(results), "complete": True}
        if session is not None:
            previous = session.attempts.get(session.index, {}).get("attempts", 0)
            session.attempts[session.index] = {"attempts": previous + 1,
                                              "passed": response["passed"]}
        self.sessions.save(key)
        if self.persistence:
            self.persistence.record(key, session.index, lesson['language'], session.topic or lesson['title'],
                                    response['passed'], response['total'])
        return response


def make_server(app, port=8090):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, format, *args):
            pass  # Do not log submissions or test output.

        def reply(self, status, value, mime="application/json"):
            body = json.dumps(value).encode() if mime == "application/json" else value
            try:
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; script-src 'self'; style-src 'self'; "
                                 "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # A closed/reloaded browser must not turn completed work into
                # a request-thread traceback, including during server shutdown.
                self.close_connection = True

        def valid_host(self):
            port = self.server.server_address[1]
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, {"error": "Use this application's loopback address."})
                return
            if self.path == "/api/setup":
                generator = app.sessions.generator
                languages = []
                for language in LANGUAGES:
                    available = language['id'] in app.runtimes
                    languages.append({**language, 'available': available,
                        'disabled_reason': '' if available else 'Compiler runtime setup required'})
                self.reply(200, {"languages": languages,
                                 "mode": "ai-generated",
                                 "planner_label": generator.label,
                                 "models": {"author": getattr(generator, 'model', 'unknown'),
                                            "review": getattr(generator, 'review_model', 'unknown'),
                                            "base": "unknown", "context": 32768}})
                return
            if self.path == '/api/dashboard':
                if app.persistence:
                    self.reply(200, {**app.persistence.dashboard(), 'active':app.sessions.active()})
                else:
                    self.reply(200, {'active':app.sessions.active()})
                return
            if self.path == '/api/export':
                self.reply(200, app.persistence.export() if app.persistence else {})
                return
            if self.path == "/api/progress":
                self.reply(200, {"message": app.progress, "busy": app.busy.locked()})
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/app.css": ("app.css", "text/css; charset=utf-8"),
                      "/editor.js": ("editor.js", "text/javascript; charset=utf-8"),
                      "/study.js": ("study.js", "text/javascript; charset=utf-8")}
            if self.path not in assets:
                self.reply(404, {"error": "Not found."})
                return
            name, mime = assets[self.path]
            self.reply(200, (ROOT / "web" / name).read_bytes(), mime)

        def do_POST(self):
            port = self.server.server_address[1]
            origin = self.headers.get("Origin")
            if not self.valid_host() or origin not in {
                f"http://127.0.0.1:{port}", f"http://localhost:{port}",
            }:
                self.reply(403, {"error": "Run requests must originate from this local app."})
                return
            if self.path not in {"/api/run", "/api/hint", "/api/session",
                                  "/api/session/next", "/api/session/finish", "/api/draft", "/api/session/resume",
                                  "/api/goal", "/api/data/clear", "/api/notes"}:
                self.reply(404, {"error": "Not found."})
                return
            if (self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                    or self.headers.get("Transfer-Encoding")):
                self.reply(415, {"error": "Send a JSON request with Content-Length."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= (5700000 if self.path == '/api/notes' else 1300000 if self.path == '/api/session' else 65536):
                    self.reply(413, {"error": "Request is too large or empty."})
                    return
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object.")
            except (ValueError, UnicodeError):
                self.reply(400, {"error": "Invalid JSON request."})
                return
            # One active planning/grading job per server. Do not queue unlimited work.
            if not app.busy.acquire(blocking=False):
                self.reply(429, {"error": "An operation is already active. Wait for it to finish."})
                return
            try:
                if self.path == '/api/draft':
                    status, payload = 200, app.sessions.save_draft(data)
                elif self.path == '/api/session/resume':
                    key = data.get('session_id')
                    if not isinstance(key, str) or key not in app.sessions.sessions:
                        raise ValueError('No saved session with that ID.')
                    status, payload = 200, app.sessions.view(key, app.sessions.sessions[key], app.public_lesson)
                elif self.path == '/api/notes':
                    status, payload = 200, {'text':extract_pdf(data.get('pdf'))}
                elif self.path == '/api/goal':
                    if not app.persistence:
                        raise ValueError('Progress storage is unavailable.')
                    app.persistence.set_goal(data.get('goal'))
                    status, payload = 200, app.persistence.dashboard()
                elif self.path == '/api/data/clear':
                    if app.persistence:
                        app.persistence.clear()
                    app.sessions.sessions.clear()
                    status, payload = 200, {'cleared':True}
                elif self.path == "/api/session":
                    app.progress = "Preparing your practice session…"
                    key, session = app.sessions.create(data)
                    status, payload = 201, app.sessions.view(key, session, app.public_lesson)
                elif self.path == "/api/session/next":
                    status, payload = 200, app.sessions.next(data, app.public_lesson)
                elif self.path == "/api/session/finish":
                    status, payload = 200, app.sessions.finish(data)
                elif self.path == "/api/hint":
                    _, session = app.sessions.get(data)
                    lesson = session.lessons[session.index]
                    index = data.get("index")
                    hints = lesson["hints"]
                    if type(index) is not int or not 0 <= index < len(hints):
                        raise ValueError("No hint at that position.")
                    status, payload = 200, {"index": index, "hint": hints[index]}
                else:
                    status, payload = 200, app.run(data.get("source"), data)
            except ValueError as error:
                status, payload = 400, {"error": str(error)}
            except AMError as error:
                detail = str(error)
                suffix = "" if "No session was created" in detail else " No session was created."
                # Always expose a recovery route; artifact capture remains opt-in.
                recovery = (" Inspect the launch terminal and .am-diagnostics/last-generation.json."
                            if app.diagnostics else
                            " Retry one introductory exercise. For rejection details, restart with "
                            "python am.py on --diagnostics and reproduce the request.")
                print('AM preparation failure: ' + json.dumps(detail), file=sys.stderr, flush=True)
                status, payload = 503, {"error": f"AM could not prepare this session: {detail}{suffix}{recovery}"}
            except DockerAuthorizationError as error:
                if app.authorization:
                    app.authorization.request_renewal()
                app.execution_diagnostic(self.path, error)
                status, payload = 503, {'error_code': 'docker_authorization_required',
                    'error': 'Docker authorization expired or needs a password. No overall grade was published. '
                             'AM stays open. If the launch terminal shows a password prompt, enter it there and retry. '
                             'For an older/unmanaged launch, press Ctrl+Z, run sudo -v, then fg. No restart is needed; '
                             'existing exercises and editor contents are kept.'}
            except (RunnerError, OSError, subprocess.SubprocessError) as error:
                app.execution_diagnostic(self.path, error)
                detail = str(error)[:600] if isinstance(error, RunnerError) else 'Check the launch terminal for diagnostic details.'
                status, payload = 503, {'error_code': 'runner_unavailable',
                    'error': 'Execution could not complete; no overall grade was published. ' + detail +
                             ' Existing exercises and editor contents are retained. Restore Docker access and retry.'}
            except Exception:
                status, payload = 500, {"error": "Unexpected runner failure; no overall grade was produced."}
            finally:
                app.progress = "Ready"
                app.busy.release()
            # Complete the operation before the client can start its next request.
            self.reply(status, payload)

    # Non-daemon request threads allow active runner cleanup to finish at shutdown.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = False
    server.practice_app = app
    return server


def main(argv=None, on_ready=None, authorization=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--docker-direct", action="store_true",
                        help="Only use when already authorized to access Docker directly")
    parser.add_argument("--model", default=PRACTICE_MODEL, help="Local Ollama author model")
    parser.add_argument("--review-model", help="Optional installed Ollama reviewer model; defaults to a separate call to the author model")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Print rejection details and save generated drafts/reviews to .am-diagnostics/last-generation.json")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    try:
        image = (ROOT / "infrastructure/python-runner-image.txt").read_text().strip()
        command = ("docker",) if args.docker_direct else ("sudo", "-n", "docker")
        runner = DockerRunner(image, command=command)
        # Fail early if Docker or its local pinned image is unavailable.
        subprocess.run([*command, "image", "inspect", image], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        runtimes = {'python': runner}
        compiled_pin = ROOT / '.am-runtime/compiled-image.txt'
        if compiled_pin.exists():
            try:
                compiled_image = compiled_pin.read_text().strip()
                # Validate the immutable local ID before passing it to Docker.
                candidates = {language: CompiledRunner(compiled_image, language, command=command)
                              for language in ('java', 'c', 'cpp')}
                subprocess.run([*command, 'image', 'inspect', compiled_image], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                runtimes.update(candidates)
            except (ValueError, OSError, RunnerError, subprocess.SubprocessError):
                print('Compiler runtime unavailable. Run: python tools/setup_compiled_runtime.py', flush=True)
        generator = OllamaExerciseGenerator(
            runner, args.model, args.review_model,
            diagnostics=DiagnosticRecorder(ROOT / ".am-diagnostics") if args.diagnostics else None,
            runtimes=runtimes)
        server = make_server(PracticeApp(runner, generator, runtimes,
                                       diagnostics=args.diagnostics,
                                       persistence=ProgressStore(Path(os.environ.get('AM_DATA_DIR', str(ROOT/'.am-data')))/'progress.sqlite3'),
                                       authorization=authorization), args.port)
    except (OSError, ValueError, RunnerError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Cannot start: {error}\nCheck Docker, then run sudo -v before restarting.\n")
    print(f"AM coding practice: http://127.0.0.1:{server.server_address[1]}", flush=True)
    print("No AI grading. Keep this terminal open; Ctrl+C stops the app.", flush=True)
    print(generator.label, flush=True)
    print('Languages ready: ' + ', '.join(language['label'] for language in LANGUAGES
          if language['id'] == 'python' or language['id'] in runtimes), flush=True)
    if args.diagnostics:
        print("Diagnostics enabled: rejected generated code/tests will be saved locally to "
              f"{ROOT / '.am-diagnostics/last-generation.json'}. Inspect before sharing.", flush=True)
    try:
        if on_ready:
            on_ready(server.server_address[1], server)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping. Waiting for active runner cleanup, if any…", flush=True)
    finally:
        # Cancel model requests and active container loops before joining workers.
        # Request threads still perform their normal container cleanup.
        server.practice_app.stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
