# Deploying Sift (free tier)

This deploys Sift to a real, internet-reachable URL using only free-tier
services: [Neon](https://neon.tech) (Postgres + pgvector) and
[Render](https://render.com) (the API, built from this repo's `Dockerfile`).

Both are genuinely free (no card required for Neon; Render's free web
service tier requires no card either, but cold-starts after inactivity —
see "What to expect" below).

## 1. Create the Neon project

1. In your Neon dashboard, click **New project**, name it `sift`.
2. Once created, open the project's connection details and copy the
   connection string. It looks like:
   ```
   postgresql://<user>:<password>@<host>/<dbname>?sslmode=require
   ```
3. From that string, note the four pieces you'll need separately:
   `<user>`, `<password>`, `<host>`, `<dbname>`.

## 2. Enable pgvector on the Neon database

Connect with `psql` (Neon's dashboard shows the exact command) and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
The first Alembic migration also does this (`CREATE EXTENSION IF NOT
EXISTS vector`), so this step is a safety net, not strictly required, but
worth confirming directly before trusting the migration to do it.

## 3. Run migrations, ingest the corpus, and seed demo users — once, from your local machine

Neon is a normal, internet-reachable Postgres endpoint, so these run
exactly like local development, just pointed at Neon instead of the local
Docker Compose database. Temporarily set these in your local `.env` (or
export them in your shell for one command session — don't leave your real
`.env` pointed at production afterward):

```
POSTGRES_USER=<user from step 1>
POSTGRES_PASSWORD=<password from step 1>
POSTGRES_DB=<dbname from step 1>
POSTGRES_HOST=<host from step 1>
POSTGRES_SSLMODE=require
```

Then run, in order:
```bash
uv run alembic upgrade head
uv run python -m app.ingestion.ingest_corpus
uv run python -m app.auth.seed_users
```

This only needs to happen once. The deployed container re-runs migrations
on every deploy (see the Dockerfile's `CMD`), but ingestion and seeding
are idempotent and not part of the container's own startup — re-running
them against an already-populated database is safe if you ever need to,
but nothing runs them automatically.

**Revert your local `.env` back to local Postgres afterward**, so local
development keeps talking to your local Docker Compose database, not Neon.

## 4. Create the Render service

1. In Render, choose **New > Blueprint**, connect this GitHub repo. Render
   reads `render.yaml` and proposes the `sift-api` web service.
2. Render will prompt for the environment variables marked `sync: false`
   in `render.yaml`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
   `POSTGRES_HOST` (all four from step 1) and `GROQ_API_KEY` (a real,
   free key from [console.groq.com](https://console.groq.com)).
3. `JWT_SECRET_KEY` is generated automatically by Render (`generateValue:
   true`) — never the checked-in local-dev placeholder from
   `app/config.py`.
4. Deploy. Render builds the Dockerfile (this bakes the embedding and
   reranker model weights into the image — the first build will take a
   few minutes for this reason) and starts the service.

## 5. Verify it's actually live

```bash
curl -X POST https://<your-render-url>/auth/login -d "username=admin&password=demo-admin-pw"
curl -X POST https://<your-render-url>/query -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"query": "What channels does the Notifications service use?"}'
```

## What to expect on the free tier

- **Cold starts.** Render's free web services sleep after inactivity; the
  first request after a period of no traffic will be slow (the container
  has to start, and the embedding/reranker models have to load into
  memory) before the API responds.
- **512MB RAM is a real, confirmed constraint, not just a theoretical
  risk.** During real usage testing (2026-09-17/18), the live instance
  genuinely exceeded its memory limit and was auto-restarted by Render
  after a short sequence of real `/query` requests (a couple of
  successful calls, then a `502` on the next one, with Render's own
  incident notification explicitly citing "exceeded its memory limit").
  After the automatic restart, subsequent requests succeeded normally —
  so this reads as intermittent memory pressure building up across
  requests, not a hard "never fits" failure on every single call.
  **Not yet root-caused further** (e.g., via Render's memory-usage graph
  over time, to see whether baseline idle memory is already near the
  limit or whether it's specifically request-handling that spikes it) —
  a deliberate choice to document this honestly as a known, live,
  confirmed limitation for now rather than chase a fix immediately. If a
  `502` shows up, retrying after a few seconds (Render auto-restarts) is
  the practical workaround; a real fix would start with that memory
  graph, not a guess.
- **The demo credentials are intentionally public** (`app/auth/seed_users.py`
  documents this choice) — they protect a small, fictional, non-sensitive
  demo corpus, the same trust level as the project's other checked-in
  dev-only credentials.
