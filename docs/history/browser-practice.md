# Browser lesson prototype

This document records the original single-lesson milestone. For the current
notes-guided setup and multi-exercise workflow, see [notes-guided practice](notes-guided-practice.md).

## Student workflow

1. Read the largest-value debugging task and its requirements.
2. Edit the starter function in the browser.
3. Explicitly choose Run tests.
4. Inspect actual and expected returns, mutation warnings, or execution errors.
5. Reveal reviewed hints one at a time when needed.
6. Fix the code and run again; reset to the starter with confirmation if desired.

This milestone has one lesson, not yet the complete five-lesson study path.
Neither AI hints nor accounts, persistent progress, or automatic grading on each
keystroke are implemented.

## Files and boundaries

- `practice_web.py`: loopback HTTP server and grading orchestration.
- `web/index.html`: task, requirements, editor, results, and hints.
- `web/app.css`: responsive layout.
- `web/app.js`: UI state and API calls; never evaluates submission code.
- `tests/test_practice_web.py`: HTTP/service tests using simulated runner results.
- `code_runner.py`: existing per-test Docker runner; unchanged by this milestone.

The lesson remains the single source for prompts, reviewed hints, and tests.
The initial lesson endpoint explicitly includes only public fields. Reference
solution code, hints, and expected answers are not included in that response.
Hints are returned individually on request. After a run, expected and actual
values are deliberately shown for these public learning tests. These are not
hidden interview tests or an anti-cheating system.

## Launch and permissions

From the project root, run `sudo -v` and then `python practice_web.py` as your
normal user. The runner uses `sudo -n docker`; it never accepts a sudo password
from the browser. Authorization can expire. In that case restart the app after
refreshing authorization in the launch terminal. Don't grant passwordless Docker
access just for this prototype. A production executor requires a different
privilege boundary and is out of scope here.

The default address is `http://127.0.0.1:8090`. The existing Open WebUI remains
on its own port. `--port` selects a different local port. `--docker-direct` is
only for environments already authorized to use Docker directly; it doesn't
change group membership or privileges.

## Request handling

Static assets use an explicit allowlist. Model/student output is rendered as
text, never inserted as HTML. POST requests must originate from this loopback
application and supply JSON. Host validation also rejects unrelated hostnames.
Request and source sizes are bounded. Only one grading job runs at a time.
Reference solutions cannot be fetched through the static-file endpoint.

Infrastructure errors produce no overall grade. A failed test is a normal test
result, not an infrastructure error. Source is passed only into the container,
never executed by the server. Stopping the server waits for active request
threads so their runner cleanup can finish. These measures are not a claim that
Docker or this prototype is a production-grade untrusted-code sandbox.

## Validation performed in the development environment

- Eleven HTTP/service tests passed using a simulated runner.
- JavaScript syntax was checked with Node.
- Live Chromium workflow passed against real Docker execution: starter 6/8,
  corrected code 8/8, stale-result warning after edits, three progressive hints,
  hints exhausted, and reset with confirmation. No page JavaScript errors were
  reported. Desktop and narrow viewport layouts were visually inspected.
- Existing terminal and runner tests remain applicable.

## Desktop acceptance checks

1. `sudo -v`, then `python practice_web.py`.
2. Open the loopback address in a desktop browser.
3. Run the unchanged starter: expect 6/8 and the two negative-only failures.
4. Reveal all three hints individually; the button should then be disabled.
5. Repair the initialization and run again: expect 8/8.
6. Edit after a run: results should be marked as belonging to previous code.
7. Reset and accept confirmation: starter restored, results cleared.
8. Introduce a syntax error: expect syntax-error test results, not a false pass.
9. Stop with Ctrl+C; check that no `am-case-` containers remain.

Code and hints are not persisted. Refreshing loses unsaved editor changes and
hint progression. Existing source files are not overwritten by browser edits.
