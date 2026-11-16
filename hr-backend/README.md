# HR Policy Assistant: Backend v1

FastAPI service. React app calls it. Search uses local Hugging Face models + Pinecone; answers come from OpenRouter.

```
React ──► FastAPI ──► pipeline.ask()
                        1. input guard (injection patterns, last 3 turns included)
                        2. sensitive topic? ──► tell employee, offer "Talk to HR"
                        3. rewrite follow-up using conversation memory
                        4. embed (bge-small, local) ──► semantic cache (keyed by country/type/level)
                        5. Pinecone search, filtered by employee profile
                        6. bge-reranker (local) ──► score floor (weak match = "not found")
                        7. OpenRouter answers ONLY from numbered excerpts (JSON)
                        8. verify citations, output guard, save cache + memory
```

## Document format (same as your existing files)
```
Policy Category: Leave        <- required
Country: India                <- optional (default ALL; "India, US" allowed)
Employment Type: full_time    <- optional (default ALL)
Role Level: manager           <- optional (default ALL)
Status: active                <- optional (retired docs are never retrieved)
```
Optional sidecar `file.txt.meta.json` overrides headers. PDFs keep page numbers for citations.

## Run
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your NEW OpenRouter and Pinecone keys

python -m unittest                            # offline tests, no keys needed
python ingest.py --dry-run                    # check document labels, no cloud calls
python ingest.py                              # downloads the HF models once, creates the Pinecone index, uploads
python ingest.py --force                      # delete + rebuild the index (after removing docs or changing models)
uvicorn hr_assistant.api:create_app --factory --reload
```
Try it (dev mode): `curl -H "X-Dev-User: priya@acme.com" localhost:8000/me`
Interactive docs: http://localhost:8000/docs

## API for the React app
| Endpoint | Purpose |
|---|---|
| `GET /me` | Profile (country, role, `is_hr`) for the header and role-based screens |
| `POST /ask` `{question, conversation_id?}` | Answer + `citations[]` + `escalate` flag. Reuse the returned `conversation_id` for follow-ups |
| `GET /conversations/{id}` / `DELETE` | Restore or clear a conversation |
| `POST /escalate` `{conversation_id, note}` | Employee clicks "Talk to HR": creates a ticket with the transcript |
| `POST /feedback` | Thumbs up/down |
| `GET /hr/tickets?status=` , `GET/PATCH /hr/tickets/{id}` | HR dashboard (HR users only) |

`answered_from`: `documents`, `cache`, `none` (not found), `escalation` (sensitive), `blocked`.
When `escalate` is true, show the "Talk to HR" button.

## Auth
Dev mode only for now: send `X-Dev-User: email`. Employees come from `employees.json`, which also acts as the allow-list.
Country and role always come from that record, never from the chat text. Real sign-in is a later step.

## Pinecone note
Uses Pinecone's current Documents API (Python SDK 10+). The index is created by `ingest.py` with a
schema: dense field `embedding` (384, cosine) + full-text field `text`. Do not create the index by hand in the
console. If an index with the same name already exists with a different shape, run `python ingest.py --force`
(or delete it in the console first). Newly upserted documents can take a few seconds to become searchable.

## Known limits
- Retrieval is dense-only (no keyword/BM25 half yet). The reranker compensates; add hybrid if tests show missed exact-term matches.
- `MIN_RERANK_SCORE` (0.3) is a starting guess for the bge reranker: tune it on your documents.
- Memory, cache and rate limits are in-process (reset on restart); tickets are a SQLite file. Move both to a database later.
- Citations show document and page but have no clickable link until originals move to blob storage.
- Guardrails are regex patterns (`heuristic`) or an OpenRouter classifier (`llm`).
