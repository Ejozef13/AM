# Project AM

A learning-first, locally hosted AI study assistant.

## Requirements

- Python 3.10 or newer
- Local Ollama service
- Downloaded gpt-oss:20b model
- Working GPU inference backend

No third-party Python packages are required.

The existing Ollama service should remain bound to loopback with
OLLAMA_NO_CLOUD=1. These programs do not change those settings.

## Files

- am_core.py: shared local HTTP client and response validation
- chat.py: interactive chat and temporary conversation history
- am.py: startup, status, chat, and model unloading
- context_probe.py: synthetic retrieval benchmark
- tests/test_terminal.py: offline behavioral tests
- docs/benchmark-notes.md: initial experimental observations

## Commands

Run from the project directory:

```bash
python am.py on
python am.py status
python am.py chat
python am.py off
```

`on` starts the existing Ollama service and checks API readiness.
It does not enable startup at boot.

`off` unloads gpt-oss:20b and leaves Ollama running.
It does not delete model files or stop other services.
Close other clients using the selected model before unloading it.

To unload a different installed model:

```bash
python am.py off --model qwen3:14b
```

## Chat commands

- /help: show command help
- /status: show settings, history count, and loaded models
- /clear: reset this client's conversation history
- /bye: exit the client

History exists only in RAM and is not saved between sessions.
Clearing history does not securely erase process memory or server caches.

Failed requests are not added to history.
Interrupted requests may still finish on the server.
Exiting chat does not immediately unload the model.

## History limits

Default settings:

- 8,192-token context
- 1,500-token generation limit
- Six successful exchanges
- 12,000-character text budget

The client requests an explicit /clear when its bounds are reached.
It does not automatically summarize or silently discard old turns.

Character limits and previous token measurements are not exact preflight
token counting. They cannot guarantee the server never truncates input.

Inspect options:

```bash
python chat.py --help
```

The default reasoning setting is low, matching GPT-OSS.
Other models may require different reasoning settings.

## Tests

```bash
python -m unittest discover -s tests -v
```

These tests simulate responses and service operations.
They do not establish live GPU readiness.

## Benchmark

```bash
python context_probe.py --records 600 --seed 42
python context_probe.py --records 1800 --seed 43
```

Optionally save raw evidence outside the repository:

```bash
python context_probe.py --records 1800 --seed 43 --output /tmp/am-probe-43.json
```

Existing output files are not overwritten.

The probe scores exact values using structured JSON output.
This differs from the original free-text benchmark.
Keep both sets of observations separately.

Repeated input can benefit from prompt caching.
Different models may use different tokenizers and reasoning settings.
Generation throughput is not the same as end-to-end latency.
One successful run does not establish general accuracy or hardware limits.

## AI-generated coding practice

The browser starts with "What are we studying today?" Choose a language, enter a topic,
and paste notes or add a small text/Markdown/code file. AM authors a debugging
exercise, starter, solution, hints, and tests. A separate, blind review call derives
another solution and more tests without seeing the author's solution or tests.
Both solutions must pass the combined cases in the restricted Docker runner,
and the starter must expose a logic bug before the exercise is published.

```bash
sudo systemctl start docker
sudo -v
python am.py on
python practice_web.py
```

Open `http://127.0.0.1:8090`. Start with one exercise; generation, review, and
container checks can take several minutes. The page reports preparation stages.
Practice, reveal hints, run tests, and review the session summary. Keep the
terminal open; Ctrl+C stops the app. Do not launch the app itself as root.

The author defaults to `am-study:latest`. The reviewer defaults to a separate call
to that same model, which is **not independent evidence from a different model**.
To use another already-installed model:

```bash
python practice_web.py --model am-study:latest --review-model YOUR_INSTALLED_MODEL
```

AI agreement and passing tests do not prove correctness. The runner determines
student test results; no AI decides pass/fail. Model-authored code, like student
code, executes only in restricted containers. This is a local prototype, not a
public hostile-code service.

Python works with the existing runner. To enable Java 21, C17, and C++17, build
and probe the compiler runtime once, then restart the website:

```bash
sudo -v
python tools/setup_compiled_runtime.py
python practice_web.py --diagnostics
```

The setup builds a local Docker image containing the compilers; it does not change
Ollama or Open WebUI. Language buttons become available after all three compiler
probes pass and the app restarts. See [language setup and supported exercises](docs/multilanguage-practice.md).

PDF/slides, persistent progress, web research, and document retrieval are not implemented. The provided
notes are sent directly to local Ollama as numbered excerpts. AM selects an
excerpt ID; the app inserts the original text rather than asking AM to copy it.
There is no web search or automatic source verification in this milestone.

Previous template modes remain explicit options:

```bash
python practice_web.py --templates  # AM selects among reviewed families
python practice_web.py --offline    # Keyword selection; no model calls
```

Those older template modes support Python only.

A failed generated draft never silently becomes a template question. Each
exercise gets at most two drafts; if preparation fails, no partial session is
published. Original runner commands and exercises remain available.

Reviewer failures now repair the review separately. When both solutions disagree
with a reviewer's expected answer, the reviewer can explicitly approve a targeted
expected-value correction; unchanged code and inputs are preserved, and the
corrected case must pass execution again. Failed corrections abort preparation.
They do not silently change test answers, remove failing cases, or regenerate an
otherwise valid author question.

For troubleshooting, launch with `--diagnostics`. Rejected generated code and
tests are saved locally to `.am-diagnostics/last-generation.json` (Git-ignored,
owner-only on creation). Inspect its generated content before sharing it. Normal
launches do not save this trace. Syntax errors now report the code role and line.

```bash
python -m unittest discover -s tests -v
```

See [AI-generated practice](docs/ai-generated-practice.md) for the architecture,
checks, limitations, and validation record. Earlier milestones are documented in
[notes-guided practice](docs/notes-guided-practice.md) and
[browser practice](docs/browser-practice.md).
