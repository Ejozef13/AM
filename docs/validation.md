# Validation, demo, and generation measurements

## Measured in this execution environment

| Check | Result | Elapsed |
| --- | --- | --- |
| Default regression discovery | 148 passed, 25 optional checks skipped | 24.064 s |
| Real Python runner suite | 17 passed | 52.363 s |
| Real Java/C/C++ runner suite | 10 passed | 489.727 s |
| New structure matrix + encoding checks | 3 test methods passed; 12 real calls across four languages | 138.629 s |
| Printable-ASCII protocol regression + real transport | 4 methods passed; 5 real Java/C++/C calls | 96.804 s |
| Author expectation typo regression | 3 methods passed; 5 real Java container calls | 95.676 s |
| Real HTTP/browser workflow | Passed | See repeatable smoke test below |

The structure matrix covers nonempty lists, sparse trees, cyclic adjacency
graphs, empty structures, and input mutation. Native compilation uses the actual
restricted container path. Docker here uses `vfs`; timings include container
creation and are not predictions of desktop performance.

The browser test checks retrieval status/source links, correct diagnostic download,
PDF upload, goal changes, syntax highlighting, line
numbers, draft save, complete server restart, restore without regeneration,
hints, grading, summary, export/delete, and mobile overflow. Its model and runner
responses are controlled regression fixtures. It proves application behavior,
not a live model's question quality or latency.

The Java expectation regression reproduces a mistyped expected reversal while
two independently supplied programs agree on the correct result. It uses a
controlled AI verification response, then executes the corrected expectation
against both real programs and checks the buggy starter. The model cannot write
replacement answers in this verification step. The raw uploaded diagnostic is
not committed. Real public search was unavailable in this environment; retrieval
and its failure disclosure have controlled unit/browser coverage. Desktop search
availability and live GPT-OSS quality still need desktop measurements.

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
python tools/benchmark_generation.py --language java --topic "printing" --web-search --samples 3
```

Repeat for `python`, `java`, and `cpp`, using representative topics and enough
samples to expose failures. Keep runtime/model settings consistent. Reports
contain elapsed preparation time, accepted combined case counts, repair-stage
counts, final response token/completion metadata, failures, and installed model
details. Generated code, notes, and hidden reasoning text are not exported.
The default output is `benchmark-results/preparation-benchmark.json`, a different
report type from the failed-session diagnostic downloaded from the app.

`preparation_rate` measures how many requested drafts passed the complete
review/execution pipeline. It is **not a correctness/learning score**. The median
includes successful and failed attempted runs and Docker/model overhead; the
first request may include model loading. An unavailable preflight records no
attempts. Reports are local and ignored by Git until deliberately reviewed and
published. Ctrl+C saves partial measurements with `status: interrupted`.

## Printable-ASCII regression

The uploaded Java failure contained literal quote characters in its "empty"
input, and literal backslash sequences where control characters were intended.
The new `text_protocol.py` format requests explicit codepoint envelopes for test
strings. Only those explicit objects are decoded; raw legacy strings are literal.
Native reviewer schemas enforce the new representation.

```bash
sudo -v
env AM_ASCII_TESTS=1 python -m unittest discover -s tests -p test_ascii_protocol.py -v
```

The real matrix round-trips every supported ASCII byte through Java/C++/C and
checks the uploaded reference/starter behavior on the full Java ASCII range.
The uploaded raw diagnostic is not committed or used as a question bank. These
checks validate transport and the regression; a new desktop model generation is
still needed to measure how often it produces acceptable fresh exercises.
