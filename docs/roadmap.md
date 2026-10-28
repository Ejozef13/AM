# Product roadmap

## Working now

- Local practice website with Python, Java, C, and C++ choices.
- Topic and optional text/Markdown/code notes guide generated debugging exercises.
- Separate author and blind review calls, typed interfaces, and bounded repair.
- Restricted execution, test evidence, progressive hints, and session summaries.
- Managed on/off/status commands and independent Open WebUI chat.

This is a local prototype. Passing checks do not prove an exercise correct for
all inputs. Custom node parameters, public hosting, saved progress, PDF parsing,
web retrieval, and RAG are not implemented.

## Next: saved practice and a better editor

1. Add local SQLite persistence for completed sessions and skill history.
2. Save and restore editor drafts deliberately; add export and delete controls.
3. Show real completion history on a home screen.
4. Add a code editor with syntax highlighting, indentation, and line numbers.

Done means a student can finish a session, restart AM, and find their progress
and unfinished work without losing it. Streaks and XP should come from saved
activity; the current interface does not invent either.

## Then: guided learning

1. Track practiced skills and offer a short next session.
2. Introduce spaced review and difficulty adjustments based on actual attempts.
3. Add small learning paths, such as arrays → strings → searching.
4. Add opt-in daily goals and achievements after history exists.

Done means returning students have a useful next step and can explain why it
was recommended. A failed test alone is not a reliable mastery score.

## Expand exercise coverage

1. Define representations and harness support for linked lists, trees, and graphs.
2. Add invariant/property checks and stronger edge-case suites per topic.
3. Add writing-a-function and predicting-output activities alongside debugging.
4. Evaluate an optional distinct reviewer model with a repeatable benchmark.

Done means each new representation works end to end in all supported languages,
with documented boundaries and representative integration tests. Topic names
alone do not establish runner support.

## Add richer study material

1. Extract text from PDFs with size and format limits.
2. Chunk longer notes and retrieve relevant passages with source references.
3. Evaluate topic relevance and citation accuracy before adding web retrieval.

RAG supplies context; it does not replace code execution or validate answers by
itself. Add it when longer inputs justify it, rather than making every short
practice request depend on another service.

## Prepare a portfolio release

- Capture a short end-to-end demo and clear screenshots.
- Publish measured generation success/failure results across representative topics.
- Add CI for the default regression suite and document real Docker verification.
- Improve setup onboarding and accessibility based on student feedback.
- Choose licensing and contribution policies before inviting contributions.

Public hosting is a separate milestone: it needs authentication, per-user
isolation, quotas, and a reviewed execution boundary. The current local Docker
setup is not a public hostile-code service.
