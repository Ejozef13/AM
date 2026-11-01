# How AM generates, verifies, and grades practice

Every practice session is generated from the student's chosen language, topic,
and optional notes. There is no question bank, default exercise, or template
fallback. Fixed test fixtures are not accessible through the application.

## Preparation: before the student sees a question

| Stage | What happens | What can reject it |
| --- | --- | --- |
| Input | Validate language/runtime, difficulty, session length, topic, notes size | Missing input, unavailable compiler, invalid limits |
| Context | Extract PDF text if uploaded; retrieve relevant passages from long notes | Invalid/scanned PDF, size bounds, no matching long-note passages |
| Web context (optional) | Fetch bounded Wikipedia excerpts using only the topic; keep them separate from notes | Network failure, no usable articles, response size/shape limits |
| Author | Local model writes task, constraints, starter bug, correct reference, hints, tests, and evidence ID | Incomplete or malformed response |
| Structure | Parse JSON/code syntax; validate fields, types, signature, arguments, source bounds, and notes origin | Broken interface, invalid native types, invented excerpt ID |
| Blind review | Separate model call sees task, notes, starter, and hints; derives another solution and cases | Ambiguous/irrelevant task, incorrect hints, invalid code/tests |
| Reference execution | Both solutions run against the combined author and reviewer cases | Wrong returns, mutations, compile/runtime errors, limits |
| Starter execution | Check every combined case; require at least one wrong answer or prohibited mutation | Starter passes everything, crashes, or exceeds execution limits |
| Publish | Save accepted session and send task, starter, constraints, skills, and interface to browser | Unresolved preparation failure means no session |

By default, author and reviewer are separate calls to the same installed
`am-study:latest` model, configured from `gpt-oss:20b`. A distinct installed
reviewer can be selected with `--review-model`. A second call is not automatically
a second independent source of truth. The reviewer does not see the author's
reference solution or test cases before deriving its own.

Each new author/reviewer request asks for 3–5 small cases. Combined cases include
both sets. Identical previously passed source/input/expected combinations can
be reused within preparation; a changed expectation must be checked again.

## Bounded repairs

- At most two author drafts per exercise, with fresh random request seeds logged
  in response diagnostics. Seeds encourage variation; they do not guarantee unique tasks.
- Malformed native test shapes or out-of-range values get one model-only repair
  using the exact signature schema. Only tests can change; source/task/signature
  are preserved. All ordinary checks and reference execution still apply.
- An invalid starter gets up to two model-only repair attempts for starter code
  and hints. A candidate must pass safety checks, still fail a test, and receive
  a fresh blind review of its bug and hints. A fully correct candidate is rejected
  as a starter and that feedback reaches the next attempt. No host-written bug
  or exercise is inserted. Infrastructure errors abort rather than trigger repair.
- At most two reviewer attempts for an otherwise unchanged draft.
- If both references agree with each other but disagree with a reviewer expected
  value, one bounded correction request checks that inconsistency against the
  specification. Agreement alone does not authorize the correction.
- Corrections can replace only the flagged reviewer expected values, not remove
  tests, change inputs, or rewrite the task. The corrected cases run again.
- Starter repair receives the failing input and runtime evidence, while keeping
  the task and valid domain. It still must expose a wrong answer safely.
- Infrastructure failures abort preparation; they do not become student failures.
- A failed later exercise never publishes a partially prepared session.

## What the student receives

The initial response excludes reference solutions, full test data/answer keys,
and unrevealed hints. The editor shows the generated starter. Each hint is
requested separately. Test inputs, expected/actual returns, printed output, and
compiler/runtime errors become visible as learning evidence after a test run.
This is a study app, not an interview platform with permanently hidden tests.

## Grading: after the student presses Run tests

1. Validate session ID/current exercise and submission size.
2. Send source and one input case to a fresh restricted container.
3. Compile Java/C/C++ inside the container; Python executes inside its container.
4. Call the required function and capture return value, input state, and output.
5. Compare actual and expected JSON values on the host. Boolean/integer and
   floating-point distinctions are preserved by the comparison rules.
6. Mark a case passed only when its return matches and its input-mutation rule
   holds. Errors and time/output limits remain visible test outcomes.
7. Publish the completed result, persist the attempt, and update actual activity
   and review scheduling. An infrastructure interruption produces no overall grade.

AI does not decide whether a student's submission passed. Expected answers stay
on the host and are not embedded in the container's execution wrapper. Drafts
and progress are stored separately from grading evidence.

## Execution boundary

The runners use pinned images, unprivileged users, dropped capabilities, no
external network, read-only root filesystems, temporary workspaces, no project
mounts, and bounded memory/process/output/time resources. C/C++ also use
sanitizers. Native array/node/graph wrappers are built by trusted code; they do
not contain expected answers. See [native limits](multilanguage-practice.md) and
[structured inputs](structured-inputs.md).

Tests and model agreement reduce mistakes but do not prove correctness for all
inputs. Both model calls may share a misconception, and generated tests may
miss cases. Treat the observed evidence as the scope of the result.

## Source locations

| Responsibility | File |
| --- | --- |
| Author/review/repair orchestration | `ai_exercises.py` |
| Student input and note retrieval | `study_input.py`, `note_retrieval.py`, `web_retrieval.py` |
| Source/JSON checks | `lesson_validation.py`, `language_contracts.py` |
| Python/container transport and host comparison | `code_runner.py` |
| Native compile/run and marshaling | `compiled_runner.py`, `compiled_driver.py`, `native_harness.py`, `native_structures.py` |
| HTTP/session/public-field boundaries | `practice_web.py`, `practice_sessions.py` |
| Saved drafts, activity, goals, review schedule | `progress_store.py` |

See [validation and demo](validation.md) for measured checks and the repeatable
live-model benchmark. No live generation accuracy percentage is inferred from
unit tests or the controlled browser demo.

## Teaching voice and diagnostics

Application system prompts apply AM's sarcastic, theatrical tutor voice to
student-facing explanations and hints, including repair calls. Accuracy and
validation rules take priority; code, expected values, schemas, and comparisons
remain free of personality. Review feedback must still obey its existing bounds.

A preparation rejection creates no session. Its reason and recovery guidance
are returned to the browser and logged in the launch terminal. `--diagnostics`
additionally captures bounded artifacts locally; it is opt-in because drafts
can contain private note context. See [first-exercise troubleshooting](../README.md#if-the-first-exercise-fails).
The execution restrictions do not guarantee perfect security or full isolation.
