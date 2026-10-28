# AM coding practice

Local, notes-guided debugging practice for Python, Java, C, and C++. Choose a
language, add a topic and optional notes, fix a short program, reveal hints, and
run its tests. Grading uses restricted execution and host-side comparisons.

## Start and stop

```bash
python am.py on --diagnostics
```

Open **http://127.0.0.1:8090** and keep the launch terminal open. This checks
Docker, starts the existing Ollama service if necessary, reports the configured
model's family/size, loads it, and starts the website. Models are not downloaded
and compiler images are not rebuilt. Start with one exercise per session.

Press **Ctrl+C** in the launch terminal to switch off, or use another terminal:

```bash
python am.py off
python am.py status
```

Shutdown cancels active model requests and container work, waits for cleanup,
and unloads only the models selected for the practice website. Shared Docker
and Ollama services remain available for Open WebUI. Sessions and editor drafts
are in memory; finish or save your work before switching off.

Stop an older `practice_web.py` with Ctrl+C once before using these commands.
An unrelated process on the requested port is never killed. Ownership records
live in Git-ignored `.am-runtime/`.

With sudo-based Docker, the launch terminal may ask for authorization. After an
idle credential expiry, keep the browser open, press Ctrl+Z in the launch terminal,
run `sudo -v`, then `fg` and retry. Existing direct Docker access is detected
automatically. Group memberships and sudo policies are unchanged.

## Your AI model

The website defaults to **`am-study:latest`**. The repository's
[Modelfile](infrastructure/Modelfile) derives it from **`gpt-oss:20b`** with a
32,768-token context. Startup reports metadata from the actual installed tag;
a name alone cannot establish which weights are installed on a machine.

An exercise normally uses two sequential calls to that local model: an author
and a blind reviewer. The reviewer sees the task and notes but not the author's
reference or tests. Both solutions must pass the combined cases; the starter
must demonstrate a failing result. Project files are not automatically read
into model context. There is no web search or RAG in this workflow.

Small structured tasks use low reasoning and request 3–5 small tests per call.
Compiled-language review schemas enforce declared types and the logical input
count. C array lengths are supplied by the runner, not extra JSON arguments.
Validation and bounded repair remain in place. Passing tests and model agreement
do not establish universal correctness.

Select other already-installed models with:

```bash
python am.py on --model am-study:latest --review-model YOUR_LOCAL_MODEL
```

If the alias is missing, with `gpt-oss:20b` already installed:

```bash
ollama create am-study -f infrastructure/Modelfile
```

## One-time language setup

Requirements: Python 3.10+, local Ollama and its installed model, and Docker on
Linux. Application code uses only Python's standard library. Preserve the
existing loopback-only Ollama/Open WebUI installation.

Python uses the pinned image in `infrastructure/python-runner-image.txt`.
To enable Java 21, C17, and C++17:

```bash
sudo systemctl start docker
sudo -v
python tools/setup_compiled_runtime.py
```

Wait for three compiler probes and `Compiler runtime ready`. Normal setup works
with legacy Docker builds and BuildKit. See [language setup and limits](docs/multilanguage-practice.md).

## Project layout

| Area | Responsibility |
| --- | --- |
| `am.py`, `site_control.py` | Website/model lifecycle and ownership |
| `practice_web.py`, `web/` | Local API and student interface |
| `ai_exercises.py`, `language_contracts.py` | Drafting, review, and typed contracts |
| `code_runner.py`, `compiled_runner.py`, `compiled_driver.py`, `native_harness.py` | Restricted execution and grading |
| `practice_sessions.py` | In-memory sessions and summaries |
| `exercise_families.py`, `practice_planner.py` | Explicit Python template modes |
| `tools/`, `examples/`, `tests/` | Setup, benchmarks, examples, and verification |
| `docs/history/` | Earlier milestones and terminal-client documentation |

Archive the recognized old untracked `study_app.py`/`study/` prototype reversibly:

```bash
python tools/archive_legacy.py          # Preview
python tools/archive_legacy.py --apply # Archive locally; never delete
```

Model-only commands remain explicit: `am.py model-on`, `model-status`, and
`model-off --model NAME`. `am.py chat` is the separate terminal client.
`practice_web.py` remains a direct website entry point. `--offline` and
`--templates` are Python-only options, never automatic fallbacks.

## Verification

```bash
python -m unittest discover -s tests -v
```

Default tests use controlled model/service fixtures. Optional real-container
checks and validation records are in [multilanguage practice](docs/multilanguage-practice.md).
`--diagnostics` stores rejected drafts locally in `.am-diagnostics/` and logs
bounded execution errors. Inspect generated content before sharing it. Token
counts and truncation reasons are recorded without saving hidden reasoning.
