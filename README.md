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

## Next milestone

Complete desktop acceptance tests, save a Git checkpoint,
then prepare Open WebUI.
