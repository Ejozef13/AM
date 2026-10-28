# Web references and fresh generated practice

The setup form's **Use web documentation references** option sends only the
chosen language and topic as a search query. Notes, uploaded code, PDFs, and
student submissions stay local. Uncheck it to use only notes/the local model.

## Retrieval

1. Prefer the existing local SearXNG JSON service at `127.0.0.1:8081`.
2. If unavailable, try public HTML search.
3. Fetch up to three bounded passages from the documentation source policy in
   `web_research.py` (official language documentation and selected reference sites).
4. Give the retrieved passages to the author, blind reviewer, and expectation
   verifier as untrusted reference material, separate from original note evidence.
5. Display the actual retrieved URLs/excerpts and retrieval status in the session.

Only HTTPS documentation URLs on the source policy are fetched; credentials,
nonstandard ports, private addresses, and redirects outside that policy are
rejected. Responses, fetch durations, and total research time are bounded.
Search never executes web code. Student execution containers still have no
external network or host-directory access.

Source retrieval supplies context; it does not establish answer correctness.
Unavailable search does not create fictional citations or prevent note/model
practice. The UI explicitly reports that no references could be retrieved.

## Existing local search setup

Managed startup reuses an already-running search service. If the private existing
`infrastructure/.env.openwebui` configuration is present, it attempts to start
only the Compose `searxng` service. It does not create credentials or change Open
WebUI settings. The search service remains available for the separate WebUI.

To start the configured service manually:

```bash
sudo docker compose --env-file infrastructure/.env.openwebui -f infrastructure/compose.yaml up -d searxng
```

Without that private configuration, public search is attempted when selected.
Public search may be rate-limited or inaccessible on a network. In that case use
a working local search service, or paste relevant documentation into notes.

## Variation and repetition

Each exercise receives a fresh variation ID and model sampling seed. Recent
published task titles are supplied as avoidance context. SHA-256 fingerprints of
normalized instructions/starter code catch identical recent tasks before their
references are executed; a duplicate requests another variation. Generated-task
metadata survives completed sessions in SQLite and is cleared by Delete study
data. It contains titles/fingerprints, not a bank of prewritten questions.

This reduces exact repetition; semantic novelty still depends on model output.
All accepted variations go through the same independent review, execution, and
starter checks. No topic-specific answer implementation or template fallback is
used to force a session to succeed.
