# AI-generated practice sessions

## Student workflow

Choose an available language, add a topic and optional notes, select a difficulty, and start a
session. One exercise is the default. During preparation the page shows drafting,
review, and execution stages. On success the student gets a debugging task,
requirements, an editor, progressive hints, test evidence, and a session summary.
The existing website layout, file reader, session navigation, and runner are reused.

## Generation and review

`ai_exercises.py` implements the author/reviewer boundary:

1. The author receives the student's topic, notes, difficulty, and titles already
   used in the session. It returns structured exercise data, not terminal commands.
2. Local validation bounds prose, code, JSON tests, function arity, and evidence.
   Python AST parsing checks syntax without executing code on the host. Java,
   C, and C++ use typed calling contracts and compile only inside containers.
   Notes are divided into verbatim chunks of at most 600 characters. The model
   selects an `evidence_id` from the provided list; the application inserts the
   original source text. The output schema does not request model-written quotes.
3. A fresh reviewer request sees the question, starter, hints, and original notes.
   It does **not** receive the author's solution or tests. It assesses ambiguity,
   relevance, and hints, then writes its own solution and expected cases.
4. Both solutions must pass every case from both authors in Docker. All tests
   forbid input mutation. The starter must fail a case through an incorrect result
   or forbidden mutation, rather than merely crash or time out.
5. Author failures repair the author draft (at most two author attempts).
   Reviewer format/code failures repair only the review (at most two reviewer
   attempts per draft). Reviewer content never becomes an author-owned test just
   because the review failed. Connection/infrastructure failures abort immediately.
6. When both solutions produce the same return on a reviewer case but disagree
   with its expected value, a short correction request asks the reviewer to
   recheck the specification. It can approve expected-value replacements only for
   the flagged indices. Inputs, solutions, and case count cannot change. Every
   corrected expectation is executed again before publication. Declined, invalid,
   or still-inconsistent corrections abort the session rather than deleting cases
   or silently accepting the observed output as truth.
7. No partial session is published if any requested exercise fails preparation.

Initial review remains blind to the author's solution/tests. A correction request
contains the public task, reviewer solution, failing inputs, observed values from
both solutions, and literal character details for string inputs. Agreement alone
is not proof of specification correctness; explicit review approval and renewed
execution are required. An unresolved reviewer failure does not regenerate a
valid author draft or copy reviewer tests into it.

Within one exercise, passing source/entrypoint/input/expected combinations are
cached to avoid launching the same container test repeatedly during repair.
Changing a solution, input, or expected value requires fresh execution. Input
dictionary insertion order is preserved in cache keys. `reference_runs` describes
the final validated source/test pairs, not total container launches including
failed attempts. The UI reports expected-value repairs separately. Starter code
must still expose an actual failing case after the final review passes.

Tests are data: native JSON positional `args` arrays and `expected` return values.
For one string parameter use `args: ["level"]`; for one list use `args: [[1,2,3]]`.
The model no longer needs to serialize JSON a second time inside string fields.
Legacy `args_json`/`expected_json` fields remain readable for prior fixtures.
Tests cannot
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
Java, C, and C++ function exercises are also available after compiler setup;
their typed interfaces and limits are documented in [multilanguage practice](multilanguage-practice.md).
Inputs and return values must be JSON-compatible. Tasks use small bounded inputs,
no input mutation, external packages, files, networking, interactive input, or
nondeterministic services. New author and reviewer requests each ask for 3–5 small cases. The reader still
accepts older 3–8-case responses. Compiled reviewer schemas enforce argument
count and JSON types; C array lengths are supplied by the harness.
Generation allows at most two author drafts, two reviews per draft, and one
expected-value correction per accepted review; sessions contain 1–5 exercises.
Correction failure aborts immediately rather than triggering another full review.
Calls use low reasoning; the author and reviewer each retain an 8,000-token output ceiling; incomplete
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
to the local model directly. Excerpt IDs confirm origin, not interpretation or
relevance. The reviewer sees the full notes once, without repeated focus-plan or skill
metadata, to check whether they support the exercise. Unknown IDs are rejected rather than silently
substituting an unrelated passage. With no notes, the selected ID and quote are
empty. Short notes remain usable; there is no arbitrary eight-character minimum.

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

The next desktop rejection reported an invalid function name, but did not show
the returned name. The entrypoint schema now explicitly requests a bare Python
identifier. When both starter and reference define exactly one top-level function
with the same name, the app can derive entrypoint metadata from those ASTs. This
recovers signature-style labels without changing source. Different definitions
or ambiguous multiple definitions require repair instead of guessing. All review
and execution checks still run afterward. Retries receive the prior draft (up to
24,000 serialized characters) and failure feedback to repair its fields.

