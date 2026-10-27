"""Local browser lesson backed by the existing Docker runner. No AI grading."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading

from code_runner import DockerRunner, RunnerError, grade_case
from am_core import AMError
from ai_exercises import OllamaExerciseGenerator
from generation_diagnostics import DiagnosticRecorder
from exercise_families import CATALOG
from practice_planner import LANGUAGES, KeywordPlanner, OllamaPlanner
from practice_sessions import SessionStore
from run_submission import load_lesson

ROOT = Path(__file__).resolve().parent


class PracticeApp:
    def __init__(self, lesson, runner, planner=None, generator=None):
        self.lesson = lesson
        self.runner = runner
        self.busy = threading.Lock()
        self.sessions = SessionStore(planner or OllamaPlanner(), runner, generator)
        self.progress = "Ready"
        if generator is not None:
            generator.progress = self.set_progress

    def set_progress(self, message):
        self.progress = message

    def public_lesson(self, lesson=None):
        # Explicit allowlist: reference solution, hints and answer keys stay off
        # the initial response. Hints are disclosed only when requested.
        keys = ("id", "title", "language", "difficulty", "instructions",
                "constraints", "skills", "starter_code")
        lesson = self.lesson if lesson is None else lesson
        return {**{key: lesson[key] for key in keys},
                "quality": {key: lesson["quality"][key] for key in
                            ("source", "separate_review", "distinct_models", "reference_runs")}
                           if "quality" in lesson else {"source": "reviewed-template"},
                "test_count": len(lesson["tests"]),
                "hint_count": len(lesson["hints"])}

    def run(self, source, session_data=None):
        # Source is passed only to the container, never exec'd on the host.
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Enter some Python code first.")
        if len(source.encode("utf-8")) > 16000:
            raise ValueError("Keep the submission below 16,000 UTF-8 bytes.")
        session = None
        lesson = self.lesson
        if session_data is not None:
            _, session = self.sessions.get(session_data)
            lesson = session.lessons[session.index]
        results = [grade_case(
            self.runner, source, lesson["entrypoint"], case,
            lesson["grading"]["forbid_input_mutation"],
        ) for case in lesson["tests"]]
        response = {"results": results, "passed": sum(r["status"] == "passed" for r in results),
                    "total": len(results), "complete": True}
        if session is not None:
            previous = session.attempts.get(session.index, {}).get("attempts", 0)
            session.attempts[session.index] = {"attempts": previous + 1,
                                              "passed": response["passed"]}
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

        def valid_host(self):
            port = self.server.server_address[1]
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, {"error": "Use this application's loopback address."})
                return
            if self.path == "/api/lesson":
                self.reply(200, app.public_lesson())
                return
            if self.path == "/api/setup":
                generator = app.sessions.generator
                self.reply(200, {"languages": LANGUAGES, "families": CATALOG,
                                 "mode": "ai-generated" if generator else "templates",
                                 "planner_label": generator.label if generator else app.sessions.planner.label})
                return
            if self.path == "/api/progress":
                self.reply(200, {"message": app.progress, "busy": app.busy.locked()})
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/app.css": ("app.css", "text/css; charset=utf-8")}
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
                                  "/api/session/next", "/api/session/finish"}:
                self.reply(404, {"error": "Not found."})
                return
            if (self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                    or self.headers.get("Transfer-Encoding")):
                self.reply(415, {"error": "Send a JSON request with Content-Length."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 65536:
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
                if self.path == "/api/session":
                    app.progress = "Preparing your practice session…"
                    key, session = app.sessions.create(data)
                    self.reply(201, app.sessions.view(key, session, app.public_lesson))
                elif self.path == "/api/session/next":
                    self.reply(200, app.sessions.next(data, app.public_lesson))
                elif self.path == "/api/session/finish":
                    self.reply(200, app.sessions.finish(data))
                elif self.path == "/api/hint":
                    lesson = app.lesson
                    if "session_id" in data:
                        _, session = app.sessions.get(data)
                        lesson = session.lessons[session.index]
                    index = data.get("index")
                    hints = lesson["hints"]
                    if type(index) is not int or not 0 <= index < len(hints):
                        raise ValueError("No hint at that position.")
                    self.reply(200, {"index": index, "hint": hints[index]})
                else:
                    self.reply(200, app.run(data.get("source"), data if "session_id" in data else None))
            except ValueError as error:
                self.reply(400, {"error": str(error)})
            except AMError as error:
                detail = str(error)
                suffix = "" if "No session was created" in detail else " No session was created."
                self.reply(503, {"error": f"AM could not prepare this session: {detail}{suffix}"})
            except (RunnerError, OSError, subprocess.SubprocessError):
                self.reply(503, {"error": "Exercise validation or execution could not complete. "
                            "No new session or overall grade was published. "
                            "Check Docker and sudo authorization in the launch terminal. "
                            "If needed, stop this server, run sudo -v, and restart it."})
            except Exception:
                self.reply(500, {"error": "Unexpected runner failure; no overall grade was produced."})
            finally:
                app.progress = "Ready"
                app.busy.release()

    # Non-daemon request threads allow active runner cleanup to finish at shutdown.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = False
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--docker-direct", action="store_true",
                        help="Only use when already authorized to access Docker directly")
    parser.add_argument("--offline", action="store_true", help="Use explicit keyword matching instead of AM planning")
    parser.add_argument("--templates", action="store_true", help="Use the previous reviewed-template mode")
    parser.add_argument("--model", default="am-study:latest", help="Local Ollama author model")
    parser.add_argument("--review-model", help="Optional installed Ollama reviewer model; defaults to a separate call to the author model")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Print rejection details and save generated drafts/reviews to .am-diagnostics/last-generation.json")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    try:
        lesson = load_lesson(ROOT / "exercises/python/largest_value.json")
        image = (ROOT / "infrastructure/python-runner-image.txt").read_text().strip()
        command = ("docker",) if args.docker_direct else ("sudo", "-n", "docker")
        runner = DockerRunner(image, command=command)
        # Fail early if Docker or its local pinned image is unavailable.
        subprocess.run([*command, "image", "inspect", image], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        planner = KeywordPlanner() if args.offline else OllamaPlanner(args.model)
        generator = None if args.offline or args.templates else OllamaExerciseGenerator(
            runner, args.model, args.review_model,
            diagnostics=DiagnosticRecorder(ROOT / ".am-diagnostics") if args.diagnostics else None)
        server = make_server(PracticeApp(lesson, runner, planner, generator), args.port)
    except (OSError, ValueError, RunnerError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Cannot start: {error}\nCheck Docker, then run sudo -v before restarting.\n")
    print(f"AM coding practice: http://127.0.0.1:{server.server_address[1]}", flush=True)
    print("No AI grading. Keep this terminal open; Ctrl+C stops the app.", flush=True)
    print(generator.label if generator else planner.label, flush=True)
    if args.diagnostics:
        print("Diagnostics enabled: rejected generated code/tests will be saved locally to "
              f"{ROOT / '.am-diagnostics/last-generation.json'}. Inspect before sharing.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping. Waiting for active runner cleanup, if any…", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
