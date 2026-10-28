# Desktop commands

## Get the update

Stop an older website with Ctrl+C in its launch terminal first. Then:

```bash
cd ~/Projects/AM
git switch codex/multilanguage-practice
git pull --ff-only
```

Compiler setup already passed on your desktop; this update needs no rebuild.

## AM practice website

```bash
cd ~/Projects/AM
python am.py on --diagnostics
```

Keep this terminal open. Visit http://127.0.0.1:8090. Choose a language, add a
topic and notes, and start with one exercise. The default model is
`am-study:latest`, configured from `gpt-oss:20b` in `infrastructure/Modelfile`.
Startup reports the actual installed model metadata.

Stop with Ctrl+C in that terminal, or in a second terminal:

```bash
cd ~/Projects/AM
python am.py off
```

Status:

```bash
python am.py status
```

Wait for the draft-save status before closing. Saved sessions and progress
survive stop/start. Stopping unloads the selected practice models and leaves the shared Ollama and Docker services running.

## Open WebUI chat, independently

The practice website does not need to be running:

```bash
cd ~/Projects/AM
sudo systemctl start docker
python am.py model-on
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml up -d open-webui
```

Visit http://127.0.0.1:8080, log in, and select `gpt-oss:20b` (or `am-study:latest`)
from the model picker. Selecting a model and sending a message loads it.
This uses the existing private environment file and existing chat storage.

Stop only WebUI, preserving chats and settings:

```bash
cd ~/Projects/AM
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml stop open-webui
```

After finishing all requests using a model, optionally unload it:

```bash
python am.py model-off --model gpt-oss:20b
python am.py model-off --model am-study:latest
```

Inspect installed and currently loaded models:

```bash
ollama list
ollama ps
ollama show am-study:latest
```

The two websites share Ollama. For smooth performance, finish one generation
before starting another. Unloading a shared model affects both clients' memory
use; a later message can load it again. Neither stop command deletes models.

## PDF notes and saved progress

Install Poppler once for PDF uploads: `sudo apt install poppler-utils`, or
`sudo pacman -S poppler` on Arch. Notes retrieval is local. Saved drafts, sessions,
and goals live in `.am-data/progress.sqlite3`; use Resume on the dashboard after
restarting. Export/delete controls are under Local data and privacy.
