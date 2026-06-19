# PulseMetrics

A self-hosted log monitoring and alerting service with AI-powered semantic log clustering. Ingest logs from any source, search them instantly, fire alerts when things go wrong — and automatically detect brand-new error patterns before you've even written a rule for them.

---

## What makes it different

Most monitoring tools alert on patterns **you already know about**. PulseMetrics adds a semantic clustering layer: every log message is embedded using a local sentence-transformer model, clustered by meaning, and new clusters trigger alerts automatically. A bug that ships a never-before-seen error message gets caught on the first occurrence.

---

## Architecture

```
Browser (dashboard)
        │
        ▼
   FastAPI API  ←──────────────── Agent (tails log files)
        │
        ├─── PostgreSQL (logs + pgvector clusters)
        │
        └─── Redis ──► Celery Worker (parsing, embedding, rules, notifications)
                            │
                            └─── Celery Beat (30s rule evaluation scheduler)
```

| Component | Technology | Why |
|---|---|---|
| API | FastAPI + asyncpg | Async I/O, handles 1k+ req/s per core |
| Database | PostgreSQL 16 + pgvector | Unified store: relational + vector + full-text search |
| Async jobs | Celery + Redis | Durable task queue; embeddings don't block the API |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | 384-dim, ~5ms on CPU, no API costs |
| Charts | matplotlib | Server-side PNG, works in emails and curl |

---

## Quick start

**Prerequisites:** Docker and Docker Compose

```bash
# 1. Clone and configure
git clone https://github.com/Peeyush237/PulseMetrics-AI-powered-log-monitoring-service.git
cd PulseMetrics
cp .env.example .env
# Edit .env — at minimum change JWT_SECRET

# 2. Start all services
cd docker
docker compose up -d

# 3. Run database migrations
docker compose exec api alembic upgrade head

# 4. Open the dashboard
open http://localhost:8000/ui

# 5. (Optional) Seed with demo data
docker compose exec api python scripts/seed_data.py
```

---

## Sending logs

### Direct HTTP (any language)

```bash
# Get your API key from Settings → Applications → Create
curl -X POST http://localhost:8000/api/v1/logs/ingest \
  -H "X-Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {
        "timestamp": "2026-06-20T14:32:11Z",
        "level": "ERROR",
        "service": "payments",
        "message": "Connection to db-host-1 failed after 3.2s",
        "metadata": {"user_id": 4521, "trace_id": "abc123"}
      }
    ]
  }'
```

### Agent (tails log files automatically)

```bash
pip install ./agent

pulsemetrics-agent \
  --api-key YOUR_API_KEY \
  --url http://localhost:8000 \
  --file /var/log/myapp.log \
  --batch-size 100 \
  --batch-interval 5
```

---

## Creating an alert rule

```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a threshold rule: fire if >10 payment errors in 5 minutes
curl -X POST "http://localhost:8000/api/v1/rules?application_id=YOUR_APP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payment error spike",
    "rule_type": "threshold",
    "config": {
      "filters": {"level": ">=ERROR", "service": "payments"},
      "window_seconds": 300,
      "threshold": 10
    },
    "cooldown_seconds": 900,
    "channel_ids": ["YOUR_CHANNEL_ID"]
  }'
```

---

## API Reference

Full interactive docs at **http://localhost:8000/api/docs**

| Group | Endpoints |
|---|---|
| Auth | `POST /api/v1/auth/register`, `/login`, `/refresh` |
| Applications | `GET/POST /api/v1/applications`, `POST /{id}/rotate-key` |
| Ingestion | `POST /api/v1/logs/ingest` (API key auth) |
| Search | `POST /api/v1/logs/search`, `GET /api/v1/logs/{id}` |
| Clusters | `GET/PATCH /api/v1/clusters` |
| Rules | Full CRUD at `/api/v1/rules` |
| Channels | Full CRUD at `/api/v1/channels` |
| Alerts | `GET /api/v1/alerts` |
| Analytics | `GET /api/v1/analytics/timeline.png`, `/top-errors.png`, `/summary` |
| Health | `GET /health`, `/metrics` (Prometheus) |

---

## Alert rule types

| Type | Description | Example use |
|---|---|---|
| `threshold` | Count of matching logs > N in window | "10+ payment errors in 5 min" |
| `regex` | Any log matching a pattern | "OutOfMemory or cannot allocate" |
| `novelty` | New log cluster appears | "Something we've never seen before" |
| `rate_of_change` | Error rate jumps by X% vs previous window | "Error rate doubled" |
| `anomaly` | Count exceeds mean + N×stddev of baseline | "Statistically unusual spike" |

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/unit/ -v          # Fast, no Docker needed
pytest tests/integration/ -v   # Requires Postgres + Redis (testcontainers spins them up)
```

---

## Load test

```bash
# Edit scripts/load_test.py to set API_KEY first
python scripts/load_test.py
```

Expected throughput: 1000+ entries/sec on a 4-core machine.

---

## Configuration

All config via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL async connection string |
| `REDIS_URL` | — | Redis connection string |
| `JWT_SECRET` | — | **Change this in production** |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace model name |
| `CLUSTERING_THRESHOLD` | `0.85` | Cosine similarity for cluster assignment |
| `DEFAULT_RETENTION_DAYS` | `30` | Log retention per application |

---

## Production deployment

Single VM (4 vCPU, 8 GB RAM):

1. Point a domain at the VM
2. Put Caddy or Nginx in front for HTTPS
3. `docker compose up -d` — that's it
4. Set up daily `pg_dump` backup

Scale path (v2): Kubernetes, Redis Streams, sharded Postgres.

---

## Design decisions

**Why Postgres for vectors instead of Pinecone?** One fewer service. pgvector + HNSW index handles millions of embeddings with sub-10ms query latency — more than enough at this scale.

**Why Celery instead of asyncio background tasks?** Durability. If the API process dies mid-embedding, Celery retries. asyncio tasks die with the process.

**Why local embeddings instead of OpenAI?** Cost and latency. Embedding 1000 logs/sec via the OpenAI API costs ~$50/day. Local inference is 5ms per message and free after model download.

**Why monthly table partitioning?** Dropping old data is `DROP TABLE logs_2026_01` — O(1), no bloat, no vacuum pressure. `DELETE` on a 100M-row table takes hours.

---

## Repo structure

```
app/               FastAPI application
├── api/v1/        HTTP endpoints
├── core/          Config, logging, security
├── db/models/     SQLAlchemy models
├── parsers/       Log parsing (JSON, Syslog, Regex, PlainText)
├── rules/         Alert rule engine (5 rule types)
├── notifiers/     Notification backends (Slack, Email, Webhook, Console)
├── services/      Business logic (clustering, ingestion, analytics)
├── tasks/         Celery workers and beat schedule
└── templates/     HTML dashboard

agent/             Standalone log-shipping CLI
alembic/           Database migrations
tests/             Unit + integration tests
scripts/           Seed data, load test, partition check
docker/            Dockerfile + docker-compose.yml
```
