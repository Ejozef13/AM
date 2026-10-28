# Execution and grading

Every student exercise starts as an AI draft and independent review. There are
no bundled exercise files or standalone default questions. The browser's coding
workspace shows the generated starter and lets the student edit code, request
hints, run tests, and inspect expected/actual results.

The session owns the task and tests. Both `/api/run` and `/api/hint` require a
valid session ID and current exercise index. The old `/api/lesson` endpoint is
removed. Generated reference solutions and hidden test data remain on the server
until results or hints are requested through the supported workflow.

## Architecture

`ai_exercises.py` validates draft structure using `lesson_validation.py` and
checks author/reviewer solutions using the same runner as student submissions.
Student source and inputs enter a restricted container; expected results stay
on the host, where actual results are compared. AI does not grade submissions.

Each test uses a fresh container with a pinned runtime, no external network,
no project-directory mounts, an unprivileged user, a read-only root filesystem,
a temporary workspace, dropped capabilities, and resource/output limits.
This is a local prototype, not a public hostile-code execution service.

Syntax errors and runtime errors are returned as test evidence. Infrastructure
failures produce no overall grade. The app keeps the session and persists drafts/progress so the
student can restore Docker access and retry. Passing cases is not proof for all
possible inputs.

## Regression checks

```bash
python -m unittest discover -s tests -v
```

Real Python container checks, with Docker running:

```bash
sudo -v
env AM_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_code_runner.py -v
```

Default discovery skips optional Docker integration checks. Controlled examples
inside `tests/` exist only to test the software, never as a question bank.
See [compiled-language setup](multilanguage-practice.md) for Java, C, and C++.