For a desktop troubleshooting run, use `python practice_web.py --diagnostics`.
Rejected attempts print the reported entrypoint, function names, list types/counts,
and rejection reason to the launch terminal. Diagnostic mode also writes generated
draft/reviewer artifacts to `.am-diagnostics/last-generation.json` for reproduction.
The folder is Git-ignored; newly created folders/files are owner-only. The file
holds up to ten rejected attempts from the most recent failed generation run,
and is overwritten on the next failed run. It includes generated code, test data,
and explanations, which may reflect private course material. It does not include
the original notes field. Inspect it before sharing and delete it when finished.
The next successful run does not clear an older failure trace; check its run ID.
Normal launches do not create this file. A failure to save diagnostics does not
replace the actual generation error. Terminal summaries exclude full artifacts.

The entrypoint update passed 70 tests, with 12 optional Docker tests skipped (82
total). Checks include metadata recovery without code changes, ambiguous and
mismatched definitions, repair context, diagnostic fields, and a complete simulated
author/reviewer workflow with a signature-style entrypoint. Live model generation
has still not been verified in this workspace.

Desktop diagnostics then identified a repeated verbatim-quotation rejection,
before the reviewer was called. The excerpt-ID design above replaces that copying
requirement. Tests verify that a model's unsolicited paraphrase cannot overwrite
the original excerpt or block an otherwise valid draft, that multiline/Unicode
notes retain their exact text, and that empty/short notes and invalid IDs behave
explicitly. These tests simulate model responses; live desktop generation is
still the remaining end-to-end check.

Further desktop diagnostics showed invalid positional arguments in one attempt
and a Python parse failure in the next. Tests now travel as native JSON values,
and argument errors report which author/test, the actual type/count, and an input
shape example. Syntax errors identify starter/author/reviewer, line, column,
Python's error message, and the offending line. Full rejected artifacts can now
be collected via diagnostic mode rather than trying to infer their contents from
generic screenshots. The workspace suite passed 80 tests with 12 opt-in Docker
tests skipped (92 total), including native test-value round trips, nested inputs,
syntax-error capture, and trace-file permissions/retention. A live desktop trace
is still needed if generation continues to fail; simulated tests do not establish
the cause of that model's actual syntax error.

## Uploaded failure reproduction and repair

The user's captured JSON supplied the concrete failure: both initial solutions
implemented literal palindrome comparison correctly. The review test named
`newline symmetry` supplied the five characters with codepoints
`[97, 92, 110, 32, 97]` and incorrectly expected `true`; both solutions returned
`false`. A later review put the prose `A man, a plan, a canal, Panama` into the
Python solution field. The prior retry path also carried the bad review test
into a new author draft. The repair boundaries above address these failures.

Minimal regression tests use those input/failure shapes without committing the
user's complete uploaded file. They check correction approval, unchanged inputs
and source, exact flagged indices, rejection of declined or incorrect corrections,
review-only syntax repair, and cache behavior. A race between sending an HTTP
response and releasing the job lock was also removed: the completed operation
now releases the lock before sending its response to the client.

A separate Chromium run replayed the **actual captured first draft and review**
using the real Docker runner, with a simulated reviewer correction approving
`false` for review case 8. The exercise retained all 15 cases and the original
source/input data. The starter scored 9/15; the repaired submission scored 15/15;
hints and the session summary worked, with no browser JavaScript errors. This
replay tests the captured failure path and actual execution, not the live model's
ability to generate the correction. Live Ollama generation remains a desktop
check. The latest automated suite contains 99 tests, with 87 passing and 12
opt-in Docker tests skipped; the capture replay separately exercised Docker.

## Optimization verification

The streamlined pipeline keeps execution and review checks. Diagnostics record
response sizes, token counts, and completion reasons without saving hidden
reasoning text. Large failed reviews are omitted from repair context.

Verification: 146 default tests (124 passed, 22 optional container tests skipped),
17 real Python runner tests, and 10 real compiled-runner tests passed. Actual
C/C++ counting probes covered repeats, empty arrays, and a deliberately faulty
answer. Managed shutdown during a real container request left no containers
behind. Local HTTP fixtures verified model cancellation and unloading while
preserving other loaded models. Live GPT-OSS generation speed and completion
rate still need testing on the desktop; this environment has no running model.

## Starter execution failures

Preparation checks the starter against every combined case, including cases after
the first wrong answer. At least one wrong answer is required; crashes, undefined
behavior detected by the runtime, and resource failures reject the draft. The
bounded author retry receives the failing case name and input, runtime message,
and instructions to preserve the task and valid input domain while making the
starter safe to execute. This improves repair evidence without guaranteeing a
model will produce an acceptable draft. Custom linked-list node types are not
supported as runner parameters; current native inputs use the documented basic
types and integer arrays.
