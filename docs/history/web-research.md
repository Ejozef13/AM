# Web research

## Services

- Open WebUI: http://127.0.0.1:8080
- SearXNG JSON endpoint:
  http://127.0.0.1:8081/search?q=<query>&format=json
- Model: am-study:latest

Create the model configuration with:

    ollama create am-study -f infrastructure/Modelfile

The model reuses GPT-OSS 20B weights and defaults to 32,768 context tokens.
Verified running with 100% GPU placement.

## Open WebUI settings

- Web Search enabled in admin settings and separately in each test chat
- Engine: searxng
- Search result count: 3
- Search concurrency: 1
- Loader concurrency: 2
- SSL verification enabled
- Web loader and embedding/retrieval bypasses disabled

These UI settings are persisted in Open WebUI's database;
Compose alone does not reproduce them.

## Verified

- SearXNG returned useful JSON search results.
- Open WebUI successfully executed search_web.
- Explicit URL attachment retrieved the Python tutorial.
- The resulting answer included a source citation and correct explanation.

## Limitations

- Search queries and webpage requests leave the desktop.
- Search engines can reject requests or require CAPTCHAs.
- Earlier runs at 4K context invented unavailable tools.
- Search succeeded with the 32K model configuration, but context was
  not conclusively established as the sole cause of earlier failures.
- Automatic full-page retrieval following search remains unverified.
- Retrieved content is untrusted evidence, not permission to run actions.
- Citations require checking against the actual source.

## Lifecycle

Start Docker and Ollama, then start both Compose services:

    sudo systemctl start docker
    python am.py on
    sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml up -d

Finish active requests, stop the UI/search containers, and unload the UI model:

    sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml stop
    python am.py off --model am-study:latest

The existing default am.py off targets gpt-oss:20b, not am-study:latest.
Private environment files must remain outside Git.
