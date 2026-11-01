# Validation, demo, and generation measurements

## Measured in this execution environment

| Check | Result | Elapsed |
| --- | --- | --- |
| Default regression discovery | 130 passed, 23 optional checks skipped | 24.825 s |
| Real Python runner suite | 17 passed | 52.363 s |
| Real Java/C/C++ runner suite | 10 passed | 489.727 s |
| New structure matrix + encoding checks | 3 test methods passed; 12 real calls across four languages | 138.629 s |
| Real HTTP/browser workflow | Passed | See repeatable smoke test below |

The structure matrix covers nonempty lists, sparse trees, cyclic adjacency
graphs, empty structures, and input mutation. Native compilation uses the actual
restricted container path. Docker here uses `vfs`; timings include container
creation and are not predictions of desktop performance.

The browser test checks PDF upload, goal changes, syntax highlighting, line
numbers, draft save, complete server restart, restore without regeneration,
hints, grading, summary, export/delete, and mobile overflow. Its model and runner
responses are controlled regression fixtures. It proves application behavior,
not a live model's question quality or latency.

Credential lifecycle checks use real controlled subprocesses rather than real
sudo/passwords. They verify refresh beyond a simulated expiry, terminal renewal,
immediate renewal requests from failed grading operations, and clean cancellation
on shutdown. Managed startup/stop is tested with controlled Docker/Ollama services.
The desktop's actual sudo policy remains authoritative; [details](docker-access.md).

## Demo artifacts

- [Setup/dashboard](screenshots/setup.png)
- [Editor, restored draft, and results](screenshots/exercise.png)
- [Session summary](screenshots/summary.png)
- [Mobile view](screenshots/mobile.png)
- [Short automated demo video](screenshots/demo.webm)

All artifacts above come from the controlled test workflow. The production app
has no question bank and cannot serve those fixtures.

Reproduce with optional browser dependencies:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python tests/browser_smoke.py --screenshots
```

Outputs go to ignored `benchmark-results/browser/`. The workflow in
`.github/workflows/checks.yml` runs Python regression checks, JavaScript syntax
checks, and this browser test, uploading screenshots/video as a CI artifact.
Remote CI status must be checked on GitHub; configuring it is not proof it ran.

## README walkthrough capture

The current README media was captured from the running application with
`tools/capture_readme_demo.py`. This is a separate development helper that imports
existing regression model/runner fixtures; it does not alter production behavior
or require Ollama, Docker execution, or private study data. All four runtime
availability flags are provided by controlled runners. The temporary SQLite
profile starts empty. The helper uses actual UI actions to reveal a hint, run a
failing starter, submit a passing fixture solution, open the summary, and save a
second unfinished session. The displayed one-day streak and history are produced
by that workflow, with no seeded completion history or clock changes.

With the optional Playwright dependency, Chromium, and a system `ffmpeg` binary
installed, reproduce the captures from the repository root:

```bash
python tools/capture_readme_demo.py
```

Use `--output /tmp/am-readme-demo` to inspect fresh captures without replacing
tracked assets. The helper records five PNGs in `docs/screenshots/readme-*.png`
and `docs/media/am-generation-loading.gif`. Earlier screenshots and `demo.webm`
above are retained as historical controlled-demo assets.

The GIF records the unchanged browser CSS while a controlled generation request
is held open. Circuit pulses have a three-second period during work; the
alternating logo glow has a four-second period. A twelve-second recording covers
both full cycles at ten frames per second. The GIF is 960 × 352 pixels and about
708 KiB. Its crop includes the logo, circuits, and greeting; preparation status
text is elsewhere on the full page. It indicates an active request, not literal
model reasoning, generation speed, or a measured inference run. The production
page respects reduced-motion preferences. ffmpeg encodes the browser screenshots;
no decorative frames or model behavior are invented.

No live Ollama model was available for these captures. This controlled workflow
cannot establish generation quality, container security, or desktop latency.

## Live GPT-OSS measurements

Live model measurements must be made against the installed desktop model.
Unit/browser fixtures and runner checks cannot establish its generation success
rate or latency. One-off benchmark JSON belongs in ignored `benchmark-results/`,
not in the application source tree.

Run a real preparation benchmark on the desktop, with no concurrent generation:

```bash
cd ~/Projects/AM
python am.py model-on
sudo -v
python tools/benchmark_generation.py --language c --topic "Linked lists" --samples 3 --output benchmark-results/c-linked-lists.json
```

Repeat for `python`, `java`, and `cpp`, using representative topics and enough
samples to expose failures. Keep runtime/model settings consistent. Reports
contain elapsed preparation time, accepted combined case counts, repair-stage
counts, final response token/completion metadata, failures, and installed model
details. Generated code, notes, and hidden reasoning text are not exported.

`preparation_rate` measures how many requested drafts passed the complete
review/execution pipeline. It is **not a correctness/learning score**. The median
includes successful and failed attempted runs and Docker/model overhead; the
first request may include model loading. An unavailable preflight records no
attempts. Reports are local and ignored by Git until deliberately reviewed and
published. Ctrl+C saves partial measurements with `status: interrupted`.
