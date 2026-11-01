# Release status and next work

## Implemented in this checkpoint

- SQLite saved sessions, resumable editor drafts, local export/delete controls.
- Local syntax highlighting, line numbers, tab indentation, and auto-indent.
- Learning-path topic selection, activity-based goals, streaks, and due reviews.
- Bounded linked-list, heap-indexed tree, and adjacency-graph inputs in Python,
  Java, C, and C++, with mutation checks and restricted execution.
- Text-based PDF extraction and local lexical retrieval for longer notes.
- Optional bounded Wikipedia reference excerpts with visible provenance; no arbitrary URL fetching.
- A repeatable browser demo, screenshots/video, GitHub Actions regression/browser
  configuration, and a live-model benchmark tool.

Every question still comes from the local AI author/review pipeline. No prewritten
questions or template fallback were reintroduced. Learning paths contain topics;
fixed regression fixtures are used only for verification and the labeled demo.

## Needs a desktop measurement

The cloud execution environment has Docker but no running GPT-OSS/Ollama model.
Real runner checks and the browser workflow were measured here. A live generation
preparation rate or latency cannot be inferred from those tests. Run the benchmark
on the desktop with the installed model; see [validation](validation.md).
CI configuration is committed; a GitHub workflow run must confirm its remote result.

## Further product work

- A richer editor with completion and compiler diagnostics linked to source lines.
- More adaptive study recommendations, calibrated against learning outcomes.
- Additional node output contracts, weighted graphs, and flexible tree encodings.
- Embedding retrieval, OCR, and source-quality evaluation if lexical retrieval
  proves insufficient for real notes.
- Import/migration for exported study data, multiple local profiles, and encryption
  options for sensitive notes.
- Public release licensing and contribution policies.

Public hosting remains a separate project: authentication, user isolation, quotas,
and a reviewed untrusted-code execution boundary are required. This release is
still designed for a single student running it locally.
