# Python, Java, C, and C++ runtime setup

Every language uses the same AI generation, blind review, reference execution,
and starter verification pipeline. See [verification](verification.md).

## One-time compiler setup

Keep the existing Ollama and Open WebUI installation. From the repository:

```bash
sudo systemctl start docker
sudo -v
python tools/setup_compiled_runtime.py
python am.py on --diagnostics
```

Setup builds a local image containing Java 21, C17, and C++17 compilers, then
actually compiles and runs a probe for each language. Only after all probes pass
does it save an immutable image ID in Git-ignored `.am-runtime/compiled-image.txt`.
Restart AM after changing that runtime setup. Ordinary source/UI updates do not
require a compiler image rebuild.

Python uses the pinned image in `infrastructure/python-runner-image.txt`.
`tools/check_runner_runtime.py --pin` verifies its configuration. Python stays
available if the compiled runtime is missing; the other language buttons explain
that setup is needed.

Existing direct Docker users can pass `--docker-direct` during setup. Optional
`--build-network host` affects dependency downloads only; student containers still
have no network. `--ca-bundle PATH` selects the BuildKit-specific Dockerfile and
uses a build secret. Without it, the standard Dockerfile works with the legacy
builder too. If a build finishes but its probes were interrupted, authorize once
and run `python tools/setup_compiled_runtime.py --use-existing-image`.

## Runtime interfaces and limits

| Area | Contract |
| --- | --- |
| Python | Synchronous function, up to five positional inputs, JSON-compatible return |
| Java | `public class Solution`, public static `solve`, no package or `main` |
| C/C++ | Free `solve` function without `main`; standard includes allowed |
| Base native values | int32, int64, finite double, boolean, bounded ASCII string, int array |
| String characters | Java/C++ ASCII 0–127, C ASCII 1–127; up to 1000 characters |
| Structured inputs | Bounded linked list, heap-indexed tree, adjacency graph; [details](structured-inputs.md) |
| C arrays | One logical JSON input expands to pointer and length supplied by runner |
| Returns | Native scalar types; Java/C++ can also return integer arrays; native node outputs are not supported |
| Source | At most 16,000 UTF-8 bytes |
| Compilation | 30-second wall limit, 8-second CPU limit |
| Student native execution | 3-second wall limit, 2-second CPU limit |
| Outer native execution | 60 seconds after container creation; creation has a separate allowance of at least 60 seconds |
| Container | 512 MB memory, 64 processes, 64 MB temporary workspace for compilation |

Generated test strings use explicit character-code envelopes, decoded to actual
strings before grading. C++ string inputs include their length to preserve NUL;
Java uses safe octal literals. See [verification](verification.md).

The host builds wrappers from validated types and input values. Author, reviewer,
and student code all execute inside restricted containers. Expected results stay
outside those containers. Full 64-bit integer and floating-point evidence is
formatted on the server before display, avoiding browser-number precision loss.

## All-day access and recovery

Managed `am.py on` refreshes an existing sudo credential while running. Existing
direct Docker access is preferred. See [Docker access](docker-access.md) for
password renewal after sleep, shutdown, and the limits of administrator policy.
Authorization/infrastructure errors do not become student grades. Sessions and
autosaved drafts survive restart in local SQLite.

## Optional real-runtime checks

```bash
sudo -v
env AM_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_code_runner.py -v
env AM_COMPILED_TESTS=1 python -m unittest discover -s tests -p test_compiled_runner.py -v
env AM_STRUCTURE_TESTS=1 python -m unittest discover -s tests -p test_structures.py -v
```

Set `AM_DOCKER_DIRECT=1` only for an already authorized direct Docker setup.
These standalone checks use their own launch terminal; they do not inherit the
website's managed lifecycle. Runtime checks and measured records are documented
in [validation](validation.md). The local execution boundary is not a public
hostile-code hosting service.
