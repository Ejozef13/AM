# AI-generated practice sessions

## Student workflow

Choose Python, add a topic and optional notes, select a difficulty, and start a
session. One exercise is the default. During preparation the page shows drafting,
review, and execution stages. On success the student gets a debugging task,
requirements, an editor, progressive hints, test evidence, and a session summary.
The existing website layout, file reader, session navigation, and runner are reused.

## Generation and review

`ai_exercises.py` implements the author/reviewer boundary:

1. The author receives the student's topic, notes, difficulty, and titles already
   used in the session. It returns structured exercise data, not terminal commands.
2. Local validation bounds prose, code, JSON tests, function arity, and evidence.
   AST parsing checks syntax without executing code on the host.
3. A fresh reviewer request sees the question, starter, hints, and original notes.
   It does **not** receive the author's solution or tests. It assesses ambiguity,
   relevance, and hints, then writes its own solution and expected cases.
4. Both solutions must pass every case from both authors in Docker. All tests
   forbid input mutation. The starter must fail a case through an incorrect result
   or forbidden mutation, rather than merely crash or time out.
5. A rejected draft receives failure feedback and one regeneration attempt. A
   connection/infrastructure failure aborts immediately. No partial session is
   published if any requested exercise cannot pass preparation.

Tests are data: positional arguments and expected JSON returns. They cannot
supply host-side assertions, shell commands, checker code, or override grading.
Only `code_runner.py` determines pass/fail using host-side comparisons. Expected
answers remain outside submission globals. All model references and starter code
use exactly the same restricted execution boundary as student submissions.

The default reviewer is a separate call to the same installed model. Use
`--review-model` for another already-installed local model. This option does not
install/download models or alter Ollama/Open WebUI. The interface identifies
whether review used the same model or a distinct model. Metadata reports checks
performed, not a confidence score or a guarantee.

## Bounds and behavior

Python synchronous functions with up to five positional arguments are supported.
Inputs and return values must be JSON-compatible. Tasks use small bounded inputs,
no input mutation, external packages, files, networking, interactive input, or
nondeterministic services. Each author supplies 3–8 cases, for 6–16 combined cases.
Generation is limited to two attempts per exercise and 1–5 exercises per session.
The initial author and reviewer each have an 8,000-token output ceiling; incomplete
or malformed output is rejected. These are limits, not typical answer lengths.

Preparation is deliberately sequential and can take several minutes on local
hardware. The app allows one active job. Stage polling contains no notes, code,
or answer keys. Session responses omit solutions, expected tests, unrevealed
hints, and reviewer feedback. Test results disclose expected/actual returns after
submission as learning evidence, not hidden interview tests.

Notes limits and in-memory retention match the previous milestone: UTF-8 text,
Markdown, and code files; 48 KB per file, 12,000 combined characters; ephemeral
sessions in RAM. The app saves no notes or progress to disk. No web search, RAG,
PDF parsing, or online source verification is implemented. All supplied notes go
to the local model directly. Exact quotes confirm origin, not interpretation.

`--templates` retains the reviewed-family mode with AM focus selection.
`--offline` uses explicit keyword matching and reviewed templates without any
model calls. Neither is an automatic fallback after AI-generation failure.

## Accuracy and limits

Separate review and execution provide complementary checks. They do not establish
universal correctness. Author and reviewer may share the same misconception;
requirements or hints can be wrong despite passing cases; finite cases can miss
bugs; notes may be incorrect; difficulty is a model judgment. A distinct model
also does not guarantee an independent or correct judgment. This milestone does
not verify asymptotic complexity, pedagogical quality, or full syllabus coverage.

Generated code is untrusted. The existing restricted Docker runner reduces local
execution exposure; it is not a production multi-tenant hostile-code sandbox.
Do not expose the loopback server as a public service.

## Validation

Run `python -m unittest discover -s tests -v`. Tests cover blind-review payloads,
configurable reviewer identity, inconsistent solutions/test answers, malformed or
incomplete output, quote provenance, bounded retries, infrastructure failures,
inert starter bugs, and atomic session publication. HTTP tests cover generated
sessions, public metadata, hints, grading, and summaries. Fixture runners do not
execute arbitrary source on the host.

Live model quality must be checked on the desktop running Ollama. Simulated model
responses establish the application contract, not the quality of AM's real output.

Validation record: the default suite ran 69 tests, with 57 passing and 12 optional
Docker integration tests skipped. The 11 generation-specific tests also passed
after the final feedback-message change. A separate Chromium workflow used
simulated author/reviewer responses with the real Docker runner: both factorial
solutions passed six combined cases, the starter scored 5/6, a hint was revealed,
the repaired submission scored 6/6, and the summary recorded completion. There
were no browser JavaScript errors. One leftover container in `created` state
was manually removed after server shutdown; automatic cleanup during Docker
startup races needs follow-up. No test containers remained afterward. No live Ollama
model was available in this workspace, so live generation remains a desktop check.

The first desktop palindrome run was rejected by the signature-format check;
the original message did not identify which signature feature triggered it.
Author and reviewer instructions now explicitly forbid decorators, variadic
parameters, and required keyword-only inputs. Diagnostics identify the code's
role, signature, and unsupported feature and feed that information into the retry.
The validator accepts optional keyword-only settings because positional calls
can omit them. Required keyword-only inputs remain unsupported. Type annotations,
positional-only parameters, and positional defaults continue to work. The HTTP
error no longer repeats the failure or suggests changing valid notes for a
format error. Regression tests cover these signature forms and retry behavior.

A subsequent desktop run was rejected for its `constraints` field. The original
output schema specified an array but omitted the validator's 1–6 item limit.
Generation schema and validation now share list bounds and text limits; the
author instructions state them explicitly. Invalid lists report the actual count
or type in retry feedback. Regression checks cover 1/6-item boundaries, missing
and oversized lists, schema limits, and recovery from a seven-constraint draft.
The post-fix suite ran 77 tests: 65 passed and 12 optional Docker tests skipped.
These checks simulate model responses; the same desktop request still needs
retesting with live Ollama.
