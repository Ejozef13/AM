# Project AM

A learning-first, local AI study assistant.

## Current capabilities

- Single-turn terminal chat through Ollama's local API
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

- Chat history is not yet implemented
- Benchmark results are exploratory
- Long-context retrieval has produced both correct and incorrect results

See docs/benchmark-notes.md for initial measurements 
