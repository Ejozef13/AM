# Python, Java, C, and C++ practice

The same notes-to-practice pipeline now supports all four languages. AM writes a
question, buggy starter, reference solution, hints, and test data. A separate
review call derives another solution and additional tests without seeing the
author's reference or cases. Both solutions must pass the combined cases; the
starter must demonstrate a logic or mutation failure. Student submissions use
the same execution boundary and host-side comparisons.

## One-time compiler setup

Keep the existing Ollama and Open WebUI installation. From the repository:

```bash
sudo systemctl start docker
sudo -v
python tools/setup_compiled_runtime.py
python am.py on
python practice_web.py --diagnostics
```

Open `http://127.0.0.1:8090`. Setup downloads compiler dependencies into a local
Docker image and runs an actual compilation/execution probe for each language.
Only after all three pass does it save the immutable image ID in
`.am-runtime/compiled-image.txt`. This machine-specific directory is Git-ignored.
Restart the app after setup. Python remains available if compiler setup fails;
the other buttons explain that setup is needed. Refresh the page after restarting.
If sudo credentials expire during a long build, run `sudo -v` and then
`python tools/setup_compiled_runtime.py --use-existing-image` to probe the built image.

If Docker's sudo authorization expires while studying, keep the browser page
open. In the same terminal running the website, press Ctrl+Z to suspend it,
run `sudo -v`, then run `fg` to resume it. Click Run tests again. This retains
the in-memory exercise and editor contents; restarting the server loses the
session. Another terminal may have a different sudo timestamp and does not
reliably refresh the launch terminal's authorization.

Authorization failures have a specific response code. Other runner failures
show their framework-provided cause instead of assuming sudo expired. With
`--diagnostics`, execution failures also print an `AM execution diagnostic:`
line containing the operation, exception type, and bounded detail; submissions,
test arguments, answer keys, and notes are not included in that diagnostic.
Failed infrastructure requests do not record a student attempt or an overall grade.

Java uses JDK 21, C uses C17, and C++ uses C++17. No extra Python packages are
required. Compilation happens inside the container, including model-authored
reference code. No uploaded code is executed on the host.

For an already-authorized direct Docker installation, setup and the website
accept `--docker-direct`. Advanced setup options include `--use-existing-image`,
`--build-network host`, and `--ca-bundle PATH` for restricted dependency-download
environments. Normal setup supports the legacy Docker builder and BuildKit.
Only `--ca-bundle` selects the separate `Dockerfile.buildkit` and requires
BuildKit secret support. The CA bundle is a build secret, not a student-container mount.
Build networking does not enable networking during student execution.

## Calling contracts

The question page shows the required interface. Students edit the function or
class, without writing a console input/output wrapper:

| Language | Required shape |
| --- | --- |
| Python | A synchronous function with up to five positional arguments |
| Java | `public class Solution` containing `public static ... solve(...)`; no package or `main` |
| C | A free `solve` function; arrays use `const int *argN, int argN_len`; no `main` |
| C++ | A free `solve` function; strings and arrays use const references; no `main` |

Compiled exercise signatures declare zero to five parameters and one return
type: `int`, `long`, `double`, `bool`, `string`, or `int_array`. Here `int` is
signed 32-bit; `long` is signed 64-bit (`long long` in C/C++). Doubles must be
finite and comparisons use exact JSON representation; approximate numerical
grading and exercises requiring signed-zero distinctions are not included.
Strings use printable ASCII plus newline, carriage return, and tab, up to 1,000
characters. Integer arrays contain at most 100 signed 32-bit integers. Java and
C++ can return integer arrays; C array returns are not supported yet. Tasks must
specify any narrower bounds and edge behavior. These are function exercises,
not support for every language feature or multi-file application.

The trusted harness is constructed from validated types and escaped inputs;
expected answers stay on the host. It calls the function and serializes the
return and argument snapshots. Grading checks return types/values and forbidden
input mutation. Results show the actual input arguments for every case, including
compiler errors. Server-formatted JSON preserves full 64-bit integers and
distinguishes `1.0` from `1` in the browser's evidence display.
Submission source remains limited to 16,000 UTF-8 bytes. The container request
limit is 32 KB for Python and 128 KB for compiled languages, accommodating escaped
typed literals without increasing source or input-value bounds.

`run_submission.py LESSON.json SOURCE --docker-direct` also supports these typed
compiled lessons after setup. Omit the flag when using the default sudo Docker
access. Existing Python lesson files still work. `--templates` and `--offline`
remain explicit Python-only modes; AI failures never silently select a template.

## Execution limits

