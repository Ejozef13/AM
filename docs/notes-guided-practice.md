# Notes-guided practice: approach one

This records the template-generation milestone. The default now uses
[AI-generated practice](ai-generated-practice.md); this mode remains available
through `--templates` or `--offline`.

## User workflow

1. Choose a language. Python is available; Java, C, and C++ are labeled planned.
2. Enter a study topic, paste notes, or add a small text/Markdown/code file.
3. Choose a difficulty and one to five exercises.
4. AM suggests a relevant supported practice family and a short focus explanation.
5. The application generates reviewed variants and validates each reference in Docker.
6. Attempt each exercise, reveal progressive hints, run tests, and advance.
7. Review the latest results and attempt counts in a session summary.

No new services, packages, or model downloads are required. Existing Ollama,
Open WebUI, and the test runner configuration are left intact.

## Responsibilities

- `practice_planner.py`: validates study inputs; asks the local model to select
  among the catalog. A plan contains no code, tests, commands, or answer key.
  Provided notes are treated as data. Quotes must be exact substrings of notes.
- `exercise_families.py`: reviewed Python templates and independent reference
  oracles produce starter code, reference code, test inputs, and expected outputs.
- `practice_sessions.py`: holds bounded, ephemeral sessions, validates generated
  references using the real runner, checks that a known case exposes the starter
  bug, and manages navigation and summaries.
- `practice_web.py`: loopback-only API and existing host-side grading integration.
- `web/`: study setup, file-to-text reading, exercise UI, notes evidence, and summary.

The model suggests intent; the application owns executable exercise structure.
An exact notes quote verifies provenance only. It does not prove that the selected
family is relevant. Students can inspect "Why this focus?" and start over if needed.

## Current family coverage

Minimum/maximum uses initialization and loop-boundary bugs. Counting covers even
numbers, strictly positive numbers, and occurrences of a target, with counter
initialization, early-return, and skipped-element bugs. First-index search covers
absent sentinels, duplicate matches, and skipped-final-element bugs.

Seeds reproduce exact variants. Difficulty changes generated inputs and permitted
bug patterns; it is not a calibrated assessment of student ability. Sessions can
repeat a task or bug pattern while varying cases. This is not an unrestricted
problem generator or the future randomizer (approach two).

Every reference must pass all generated cases before the session is published.
The starter must fail its designated regression with an incorrect return, not
merely crash. Failed preparation publishes no partial session. No student grade
is produced when execution infrastructure fails.

## Uploads and retention

Supported files: `.txt`, `.md`, `.markdown`, `.py`, `.java`, `.c`, `.cpp`, `.h`,
and `.hpp`. The browser reads one file at a time as UTF-8 text. Files append to
existing pasted notes rather than replacing them. File size is capped at 48 KB,
and combined notes at 12,000 characters. Unsupported formats/binary text are
rejected. Filenames are displayed as text, not HTML. File contents are notes,
not code to execute. No notes are sent to a web search service.

The local Ollama planner receives topic and notes. The server retains only the
selected plan/excerpt, generated lessons, and numeric attempt results in RAM.
No notes, source drafts, or progress are saved by this app to disk. The browser
retains text in the current tab; refreshing abandons visible state. This is not
secure memory erasure. Up to 24 sessions remain for at most two hours, and are
removed on normal session completion or server restart.

## Running

```bash
sudo -v
python am.py on
python practice_web.py
```

The default planner model is `am-study:latest`. `--model` changes it. Open the
existing loopback address on port 8090. A planning error is explicit; it does not
silently fall back to a different model or a fixed unrelated lesson.

For offline development, `python practice_web.py --offline` enables labeled
keyword matching. It requires an explicit matching topic or notes and still uses
the real Docker checker. It does not claim to semantically understand notes.

Docker authorization can expire as before. Stop the app, refresh `sudo -v` in
the launch terminal, and restart. Never launch the application itself as root or
add passwordless Docker access for this prototype.

## Tests and limits

```bash
python -m unittest discover -s tests -v
```

Family tests check 270 seeded variants across three families and difficulties,
including reference outputs, input preservation, and designated starter failures.
These tests execute only fixed reviewed author templates, not uploaded/student
or model-generated source. Actual student code always uses Docker.

Planner tests simulate model responses and reject malformed plans, unsupported
families, invented quotes, and incomplete generations. Session tests cover
isolation, stale requests, expiration, validation failures, navigation, and summary.
Existing runner integration tests remain explicitly opt-in.

Validation for this milestone: the default suite ran 57 tests, with 45 passing
and 12 opt-in Docker tests skipped. A separate Chromium workflow used the real
Docker runner in explicit offline-planner mode: unsupported topic rejection,
notes upload, two-exercise preparation, hints, an 8/8 submission, navigation,
unattempted-item summary, and mobile layout were checked. No containers remained
after the workflow. This browser check did not exercise a live Ollama model.

Live Ollama planning must also be checked on the desktop where the model runs.
Passing contract tests does not establish model selection quality. New language
support requires reviewed exercise families, runner adapters, and checks; enabling
a button alone is insufficient. Hints currently come from reviewed templates.
