# E-mail API

FastAPI backend over an inbox of e-mails, stored in SQLite and populated by
importing a JSON file.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>

## Endpoints

| Method | Path                | Notes                                                       |
| ------ | ------------------- | ----------------------------------------------------------- |
| POST   | `/emails/import`    | Multipart upload of a JSON file. See below.                   |
| GET    | `/emails`           | All e-mails, newest first. `?q=` searches subject + body, `?priority=` filters. Trailing slash also works. |
| GET    | `/emails/{id}`      | One e-mail; `404` if the id is unknown.                       |
| GET    | `/emails/summarize` | Summary of the matching e-mails. Accepts `q`, `priority`, `ids`. **Stub** — see below. |
| GET    | `/health`           | Liveness probe.                                               |

`/emails/summarize` is registered before `/emails/{id}` so the path parameter
does not swallow it.

## Data contract

```json
{
  "id": 1,
  "from": "test@gmail.com",
  "to": "test@gmail.com",
  "subject": "Critical Bug",
  "body": "Email text",
  "priority": "critical",
  "date": "28-Jul-2026",
  "time": "13:53",
  "highPriority": true
}
```

- `priority` is one of `low` / `medium` / `critical`.
- `date` is `DD-Mon-YYYY`, `time` is 24-hour `HH:MM`.
- `highPriority` is optional — when absent it is derived as `priority == "critical"`.
- `id` is **required**: it is the key the importer upserts on.

## Import

```bash
curl -F "file=@emails.json" http://localhost:8000/emails/import
# {"received":12,"inserted":10,"updated":2,"emailIds":[...]}
```

The file holds a JSON array of the objects above (a single object is also
accepted). Behaviour worth knowing:

- **Upsert by id** — an id already in the database is overwritten, so importing
  the same file twice is idempotent. Duplicate ids *within* one file resolve to
  the last occurrence.
- **All or nothing** — every item is validated before anything is written. One
  bad item means a `422` naming its index and field, and no rows change.
- `400` for malformed JSON, `413` above 5 MB.

## Storage

SQLite, at `../data/emails.db` relative to this folder (the repo-root `data/`
folder). The file and its schema are created on startup; the database is
gitignored. Point `EMAILS_DB_PATH` elsewhere to override.

Alongside the contract fields the table keeps a derived `sent_at` column holding
an ISO timestamp: `DD-Mon-YYYY` does not sort lexicographically, so ordering
"newest first" needs a sortable copy. Search uses a `casefold` SQL function
registered on the connection rather than plain `LIKE`, which keeps matching
Unicode-aware and treats `%` and `_` in a query as literal characters.

## Summarization

`app/summarizer.py::summarize()` is intentionally unimplemented: it returns
`None`, and the endpoint reports the final response shape with
`"summary": null, "status": "not_implemented"`. Fill in the function body — the
router needs no changes once it returns a string.

## Layout

```
app/
  main.py            FastAPI app, lifespan schema bootstrap, CORS (http://localhost:3000)
  db.py              SQLite path, connection factory, schema
  models.py          Email / EmailSummary / ImportResult contract
  repository.py      SQL queries and upsert
  summarizer.py      summarization stub
  routers/emails.py  /emails routes
```
