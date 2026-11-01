# AM · Coding practice

AM is an AI-powered coding practice app inspired by Duolingo, built for computer
science students. Turn pasted class notes or articles, or uploaded text files,
into short debugging sessions in a built-in browser editor. Choose **Python, Java, C, or C++**,
fix a generated program, reveal hints, run tests, and review your session.
AM runs locally with Ollama and grades code using restricted Docker execution.
Progressive hints, saved sessions, daily goals, and streaks support regular practice.
AM's character draws on Harlan Ellison's *I Have No Mouth, and I Must Scream*:
theatrical, sarcastic, and quietly invested in your progress. The sarcasm targets
bugs and humanity's habits, never a student's intelligence or circumstances.

![Editor and saved practice](docs/screenshots/exercise.png)

Existing controlled browser demo using regression fixtures, not live inference.
Production sessions always use AI generation.

## Quick start

From the repository, with the existing model and runner images installed:

```bash
python am.py on --diagnostics
```

Open **http://127.0.0.1:8090**. Keep the terminal open. Start with one exercise.
Press **Ctrl+C** to stop, or use another terminal:

```bash
python am.py off
python am.py status
```

The launch terminal remains open while you study. Managed startup maintains
Docker authorization during normal use; [renewal after sleep](docs/docker-access.md)
happens there without restarting the app.

Stopping cancels active work, cleans up containers, and unloads the selected
models. Shared Ollama and Docker services remain available. Practice sessions
and editor drafts are saved locally in SQLite. Wait for the draft-save status
before closing. Resume unfinished sessions from the dashboard after restarting.
Stop any older `practice_web.py` launch before switching to the managed commands.

## Setup

Requirements: **Linux, Python 3.10+, Ollama, and Docker**. Application code uses
Python's standard library. The default model is `am-study:latest`, configured
from `gpt-oss:20b` with a 32,768-token context in
[`infrastructure/Modelfile`](infrastructure/Modelfile). Startup reports installed
model metadata. No models are downloaded automatically.

Start Ollama and obtain the default base model, then create the alias:

```bash
python am.py model-on
ollama pull gpt-oss:20b
ollama create am-study -f infrastructure/Modelfile
```

For first-time runner setup:

```bash
sudo systemctl start docker
sudo -v
docker_image=$(cat infrastructure/python-runner-image.txt)
sudo docker pull "$docker_image"
python tools/check_runner_runtime.py
python tools/setup_compiled_runtime.py
```

The pin is already tracked; do not use `--pin` to overwrite it.
The Python image listed in `infrastructure/python-runner-image.txt` must be
available locally. See [runtime setup](docs/multilanguage-practice.md) for compiler
options and limits. Existing installations do not need a rebuild for frontend edits.

## Saved learning and notes

The dashboard shows saved sessions, a daily goal, real completion history/streaks,
learning-path topics, and due reviews. The editor has local syntax highlighting,
line numbers, indentation, and autosave. Export/delete controls manage the local
study profile in Git-ignored `.am-data/`.

Text/Markdown/code notes and text-based PDFs are accepted. Install Poppler for PDF
extraction (`sudo apt install poppler-utils`, or `sudo pacman -S poppler` on Arch).
Long notes use local passage retrieval and visible source references. No cloud
API, vector service, or additional AI model is required.

Articles must be pasted or uploaded as supported files; AM does not fetch URLs.

## AI model

The default **base model** is `gpt-oss:20b`. The website actually requests the
Ollama **alias** `am-study:latest`. `ollama create am-study -f infrastructure/Modelfile`
creates that alias from the base with `PARAMETER num_ctx 32768`. This configures
an existing model; AM does not train or fine-tune it. The Modelfile contains no
persona prompt. Application system prompts supply the teaching personality.

`am_core.py` defines defaults. `am.py on --model` selects the author model;
`--review-model` selects the reviewer and defaults to the author model. Author
repair uses the author; review repair and expected-value correction use the
reviewer. The default is separate calls to the same model, not independent models.
`ai_exercises.py` requests 32,768 context tokens, at most 8,000 output tokens,
temperature 0.2, and `think: low`; startup in `site_control.py` also requests
32,768 context tokens. These runtime context settings override model defaults.
The browser's AI model settings show configured names and label unverified base
identity unknown. Terminal startup reports actual installed family and parameter
metadata; family alone does not verify a base model's name.

Optional terminal chat defaults to `gpt-oss:20b`, separately from practice, with
8,192 context tokens and 1,500 output tokens. Open WebUI selects its own model.

## Using another model

Install your chosen Ollama-compatible model first. `YOUR_MODEL_NAME` is a
placeholder for its exact installed tag, as listed by `ollama list`:

```bash
ollama list
ollama show YOUR_MODEL_NAME
python am.py on --model YOUR_MODEL_NAME --diagnostics
```

To use a distinct installed reviewer, add `--review-model YOUR_REVIEW_MODEL_NAME`.
Otherwise generation, review, and their repairs all use `YOUR_MODEL_NAME`.
For optional chat, select it separately:

```bash
python chat.py --model YOUR_MODEL_NAME --context 8192 --output 1500
```

