# Validation, demo, and generation measurements

## Measured in this execution environment

| Check | Result | Elapsed |
| --- | --- | --- |
| Default regression discovery | 123 passed, 23 optional checks skipped | 19.460 s |
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

## Live GPT-OSS measurements

There is no running Ollama/model in this cloud environment. The recorded
[environment report](generation-environment.json) has `status: unavailable`,
zero attempted generations, and null success-rate/latency fields. It would be
misleading to report fixture or runner results as live generation accuracy.

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
