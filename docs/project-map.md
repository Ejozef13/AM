# Project map and editing guide

AM is a local web app with a plain HTML/CSS/JavaScript interface and a Python
backend. It has no frontend build step or external Python packages. Ollama runs
the installed model; Docker compiles and executes submissions.

## Where to edit the interface

| What you want to change | File and location |
| --- | --- |
| Colors, fonts, rounded corners, page width | `web/app.css`: variables in `:root` at the top |
| Header, setup page title, form labels, buttons, footer | `web/index.html` |
| Header logo mark | `web/index.html`: `.brand` and `.brand-mark` |
| Page layout and spacing | `web/app.css`: Page, Setup form, and Exercise workspace sections |
| Mobile layout | `web/app.css`: Small screens section at the bottom |
| Text that changes during a session | `web/app.js`: `renderSession`, `renderResults`, and `another-session` handler |
| Test-result labels and language display names | `web/app.js`: `labels` and `languageLabels` near the top |
| Sample notes | `web/app.js`: `sample` click handler |
| Setup mode explanation | `web/app.js`: `/api/setup` response handler at the bottom |
| Circuit routes and activity | `web/app.js`: `drawCircuits`, `setBusy`; `web/app.css`: machine room section |
| Optional internet reference lookup | `web_retrieval.py`; checkbox in `web/index.html` |
| Generation progress text | `ai_exercises.py`: calls to `self.progress` |
| Supported languages and setup metadata | `study_input.py`: `LANGUAGES`; `practice_web.py`: `/api/setup` |

Start the app with `python am.py on --diagnostics`. Edit a frontend file, save,
and refresh the browser. No rebuild is needed. Refreshing during a session can
lose your current editor state; finish the session before editing the UI.
Backend changes require stopping and restarting the app.

Keep existing HTML `id` values unless you update their matching JavaScript
selectors too. Edit generated content with `textContent`, as the app currently
does, so notes and model output are displayed as text rather than executed HTML.
The stylesheet comments are section markers, not generated code.

## Repository outline

```text
AM/
├── am.py                       Public on/off/status and model-only commands
├── site_control.py             Website ownership, model loading, clean shutdown
├── sudo_session.py             Refresh/renew Docker credentials while AM runs
├── am_core.py                  Local Ollama HTTP client and model defaults
├── chat.py                     Optional terminal chat used by am.py chat
├── practice_web.py             Loopback HTTP server and browser API
├── practice_sessions.py        Session lifecycle, attempts, next, and summary
├── ai_exercises.py             AI author, blind review, repair, execution checks
├── language_contracts.py       Supported native types and function signatures
├── study_input.py              Student topic, notes, difficulty, language validation
├── progress_store.py           SQLite, activity, goals, and review schedule
├── learning_paths.py           Curriculum topic lists (no questions)
├── note_retrieval.py           Bounded PDF extraction and passage retrieval
├── web_retrieval.py            Opt-in Wikipedia excerpts, bounds, HTTPS transport
├── structures.py               Tagged encodings and Python node adapters
├── native_structures.py        Native node types/builders/serializers
├── generation_diagnostics.py   Optional local rejected-generation reports
├── code_runner.py              Container lifecycle and host-side result grading
├── compiled_runner.py          Java/C/C++ runner configuration
├── compiled_driver.py          Compile/run supervision inside the container
├── native_harness.py           Language-specific wrappers around solve(...)
├── lesson_validation.py        Structural checks and strict JSON comparisons
├── web/
│   ├── index.html              Page structure and static text
│   ├── app.css                 Theme, components, responsive layout
│   ├── app.js                  Browser state, API calls, drafts, results, summary
│   ├── editor.js               Highlighting, line numbers, indentation
│   └── study.js                Dashboard, resume, goals, paths, export/delete
├── tools/
│   ├── setup_compiled_runtime.py  One-time Java/C/C++ compiler setup
│   └── check_runner_runtime.py    Python runtime probe and image pinning
├── infrastructure/
│   ├── Modelfile               am-study alias built from gpt-oss:20b
│   ├── python-runner-image.txt Pinned Python runtime image
│   ├── compiled-runtime/      Compiler image definitions
│   ├── compose.yaml           Existing Open WebUI and search-service configuration
│   └── searxng/settings.yml   Existing search-service configuration
├── tests/                      Regression checks and optional Docker integration
└── docs/                       Current setup, architecture, limits, roadmap
```

There is no bundled exercise directory or question bank. Every question, starter,
reference, hint, and test set comes from the AI preparation pipeline. The editor
and results panel are the local coding workspace. Regression fixtures stay only
in `tests/`, where model and Docker responses can be checked repeatably; they are
not accessible as student practice content. Shared validators, image pins, and
runtime setup tools remain part of the app. Existing search configuration is
kept for the user's separate service; the practice generator does not call it.

## What happens when you build a session

```mermaid
flowchart TD
  A[Browser: language, topic, notes] --> B[HTTP API and session store]
  B --> C[Local Ollama: author draft]
  C --> D[Validate structure and calling convention]
  D --> E[Local Ollama: blind review]
  E --> F[Docker: check both solutions and starter]
  F --> G[Browser: exercise, editor, hints]
  G --> H[Docker: run student submission]
  H --> I[Host: compare actual and expected results]
  I --> J[Browser: evidence and session summary]
```

Invalid drafts receive bounded repair attempts. Unresolved failures stop
preparation; they never silently become another topic or a prewritten exercise.
The reviewer receives the task and notes, not the author's reference or tests.

## Runtime data outside Git

- `.am-data/`: SQLite saved sessions, drafts, activity, review schedules, goals.
- `.am-runtime/`: compiler pin, website ownership record, and lock.
- `.am-diagnostics/`: rejected generation reports when diagnostics are enabled.
- `.am-archive/`: existing local backups from the earlier cleanup.
- `infrastructure/.env.openwebui`: private service configuration.

These are machine-specific or private. This cleanup leaves them alone. Models
live in Ollama storage; Open WebUI chats live in its Docker volume. The practice app saves generated sessions, selected note excerpts, attempts, and
editor drafts in SQLite. Original PDFs are temporary and are not retained.
