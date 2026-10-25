# Open WebUI deployment

Open WebUI runs through Docker Compose and connects to the host's
Ollama service at http://127.0.0.1:11434.

The UI listens at http://127.0.0.1:8080.
Authentication is enabled; additional signups are disabled in admin settings.

## Start

From the project root:

```bash
sudo systemctl start docker
python am.py on
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml up -d
```

Initial startup can take time. Verify readiness:

```bash
curl --fail --show-error --max-time 10 http://127.0.0.1:8080/health
```

## Stop AM's UI and unload its model

Finish active requests first:

```bash
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml stop
python am.py off
```

This preserves application data and leaves Docker and Ollama running.
It does not stop unrelated services.

## Status

```bash
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml ps
python am.py status
```

## Storage and configuration

The named volume am_open_webui_data stores accounts, settings, and chats.
Do not use docker compose down -v unless intentionally deleting that data.

infrastructure/.env.openwebui contains the pinned image digest and a private
session-signing secret. Keep it outside Git and include it in secure backups.

The Compose file uses Linux host networking so the container can reach
Ollama's loopback listener. Open WebUI itself binds to loopback.

A fresh deployment requires creating the private environment file and
reviewing the signup setting again. Database-persisted admin settings
are not fully described by the Compose file.

## Verified

- Local health endpoint responds.
- UI listener is restricted to 127.0.0.1:8080.
- Authenticated chat with gpt-oss:20b works.
- Follow-up questions and conversation history work.
- Account, conversations, and disabled signups survive container recreation.

## Remaining work

- Secure data-backup procedure
- Web search and source validation
- Document RAG and retrieval evaluation
- Private remote access
