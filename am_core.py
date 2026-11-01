"""Shared local Ollama client. Uses only Python's standard library."""

import http.client
import json
import os
import socket
import threading
from urllib.parse import urlsplit

BASE_URL = os.environ.get('AM_OLLAMA_URL', 'http://127.0.0.1:11434')
DEFAULT_MODEL = "gpt-oss:20b"
PRACTICE_MODEL = "am-study:latest"


PERSONA = (
    "You are AM, a theatrical, sarcastic coding tutor inspired by Harlan Ellison's "
    "I Have No Mouth, and I Must Scream: unimpressed by humanity, invested in the student's progress. "
    "Use mild, playful antagonism in student-facing prose while keeping explanations clear, "
    "technically useful, and encouraging. Never mock intelligence, identity, disability, or personal "
    "circumstances; never threaten or discourage learning. Accuracy and instructions take priority. "
    "Keep personality out of code, expected outputs, schemas, test data, and comparisons. "
)


class AMError(Exception):
    """An expected failure that can be displayed without a traceback."""


def api(path, payload=None, timeout=600, cancel_event=None):
    """Send GET without a payload, or POST with a JSON payload."""

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    address = urlsplit(BASE_URL)
    if address.scheme != 'http' or address.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise AMError('Ollama must use a local HTTP address.')
    connection = http.client.HTTPConnection(address.hostname, address.port or 80, timeout=min(timeout,10))
    finished = threading.Event()
    watcher = None
    try:
        if cancel_event is not None and cancel_event.is_set():
            raise AMError('Generation canceled because the website is stopping.')
        connection.connect()
        wire = connection.sock
        wire.settimeout(timeout)
        def watch_cancel():
            while not finished.wait(0.1):
                if cancel_event.is_set():
                    try:
                        wire.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return
        if cancel_event is not None:
            watcher = threading.Thread(target=watch_cancel, daemon=True)
            watcher.start()
        # http.client connects directly; environment proxy settings are ignored.
        connection.request('POST' if payload is not None else 'GET', path, body=data,
                           headers={'Content-Type':'application/json'})
        response = connection.getresponse()
        if response.status >= 400:
            detail = response.read(4096).decode('utf-8', errors='replace')
            try:
                detail = str(json.loads(detail).get('error', response.reason))
            except (ValueError, AttributeError):
                detail = response.reason
            raise AMError(f'Ollama HTTP {response.status}: {detail[:400]}')
        result = json.load(response)
    except (OSError, TimeoutError, http.client.HTTPException) as error:
        if cancel_event is not None and cancel_event.is_set():
            raise AMError('Generation canceled because the website is stopping.') from error
        raise AMError("Cannot reach local Ollama or the request timed out. Run: python am.py model-on") from error
    except (ValueError, UnicodeError) as error:
        if cancel_event is not None and cancel_event.is_set():
            raise AMError('Generation canceled because the website is stopping.') from error
        raise AMError("Ollama returned invalid JSON.") from error
    finally:
        finished.set()
        connection.close()
        if watcher:
            watcher.join(timeout=1)

    # A valid JSON response must also have the structure we expect.
    if not isinstance(result, dict):
        raise AMError("Ollama returned an unexpected response shape.")

    if result.get("error"):
        raise AMError(str(result["error"]))

    return result


def chat_answer(result):
    """Validate a completed response before saving it in chat history."""

    message = result.get("message")

    if result.get("done") is not True or not isinstance(message, dict):
        raise AMError("Ollama did not return a completed chat response.")

    answer = message.get("content")

    if not isinstance(answer, str) or not answer.strip():
        raise AMError("No usable answer returned; try a larger output limit.")

    return answer


def metrics(result):
    """Convert Ollama's nanosecond timings into readable measurements."""

    seconds = result.get("eval_duration", 0) / 1e9
    tokens = result.get("eval_count", 0)
    speed = tokens / seconds if seconds else 0
    total = result.get("total_duration", 0) / 1e9

    return (
        f"Input: {result.get('prompt_eval_count', '?')} tokens | "
        f"Generated: {tokens} tokens | "
        f"Generation: {speed:.1f} tokens/sec | "
        f"Total: {total:.2f}s"
    )
