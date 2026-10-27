# Python exercise runner

## Architecture

Student source and test inputs enter a restricted Docker container.
Expected answers stay on the host, where actual results are compared.
No AI participates in grading.

Each test uses a fresh container.

## Runtime restrictions

- Pinned Python image
- No network access beyond container loopback
- No project-directory mounts
- Unprivileged user
- Read-only root filesystem
- Temporary writable workspace
- Dropped Linux capabilities and no new privileges
- Memory, CPU, process, wall-time, and output limits

This is a local prototype, not a public hostile-code execution service.

## Run an exercise

From the project root:

```bash
sudo -v
python run_submission.py exercises/python/largest_value.json submissions/largest_value_buggy.py
python run_submission.py exercises/python/largest_value.json submissions/largest_value_fixed.py
```

Expected results: buggy solution 6/8; fixed solution 8/8.

Exit codes:
- 0: all reviewed cases passed
- 1: one or more cases did not pass
- 2: infrastructure or configuration failure
- 130: interrupted

Passing reviewed cases is not proof of correctness for every input.

## Authoring checks

```bash
python tools/validate_lesson.py exercises/python/largest_value.json
```

The --check-trusted-code option executes author code directly on the host.
Never use that authoring option for student submissions.

## Regression tests

```bash
sudo -v
env AM_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_code_runner.py -v
```

Verified on the desktop:
- All 13 tests passed.
- Correct and incorrect results were distinguished.
- Input mutation was detected.
- Syntax errors, runtime errors, excessive output, and timeouts were handled.
- No am-case- containers remained afterward.

Default test discovery skips Docker integration tests unless explicitly enabled.