Alternative models must support Ollama's structured JSON schema output, the
current `think: low` request, AM's language contracts, and the configured context
and execution limits. Practice currently requests 32,768 tokens; use a model and
hardware capable of that setting. To change practice context/output/temperature,
edit the runtime options in `ai_exercises.py` and keep startup context in
`site_control.py` consistent; changing only the Modelfile does not override them.
No separate repair model setting is needed. Larger parameter counts alone do not
guarantee better results. Hardware and model choice affect latency, memory,
exercise quality, and rejection rates; results will differ.

## If the first exercise fails

A responding website and a loaded model do not establish that a generated
exercise passed preparation. The screenshot's “could not verify a fresh exercise”
message describes a preparation failure, not its specific cause. Expand any
Preparation details and reproduce with:

```bash
python am.py on --diagnostics
```

Stop an existing managed launch with Ctrl+C first. Start with one introductory
exercise and a narrow topic. The browser reports the failed check; the launch
terminal reports rejection details. Opt-in `.am-diagnostics/last-generation.json`
contains bounded rejected drafts/reviews and can include private note excerpts;
inspect it before sharing. Do not bypass validation to force a session through.

- Missing model: check `ollama list` and `ollama show am-study:latest`; obtain the
  base and create the alias with the setup commands above, or select an installed tag.
- Ollama unavailable: `python am.py model-on`, then `python am.py model-status`.
  `AM_OLLAMA_URL` accepts only local HTTP addresses (default port 11434).
- Malformed/incomplete JSON or rejected code/tests: inspect the exact rejection
  and token-limit metadata in diagnostics. Repairs are bounded; incompatible
  structured output or language contracts can require another model or a prompt fix.
- Slow/failed generation: preparation includes several model calls and Docker
  runs. Check `ollama ps`, avoid simultaneous WebUI inference, try one exercise,
  and inspect timeout/output-limit evidence. There is no guaranteed latency.
- Runner unavailable: run `sudo -v`, `python tools/check_runner_runtime.py`, and
  `python tools/setup_compiled_runtime.py --use-existing-image` if the compiled
  image is installed. See the runtime guide for first-time builds and access renewal.

Saved notes, drafts, and settings survive preparation rejection. No fixed question
fallback is served.

## Customize the app

| Change | Edit |
| --- | --- |
| Colors, fonts, spacing, mobile layout | [`web/app.css`](web/app.css) |
| Page headings, labels, buttons, structure | [`web/index.html`](web/index.html) |
| Dynamic session text, hints UI, results | [`web/app.js`](web/app.js) |
| Highlighting and editor behavior | [`web/editor.js`](web/editor.js) |
| Dashboard, paths, goals, review UI | [`web/study.js`](web/study.js) |
| Learning-path topic lists | [`learning_paths.py`](learning_paths.py) |
| AI instructions, review, repair | [`ai_exercises.py`](ai_exercises.py) |
| Supported function types | [`language_contracts.py`](language_contracts.py) |

Frontend changes need a browser refresh. Backend changes need an app restart.
The [project map](docs/project-map.md) explains every module and the request flow.

## How it works

The local model drafts a question, buggy starter, reference, hints, and tests.
A separate blind review derives another solution and test set. Both references
must pass the combined cases, and the starter must show a wrong answer without
crashing on the checked inputs. Student grading uses execution and comparisons;
AI does not decide whether a submission passed. The browser editor is an input
tool; execution and deterministic comparisons perform grading.

New requests ask for 3–5 small cases per call and use typed native contracts.
Failed drafts receive bounded repairs. Model agreement and passing tests are
useful evidence, not proof of correctness. Docker restrictions reduce risk;
they do not guarantee perfect security or a fully isolated sandbox. No web search or embedding service is enabled. Long notes use bounded local
lexical retrieval before generation.
Bounded linked-list, tree, and graph inputs are supported across all four
languages; see the structured-input guide for calling conventions and limits.

Every practice session is AI-generated. There is no bundled question bank,
prewritten exercise generator, or offline/template fallback. Run tests and hints
only within a generated session. Fixed examples in `tests/` simulate model and
runner responses for regression checks; the app never serves them as questions.

`am.py chat` is optional terminal chat. Open WebUI remains independent of the
practice website.

## Guides

- [Docker authorization and all-day practice](docs/docker-access.md)
- [Desktop start/stop commands and independent Open WebUI](docs/desktop-commands.md)
- [Project map and editing guide](docs/project-map.md)
- [Saved learning and privacy](docs/saved-learning.md)
- [Structured inputs](docs/structured-inputs.md)
- [PDF notes and retrieval](docs/notes-and-retrieval.md)
- [Validation, demo, and live benchmark](docs/validation.md)
- [Release status and roadmap](docs/roadmap.md)
- [Generation, review, and accuracy limitations](docs/verification.md)
- [Java/C/C++ setup](docs/multilanguage-practice.md)
- [Open WebUI configuration](docs/open-webui.md)

## Development checks

```bash
python -m unittest discover -s tests -v
node --check web/app.js
node --check web/editor.js
node --check web/study.js
```

Default tests use controlled model/service fixtures. Optional real Docker checks
are documented in the runtime guides. Keep tests and validation tools with the
source: they protect the execution boundary and generation contracts.

Diagnostics save rejected drafts to Git-ignored `.am-diagnostics/`; inspect them
before sharing. Runtime pins and locks stay in `.am-runtime/`. Existing private
configuration, model storage, archived local files, and Open WebUI data are not
removed by repository cleanup.
