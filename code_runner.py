"""Run one Python call per restricted Docker container."""

import json
import re
import selectors
import subprocess
import time
import uuid
from pathlib import Path


class RunnerError(Exception):
    """An infrastructure failure, not an incorrect student answer."""


class DockerAuthorizationError(RunnerError):
    """The sudo credential needed to start/clean up a container is unavailable."""


# This program executes INSIDE the container.
# Student source is never executed in the host process.
STRUCTURE_RUNTIME = (Path(__file__).resolve().parent / "structures.py").read_text()

DRIVER = STRUCTURE_RUNTIME + "\n" + r"""
import contextlib
import io
import json
import sys


class OutputLimit(Exception):
    pass


class BoundedOutput(io.StringIO):
    def __init__(self):
        super().__init__()
        self.exceeded = False

    def write(self, text):
        if self.tell() + len(text) > 2000:
            self.exceeded = True
            raise OutputLimit()
        return super().write(text)


# One newline-delimited request avoids waiting for Docker to forward stdin EOF.
data = json.loads(sys.stdin.readline())
output = BoundedOutput()

try:
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        namespace = {"__name__": "submission", "ListNode":ListNode, "TreeNode":TreeNode, "Graph":Graph}

        exec(
            compile(data["source"], "submission.py", "exec"),
            namespace,
        )

        function = namespace.get(data["entrypoint"])
        if not callable(function):
            raise ValueError("Required function is missing.")

        args = decode(data["args"])
        value = function(*args)

        if output.exceeded:
            raise OutputLimit()

        record = {
            "status": "ok",
            "value": encode(value),
            "args_after": encode(args, data["args"]),
        }

        # The result must be representable by our JSON protocol.
        json.dumps(record, allow_nan=False)

except OutputLimit:
    record = {
        "status": "output_limit",
        "message": "Submission printed too much output.",
    }

except SyntaxError as error:
    record = {
        "status": "syntax_error",
        "message": "Line %s: %s" % (error.lineno, error.msg),
    }

except BaseException as error:
    record = {
        "status": "runtime_error",
        "message": type(error).__name__ + ": " + str(error)[:300],
    }

record["output"] = output.getvalue()
print(json.dumps(record, allow_nan=False))
"""


def equivalent(first, second):
    """Compare JSON values without treating True as integer 1."""
    try:
        return json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
            second, sort_keys=True, allow_nan=False
        )
    except (TypeError, ValueError):
        return False


