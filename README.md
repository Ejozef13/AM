# Project AM

A learning-first, local AI study assistant.

## Current capabilities

- Multi-turn terminal chat through Ollama's local API
- In-memory conversation history and /bye command
- Synthetic long-context retrieval probe
- Initial GPU inference benchmarks

## Development setup

Python 3.14 was used for initial testing.
The clients use only Python's standard library.

Ollama must be running locally with gpt-oss:20b downloaded.
Cloud functionality is disabled in the local service configuration.

Run:

    python chat.py
    python context_probe.py

The context probe uses generated fictional records.
Model weights are managed separately by Ollama.

## Current limitations

- Connection failures display a message and allow another attempt
- Failed requests are excluded from conversation history

See docs/benchmark-notes.md for initial measurements 
