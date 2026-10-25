"""Shared local Ollama client. Uses only Python's standard library."""

import http.client
import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gpt-oss:20b"


class AMError(Exception):
    """An expected failure that can be displayed without a traceback."""


def api(path, payload=None, timeout=600):
    """Send GET without a payload, or POST with a JSON payload."""

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    # This connection is explicitly local. Don't route it through a proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    try:
        with opener.open(request, timeout=timeout) as response:
            result = json.load(response)

    except urllib.error.HTTPError as error:
        # Ollama often includes a useful explanation in its error response.
        detail = ""
        try:
            body = json.loads(error.read(4096).decode("utf-8"))
            detail = str(body.get("error", ""))[:400]
        except (ValueError, AttributeError):
            pass

        raise AMError(f"Ollama HTTP {error.code}: {detail or error.reason}") from error

    except urllib.error.URLError as error:
        raise AMError("Cannot reach local Ollama. Run: python am.py on") from error

    except (OSError, TimeoutError, http.client.HTTPException) as error:
        raise AMError("Connection failed or timed out. Check Ollama status.") from error

    except (ValueError, UnicodeError) as error:
        raise AMError("Ollama returned invalid JSON.") from error

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