class DockerRunner:
    payload_limit = 32000
    memory = "128m"
    pids = "32"
    nofile = "64:64"
    cpu_limit = "2:2"
    temporary_filesystem = "/tmp:rw,noexec,nosuid,nodev,size=16m"
    driver = DRIVER

    def valid_image(self, image):
        return re.fullmatch(r"(?:docker\.io/library/)?python@sha256:[0-9a-f]{64}", image)

    def __init__(
        self,
        image,
        command=("sudo", "-n", "docker"),
        wall_seconds=15,
    ):
        if not self.valid_image(image):
            raise RunnerError("Use the immutable runtime image ID or digest saved by setup.")

        self.image = image
        self.command = list(command)
        self.wall_seconds = wall_seconds
        self.cancel_event = None

    def remove(self, name):
        """Remove only the uniquely named container we created."""
        for attempt in range(2):
            try:
                result = subprocess.run(self.command + ["rm", "-f", name],
                                        capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired as error:
                if attempt == 0:
                    continue  # Removal may already have completed on the daemon.
                raise RunnerError('Could not confirm container cleanup after two attempts.') from error
            if not result.returncode:
                return True
            self.check_authorization(result.stderr)
            if 'No such container' in result.stderr:
                return False
            if attempt == 0 and 'removal of container' in result.stderr and 'in progress' in result.stderr:
                continue
            raise RunnerError('Could not confirm container cleanup: ' + result.stderr[:400])

    def check_authorization(self, output):
        if (self.command and self.command[0].rsplit('/', 1)[-1] == 'sudo'
                and 'sudo:' in output.lower()
                and any(text in output.lower() for text in
                        ('password is required', 'a terminal is required', 'authentication is required'))):
            raise DockerAuthorizationError('Docker sudo authorization is unavailable or expired.')

    def run(self, source, entrypoint, args):
        """Execute one function call with bounded input and output."""
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise RunnerError('Execution canceled because the website is stopping.')
        if not isinstance(source, str) or len(source.encode()) > 16000:
            raise RunnerError("Submission must be at most 16,000 UTF-8 bytes.")

        if not isinstance(entrypoint, str) or not entrypoint.isidentifier():
            raise RunnerError("Invalid entrypoint.")

        if not isinstance(args, list):
            raise RunnerError("Test arguments must be a list.")

        payload = json.dumps(self.request_payload(source, entrypoint, args), allow_nan=False).encode() + b'\n'

        if len(payload) > self.payload_limit:
            raise RunnerError("Submission and test inputs exceed the prototype limit.")

        name = "am-case-" + uuid.uuid4().hex

        command = self.command + [
            "run",
            "--name",
            name,
            "--pull",
            "never",
            "--log-driver",
            "none",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--memory",
            self.memory,
            "--memory-swap",
            self.memory,
            "--cpus",
            "0.5",
            "--pids-limit",
            self.pids,
            "--ulimit",
            "nofile=" + self.nofile,
            "--ulimit",
            "cpu=" + self.cpu_limit,
            "--tmpfs",
            self.temporary_filesystem,
            "-i",
            self.image,
            "python",
            "-I",
            "-B",
            "-u",
            "-c",
            self.driver,
        ]

        process = None
        captured = bytearray()
        deadline = time.monotonic() + self.wall_seconds

        try:
            # Finish creation before attaching input or starting student code.
            # Killing a combined `docker run` during image setup can leave a
            # daemon-side create request that registers after cleanup returned.
            create_command = list(command)
            create_command[len(self.command)] = 'create'
            created = subprocess.run(create_command, capture_output=True, text=True,
                                     timeout=max(60,self.wall_seconds))
            if created.returncode:
                self.check_authorization(created.stderr)
                raise RunnerError('Docker could not create the test container: '+created.stderr[:500])
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise RunnerError('Execution canceled because the website is stopping.')
            deadline = time.monotonic()+self.wall_seconds
            process = subprocess.Popen(
                self.command + ['start','--attach','--interactive',name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # Nonblocking pipes prevent input/output from trapping the host.
            import os

            os.set_blocking(process.stdin.fileno(), False)
            os.set_blocking(process.stdout.fileno(), False)
            offset = 0

            with selectors.DefaultSelector() as selector:
                selector.register(process.stdin, selectors.EVENT_WRITE)
                selector.register(process.stdout, selectors.EVENT_READ)

                while selector.get_map():
                    if self.cancel_event is not None and self.cancel_event.is_set():
                        raise RunnerError('Execution canceled because the website is stopping.')
                    remaining = deadline - time.monotonic()

                    if remaining <= 0:
                        return {
                            "status": "timeout",
                            "message": "Wall-time limit reached.",
                        }

                    for key, _ in selector.select(min(remaining, 0.1)):
                        if key.fileobj is process.stdin:
                            try:
                                offset += os.write(
                                    process.stdin.fileno(),
                                    payload[offset : offset + 4096],
                                )
                            except BrokenPipeError:
                                offset = len(payload)

                            if offset == len(payload):
                                selector.unregister(process.stdin)
                                process.stdin.close()

                        else:
                            chunk = os.read(process.stdout.fileno(), 4096)

                            if not chunk:
                                selector.unregister(process.stdout)
                            else:
                                captured.extend(chunk)

                                if len(captured) > 16384:
                                    return {
                                        "status": "output_limit",
                                        "message": "Captured output limit reached.",
                                    }

            try:
                code = process.wait(
                    timeout=max(
                        0.01,
                        deadline - time.monotonic(),
                    )
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "message": "Wall-time limit reached.",
                }

            # Docker startup failures are not learner failures.
            if code:
                self.check_authorization(captured.decode(errors='replace'))
            if code in {125, 126, 127}:
                raise RunnerError(
                    "Docker could not execute the test: "
                    + captured.decode(errors="replace")[:500]
                )

            if code:
                return {
                    "status": "execution_error",
                    "message": f"Container exited with code {code}; "
                    "no result accepted.",
                }

            try:
                result = json.loads(captured)
            except (ValueError, UnicodeError):
                return {
                    "status": "protocol_error",
                    "message": "Submission did not return a usable runner response.",
                }

            allowed = {
                "ok",
                "output_limit",
                "syntax_error",
                "runtime_error",
                "compile_error",
                "timeout",
            }

            if (
                not isinstance(result, dict)
                or result.get("status") not in allowed
                or (
                    result["status"] == "ok"
                    and not {"value", "args_after"} <= result.keys()
                )
            ):
                return {
                    "status": "protocol_error",
                    "message": "Malformed runner response.",
                }

            return result

        finally:
            # Release attached streams before removing a noisy container.
            if process:
                for pipe in (process.stdin, process.stdout):
                    if pipe and not pipe.closed:
                        pipe.close()

            # Stopping the Docker client alone doesn't stop its container.
            removed = False
            try:
                removed = self.remove(name)

            finally:
                if process:
                    try:
                        process.wait(timeout=5)

                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except PermissionError:
                            subprocess.run(
                                [
                                    "sudo",
                                    "-n",
                                    "kill",
                                    "-KILL",
                                    str(process.pid),
                                ],
                                check=True,
                                timeout=5,
                            )

                        process.wait(timeout=5)

                    for pipe in (process.stdin, process.stdout):
                        if pipe and not pipe.closed:
                            pipe.close()
                if not removed:
                    # A Docker create request can finish after an early rm saw no
                    # container. Recheck after the client has exited or been killed.
                    removed = self.remove(name)
                    if not removed and process is not None:
                        # The daemon can finish a slow create after its client
                        # has exited. Drain that request within the startup
                        # allowance, then remove only our unique container.
                        cleanup_deadline = max(deadline, time.monotonic()+10)
                        while not removed and time.monotonic() < cleanup_deadline:
                            time.sleep(0.2)
                            removed = self.remove(name)

    def request_payload(self, source, entrypoint, args):
        return {"source": source, "entrypoint": entrypoint, "args": args}


def grade_case(
    runner,
    source,
    entrypoint,
    case,
    forbid_mutation=False,
):
    """Compare actual values on the host; ignore any student 'pass' claim."""
    observed = runner.run(source, entrypoint, case["args"])

    if observed["status"] != "ok":
        return {"name": case["name"], **observed}

    mutation = not equivalent(
        observed["args_after"],
        case["args"],
    )

    passed = equivalent(observed["value"], case["expected"]) and not (
        forbid_mutation and mutation
    )

    return {
        "name": case["name"],
        "status": "passed" if passed else "failed",
        "expected": case["expected"],
        "actual": observed["value"],
        "input_modified": mutation,
        "output": observed.get("output", ""),
    }
