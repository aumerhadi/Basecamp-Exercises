# E-mail API

FastAPI backend over an inbox of e-mails, stored in SQLite and populated by
importing a JSON file.

## Running the server

Requires Python 3.10+ for the `X | None` annotations FastAPI resolves at import
time; developed against 3.13. All commands run from this `api/` folder —
`app.main` is resolved relative to the working directory.

**1. Activate an environment.** The repo already ships one at the root, which is
the simplest option:

```bash
source ../.venv/Scripts/activate     # Windows
source ../.venv/bin/activate         # macOS / Linux
```

Or create one just for the API: `python -m venv .venv && source .venv/Scripts/activate`.

**2. Install the dependencies.**

```bash
pip install -r requirements.txt
```

**3. Start uvicorn.**

```bash
uvicorn app.main:app --reload --port 8000
```

`--reload` restarts on file changes; drop it outside development. On startup the
app creates `../data/emails.db` and its schema if they are not there yet, so the
first run needs no migration step.

**4. Check it is up.**

```bash
curl http://localhost:8000/health      # {"status":"ok"}
curl http://localhost:8000/emails      # [] until you import
```

Interactive docs — including a file picker for the import endpoint — are at
<http://localhost:8000/docs>. Stop the server with `Ctrl-C`.

A fresh database is empty; see [Import](#import) below for getting e-mails in.

### Configuration

| Variable         | Default                   | Purpose                                  |
| ---------------- | ------------------------- | ---------------------------------------- |
| `EMAILS_DB_PATH` | `../data/emails.db`       | Where the SQLite file lives.              |
| `CORS_ORIGINS`   | `http://localhost:3000`   | Comma-separated allowed origins. The default matches the Next.js client in `../client`. |

```bash
EMAILS_DB_PATH=/tmp/scratch.db uvicorn app.main:app --port 8000
```

## Endpoints

| Method | Path                | Notes                                                       |
| ------ | ------------------- | ----------------------------------------------------------- |
| POST   | `/emails/import`    | Multipart upload of a JSON file. See below.                   |
| GET    | `/emails`           | All e-mails, newest first. `?q=` searches subject + body, `?priority=` filters. Trailing slash also works. |
| GET    | `/emails/{id}`      | One e-mail; `404` if the id is unknown.                       |
| GET    | `/emails/summarize` | Summary of the matching e-mails. Accepts `q`, `priority`, `ids`. **Stub** — see below. |
| POST   | `/summarize`        | Queue a summarization job for a list of e-mail ids; returns its id. |
| GET    | `/summarize`        | Queued jobs still waiting for a summary. Trailing slash also works. |
| GET    | `/summarize/{id}`   | That job's `summary`; `404` if the id is unknown.              |
| POST   | `/agenda`           | Store the plan of a day. One plan per day; storing again replaces it. |
| GET    | `/agenda`           | Today's plan. Trailing slash also works.                      |
| GET    | `/agenda/{day}`     | The plan of one day, `DD-Mon-YYYY` or `YYYY-MM-DD`; `404` if none. |
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
- `id` is assigned by the API and always present in responses. It is optional on
  import — see below.

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
- **`id` may be omitted**, as it is in a plain mail export. Those items are
  appended under fresh ids, counting up from the highest id already in the table
  and the highest one named in the file. Note the consequence: without ids there
  is nothing to match on, so re-importing the same file adds the e-mails again.
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

### Summarization queue

`/summarize` is the asynchronous route: a request is *queued* rather than
answered, and the summary is fetched later by id.

```bash
curl -X POST http://localhost:8000/summarize \
     -H 'Content-Type: application/json' -d '[1, 2, 3]'
# 201 {"id":1}

curl http://localhost:8000/summarize        # jobs still awaiting a summary
# [{"id":1,"emailIds":[1,2,3],"summary":null,"createdAt":"2026-07-28T21:42:38.722385Z"}]

curl http://localhost:8000/summarize/1      # {"id":1,"summary":null} until filled in
```

The body is a plain JSON array of e-mail ids; an empty array is a `422`. Rows
land in the `summarize_queue` table with `summary` NULL, and `GET /summarize`
lists exactly those — a job counts as pending while `summary` is NULL *or* the
empty string, so a worker cannot make one vanish by writing `''`. Ids are not
checked against the `emails` table at enqueue time.

Nothing drains the queue yet: writing the summaries is the missing half, and
until it exists `GET /summarize/{id}` keeps returning `null` for a known id.

| Column       | Type                          |
| ------------ | ----------------------------- |
| `id`         | INTEGER, auto-assigned rowid   |
| `email_ids`  | TEXT — JSON array of ids       |
| `summary`    | TEXT, nullable                 |
| `created_at` | TEXT — ISO-8601 UTC timestamp  |

`email_ids` is JSON because SQLite has no list type and the queue only ever
reads the set back whole; `created_at` is ISO for the same sortability reason as
`emails.sent_at`.

## Agenda

The plan of one day: the e-mails to deal with first, plus free-text meeting and
support notes. Stored in its own `agenda_queue` table.

```bash
curl -X POST http://localhost:8000/agenda -H 'Content-Type: application/json' -d '{
  "top": [3, 1, 2],
  "meeting": "Standup 10:00, design review 15:00",
  "support": "On call: Dana until 18:00",
  "date": "2026-07-28T09:00:00"
}'
# 201 {"top":[{"id":3,...},{"id":1,...},{"id":2,...}],"meeting":"...","support":"...","date":"2026-07-28T09:00:00"}

curl http://localhost:8000/agenda                 # today's plan
curl http://localhost:8000/agenda/28-Jul-2026     # a given day — YYYY-MM-DD works too
```

- **`top` holds e-mail ids or whole e-mail objects.** Either way only the ids are
  stored, and the e-mails are read back from the `emails` table, so an agenda
  never carries a stale copy of a subject or body. Every id must already be in
  the inbox — an unknown one is a `422` naming it.
- **Order is preserved** exactly as posted, unlike `GET /emails`, which sorts by
  date; a repeated id keeps its first position and is stored once.
- **One plan per day** — `date` is a full timestamp, but the day it falls on is
  unique, so posting again for that day replaces the plan rather than adding a
  second one.
- **`date` is optional** and defaults to now, which makes a body without it
  today's plan. `GET /agenda` likewise means today by the server's local clock.
- A day with no plan stored is a `404`, and an unparseable day is a `422`.

| Column       | Type                                        |
| ------------ | ------------------------------------------- |
| `id`         | INTEGER, auto-assigned rowid                 |
| `day`        | TEXT — `YYYY-MM-DD`, UNIQUE, derived from `date` |
| `date`       | TEXT — ISO-8601 timestamp as posted          |
| `email_ids`  | TEXT — JSON array of ids                     |
| `meeting`    | TEXT                                         |
| `support`    | TEXT                                         |
| `created_at` | TEXT — ISO-8601 UTC, when the day's plan was first stored |

`day` exists because `date` is a timestamp: lookups and the one-per-day
constraint need the calendar day on its own. Replacing a plan leaves
`created_at` alone.

## Layout

```
app/
  main.py            FastAPI app, lifespan schema bootstrap, CORS (http://localhost:3000)
  db.py              SQLite path, connection factory, schema
  models.py          Email / EmailSummary / ImportResult / SummarizeJob / Agenda contract
  repository.py      SQL queries and upserts, one class per table
  summarizer.py      summarization stub
  routers/emails.py     /emails routes
  routers/summarize.py  /summarize queue routes
  routers/agenda.py     /agenda routes
```