Each case gets a fresh container with no network, no host-directory mounts,
read-only root, unprivileged UID/GID, dropped Linux capabilities, and disabled
privilege escalation. Python keeps its existing 128 MB memory limit and 16 MB
non-executable temporary filesystem. Compiler containers use 512 MB, 64 process
slots, and a 64 MB executable temporary filesystem for native binaries.

Compilation has a 30-second wall limit and 8-second CPU limit. The compiled
student program has a 3-second wall limit and 2-second CPU limit. The surrounding
container request has a 60-second wall limit to allow Docker startup overhead;
cleanup removes the uniquely named
container and retries a bounded daemon-removal failure. C/C++ builds enable
AddressSanitizer and UndefinedBehaviorSanitizer. Output and compiler diagnostics
are bounded. Compiler errors, runtime errors, timeouts, and output limits appear
as distinct result statuses. This remains a local prototype rather than a
public service for hostile submissions.

Requests contain one newline-delimited JSON record, so drivers do not have to
wait for Docker to forward stdin EOF. An integration regression deliberately
leaves stdin open. An outer compiled-runner deadline is an infrastructure error
and produces no student grade; the inner program deadline remains a distinct
student time-limit result. Slow Docker storage drivers can require additional
startup allowance in test environments without changing program limits.

## Verification and accuracy

The compiler integration suite covers correct and incorrect returns, compilation
failures, runtime errors, infinite loops, output limits, input mutation, escaped
strings, scalar types, full 64-bit boundaries, Java/C++ array returns, and denied
root-filesystem writes. Run it explicitly after compiler setup:

```bash
python -m unittest discover -s tests -v
sudo -v
env AM_COMPILED_TESTS=1 python -m unittest discover -s tests -p test_compiled_runner.py -v
env AM_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_code_runner.py -v
```

Set `AM_DOCKER_DIRECT=1` in those test commands only when using direct Docker.
The default suite tests generation contracts, blind-review inputs, language
routing, HTTP sessions, evidence, and grading with controlled fixtures. Browser
checks can combine simulated model responses with real compilers; that verifies
the application workflow, not live Ollama generation quality.

Validation on 2026-10-27: the default suite ran 125 tests (103 passed, 22 optional
container tests skipped). The separate Python runner suite passed all 14 tests.
The eight-method compiler matrix passed across Java, C, and C++, followed by
focused successful runs for full 64-bit boundaries, the open-stdin regression,
and a valid escaped native request larger than Python's 32 KB allowance.
All three compiled-language browser workflows passed with simulated author and
review replies and real compiler execution: preparation, intended starter failures
(4/6 passing), hint reveal, corrected submissions (6/6), and completion summaries.
There were no JavaScript errors; desktop and 390-pixel mobile layouts were inspected.
The cloud Docker daemon uses `vfs`, which copies the image for every container;
browser verification here uses a 180-second outer startup allowance. Compilation
and student execution retain the same 30-second and 3-second limits. The normal
app default remains 60 seconds for the outer request. An exceeded outer deadline
is an infrastructure error, not an incorrect student answer. Live local Ollama
generation was unavailable in this cloud environment.

Compatibility follow-up: the default suite ran 131 tests (109 passed, 22 optional
container tests skipped), including setup publication failures and browser
disconnects during response headers/body. Normal setup no longer requires
BuildKit; the custom-CA path selects its own Dockerfile. A real build with
`DOCKER_BUILDKIT=0` completed dependency installation, and the resulting image
passed restricted Java, C, and C++ compiler/execution probes. For this cloud
network test only, the base image received the cloud's public CA bundle and
proxy settings; certificate verification stayed enabled. The shipped default
Dockerfile continues to use the pinned upstream Python base. Browser peer
disconnects now close the response without an expected broken-pipe traceback.

Runner-recovery follow-up: the default suite ran 135 tests (113 passed,
22 optional container tests skipped). A trusted fake-sudo process verifies
that a password-required exit status of 1 is an infrastructure error, including
cleanup. The Java HTTP recovery test preserves the same exercise, records no
failed infrastructure attempt, and grades a retry without another model call.
Execution-diagnostic tests verify that the cause is logged without submission
contents. A separate real Java check rejected the all-negative starter result
and accepted the corrected maximum-finding function. These checks do not
identify the cause of a particular desktop failure without its runtime diagnostic.

Two model calls can share mistakes, particularly when using the same model.
Passing the combined suite does not prove the question matches its notes or
cover all valid inputs. Targeted expected-value repairs retain the existing
explicit reviewer approval and renewed execution checks; agreement alone is
insufficient. Notes still go directly to local Ollama. There is no web search,
RAG, automatic source verification, or new model installation in this change.
Use `--diagnostics` to retain rejected drafts locally for investigation; inspect
them before sharing. Notes and student progress otherwise remain in memory.
