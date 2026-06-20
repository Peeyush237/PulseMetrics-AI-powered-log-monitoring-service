# PulseMetrics — Product Requirements Document

**Version:** 1.0
**Author:** Peeyush Mishra
**Status:** Draft for portfolio build
**Last updated:** June 2026

---

## 1. Executive Summary

PulseMetrics is a self-hosted log monitoring and alerting service that ingests application logs from any source, stores them in a queryable database, evaluates user-defined alert rules against the stream, and notifies the team when something is wrong. A novel AI-powered clustering layer groups semantically similar log messages and surfaces previously unseen error patterns as they emerge.

**Elevator pitch:** "It's like Datadog Logs or Grafana Loki — but small, opinionated, and built to demonstrate solid Python engineering. Instead of reacting to known errors, it learns the shape of your normal logs and tells you when something new appears."

**Target user:** A backend or DevOps engineer at a small-to-mid-sized company who wants log monitoring without paying $500/month or running a Kubernetes-scale observability stack.

---

## 2. The Problem

Every application generates logs. They are the system's running commentary — what it did, what it tried, what failed.

In a healthy team, logs are read continuously by automated tools. In most teams, they are written and never read. They pile up in text files until disk space runs out or until a customer complains and someone greps frantically through last week's archive.

The market has solutions — Datadog, Splunk, New Relic, Sumo Logic, Grafana Loki — but they are either expensive (Datadog can cost more than the team's AWS bill) or operationally complex (Loki + Promtail + Grafana + alertmanager is a real stack to run). Small teams end up with nothing.

PulseMetrics targets the gap: a single-binary, Docker-compose-able log monitor that does 80% of what the giants do, with one differentiated feature (semantic clustering) that the giants charge premium tiers for.

---

## 3. Product Vision & Goals

### Vision

A log monitoring service that a one-person team can deploy on a single VM, integrate with three lines of code, and rely on to surface problems before users do.

### Primary goals

1. **Ingest logs reliably** from any source via a simple HTTP endpoint or a lightweight agent.
2. **Store and query** logs efficiently, supporting both structured search and full-text search.
3. **Evaluate alert rules** continuously and notify users through multiple channels.
4. **Surface novel errors** automatically using semantic clustering — the differentiated feature.
5. **Be observable itself** — the tool eats its own dogfood.

### Non-goals (explicit)

- **Distributed/horizontally-scalable architecture.** Single-node design. A real production deployment would need to scale, but that is out of scope for a 5-day build.
- **Multi-region or HA.** No leader election, no replication.
- **General-purpose APM.** No tracing, no metrics-as-a-first-class-citizen. Logs only.
- **A pretty frontend.** A functional dashboard is required, but pixel-perfect UI is not.
- **Mobile SDKs or browser SDKs.** Server-side log sources only.

### Success metrics (for portfolio defense)

- Can ingest **1000+ log lines/second** on a single 4-core VM.
- p95 query latency **under 500ms** for searches over the last 24 hours.
- Alert evaluation latency **under 30 seconds** from log arrival to notification.
- **>80%** test coverage on business logic.
- `mypy --strict` clean across `app/`.

---

## 4. Target Users & Personas

### Primary: "Priya the platform engineer"

Mid-level backend engineer at a 20-person startup. Runs Python and Node services on three EC2 instances. Has tried Loki but found it too complex; tried Datadog but the bill scared her. Wants something she can set up in an afternoon, get alerts in Slack, and stop worrying about.

### Secondary: "Daniel the on-call developer"

Junior engineer who gets paged at 2am. Cares about one thing: when the alert fires, can he get from the notification to the root cause in under 10 minutes? Needs fast search, good context, and links from alerts directly to the relevant log lines.

### Tertiary: "Maya the engineering manager"

Wants a weekly view of error trends. Doesn't care about individual log lines. Wants charts showing "are we getting better or worse?"

---

## 5. Core Features

### 5.1 Log Ingestion

**What it does:** Accepts log entries from any source. Two ingestion paths:

1. **HTTP POST endpoint** — `POST /api/v1/logs/ingest` accepts a JSON array of log entries, authenticated by a per-application API key. Suitable for direct integration from any language.
2. **Lightweight Python agent** — a CLI tool (`pulsemetrics-agent`) that tails log files using `subprocess` (`tail -F`), batches lines, and ships them to the ingestion endpoint. Includes a local disk buffer so logs survive network outages.

**Accepted formats:**
- JSON (structured logs — preferred)
- Plain text with auto-detection (timestamp + level + message)
- Syslog (RFC 5424)
- Custom regex-defined formats

**Constraints:**
- Max batch size: 1000 entries
- Max entry size: 64 KB
- Rate limit: 5000 entries/sec per application

### 5.2 Log Parsing & Storage

**What it does:** Takes raw log lines and extracts structured fields (timestamp, severity, service name, message body, custom attributes).

**Design:** An abstract `LogParser` base class with concrete subclasses:
- `JSONParser` — parses JSON logs directly
- `SyslogParser` — handles RFC 5424
- `RegexParser` — user-configurable pattern matching
- `PlainTextParser` — heuristic fallback

The parser is selected per-application based on configuration. Parsed entries are written to PostgreSQL.

**Storage strategy:**
- A `logs` table partitioned by month (PostgreSQL native partitioning).
- Indexes: `(application_id, timestamp DESC)`, GIN index on the JSONB metadata column for attribute search.
- A `tsvector` column on the message body with a GIN index for full-text search.
- Retention policy: configurable per-application, default 30 days. A Celery beat job drops old partitions.

### 5.3 Search & Query

**What it does:** Lets users find log lines by any combination of:
- Time range (required)
- Application
- Severity level (`>= ERROR`, `== INFO`, etc.)
- Service name
- Full-text match on message
- Structured attribute filters (`user_id = 4521`, `latency_ms > 1000`)
- Cluster ID (see §5.7)

**API:** `POST /api/v1/logs/search` with a JSON query body. Returns paginated results with cursor-based pagination.

**Performance target:** p95 < 500ms for 24-hour windows over 10M log lines.

### 5.4 Alert Rules Engine

**What it does:** Continuously evaluates user-defined rules against incoming logs and fires alert events when conditions are met.

**Rule types (each is an OOP class):**

| Rule type | Class | What it does |
|---|---|---|
| Threshold | `ThresholdRule` | "Fire if count of matching logs in window > N" |
| Regex match | `RegexRule` | "Fire on any log matching this regex" |
| Rate of change | `RateOfChangeRule` | "Fire if rate increases >X% vs previous window" |
| Novelty | `NoveltyRule` | "Fire when a new cluster appears" (see §5.7) |
| Anomaly | `AnomalyRule` | "Fire when count is >N standard deviations from baseline" |

**Configuration:** Rules are defined via the API as JSON payloads. Each rule has a name, an enabled flag, a target (application + filters), a time window, and channel bindings.

**Evaluation:** Celery beat fires every 30 seconds. For each enabled rule, a Celery task is dispatched. The task instantiates the rule class, runs `.evaluate(window)`, and if it fires, creates an `AlertEvent` and dispatches notification tasks.

**Deduplication:** Each rule has a cooldown period to prevent alert storms.

### 5.5 Notification Delivery

**What it does:** Sends alert events to configured channels.

**Channel types (OOP again):**
- `EmailNotifier` — SMTP
- `SlackNotifier` — incoming webhook
- `WebhookNotifier` — generic POST to any URL
- `ConsoleNotifier` — for development

Each notifier implements a common `Notifier.send(alert_event)` interface. Adding a new channel type means writing one class.

**Reliability:** Notification dispatches are Celery tasks with exponential backoff retries. Failed notifications are logged.

### 5.6 Dashboard & Analytics

**What it does:** A web dashboard for browsing logs, configuring rules, viewing alerts, and seeing trends.

**Pages:**
- **Overview** — recent alerts, log volume by application, error rate trend
- **Search** — interactive log search with filter builder
- **Rules** — list, create, edit, delete alert rules
- **Alerts** — history of fired alerts with drill-down to triggering logs
- **Clusters** — explore log clusters, see members, mark as ignored or important
- **Settings** — applications, API keys, notification channels, users

**Analytics charts:** Server-side rendering using matplotlib. Endpoints return PNG. Charts include:
- Log volume over time (line chart, by severity)
- Latency percentiles (p50/p95/p99) where latency is extracted as a metadata field
- Top error messages (bar chart)
- Cluster growth (new clusters per day)

**Note for build:** A minimal HTML+vanilla-JS or HTMX dashboard is sufficient. Spending days on React is not the use of time here. The API is the product.

### 5.7 AI Log Clustering — the differentiated feature

**What it does:** Groups semantically similar log messages and detects when previously-unseen messages appear.

**Why it matters:** Most monitoring tools alert on patterns you already know about ("alert me on 'OutOfMemory'"). New problems show up as new error messages — but you can't write a rule for an error you haven't seen yet. Clustering catches these.

**How it works:**

1. On ingestion, each log message is normalized (replace numbers, UUIDs, timestamps with placeholders → `"Connection to host db-7 failed after 3.2s"` becomes `"Connection to host <ID> failed after <NUM>s"`).
2. The normalized message is embedded using `sentence-transformers/all-MiniLM-L6-v2` (384-dimension vector, runs on CPU in ~5ms).
3. The embedding is compared against existing cluster centroids using pgvector's HNSW index.
4. If the nearest cluster's cosine similarity is above a threshold (default 0.85), assign the log to that cluster and update the centroid (running average).
5. If no cluster matches, create a new cluster. **This triggers a `NoveltyRule` if one is configured.**

**Data model:**
- `log_clusters` table: id, application_id, centroid (vector(384)), representative_message, first_seen, last_seen, member_count, is_acknowledged.
- `logs.cluster_id` foreign key.

**Why this isn't gimmicky:**
- It uses a small, fast, well-understood model — not an LLM call per log line.
- It runs locally — no external API costs.
- The novelty detection is genuinely useful: "something new is happening" is a real signal.
- The data model is sound — clusters are first-class entities you can browse, name, and build rules around.

### 5.8 User Management & Multi-tenancy

**What it does:** Supports multiple organizations, each with its own users, applications, and data.

**Model:**
- Organizations (tenants)
- Users belong to one organization, have a role (`admin` or `member`)
- Applications belong to an organization
- All data is scoped by organization — enforced at the repository layer

**Auth:** JWT-based, 24-hour access tokens, refresh tokens. Standard FastAPI + `python-jose` setup. Bcrypt for password hashing.

**API keys:** Each application has an API key (used by the agent for ingestion). Stored as a SHA-256 hash. Rotatable.

---

## 6. User Flows

### Flow 1: Initial integration

1. User signs up, creates an organization.
2. User creates an application ("backend-api") → receives an API key.
3. User installs the agent on their server: `pip install pulsemetrics-agent`.
4. User runs `pulsemetrics-agent --api-key XYZ --file /var/log/myapp.log --url https://pulse.mycompany.com`.
5. Within seconds, log lines appear in the dashboard's log search.

### Flow 2: Creating an alert rule

1. User goes to the Rules page, clicks "New rule".
2. Selects rule type: "Threshold".
3. Configures: "If count of logs where level=ERROR and service=payments in the last 5 minutes is greater than 10, fire."
4. Selects notification channel: Slack.
5. Sets cooldown: 15 minutes.
6. Saves. Rule is now active.

### Flow 3: Investigating an alert

1. Slack notification fires: "🚨 [payments] error spike — 47 errors in 5 minutes."
2. User clicks the link → lands on the alert detail page.
3. Sees the triggering logs, the cluster they belong to, and a chart of error volume over the last hour.
4. Clicks a log line to see full context (logs around it, same correlation ID).
5. Identifies root cause, fixes deployment, error rate drops.

### Flow 4: Discovering a new problem

1. A new deploy ships a bug that produces a never-before-seen error message.
2. The clustering layer creates a new cluster on the first occurrence.
3. The user's `NoveltyRule` ("alert on any new cluster in production") fires.
4. User is notified: "New log pattern detected: 'Failed to serialize user preferences: TypeError'."
5. User investigates and rolls back the deploy — before a customer notices.

This flow is the demo moment. Everything else is table stakes; this is what makes the project memorable.

---

## 7. System Architecture

### High-level view

```
                    ┌──────────────┐
                    │   Browser    │
                    │  (dashboard) │
                    └──────┬───────┘
                           │ HTTPS
                           ▼
   ┌────────────┐    ┌───────────────┐    ┌──────────────┐
   │   Agent    │───▶│   FastAPI     │◀──▶│ PostgreSQL   │
   │ (tails log │    │  - API        │    │ + pgvector   │
   │  files via │    │  - Auth       │    │              │
   │  subprocess)│   │  - Search     │    └──────────────┘
   └────────────┘    │  - Dashboard  │
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │     Redis     │
                     │ (queue+cache) │
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │ Celery worker │
                     │ - Parsing     │
                     │ - Embedding   │
                     │ - Rule eval   │
                     │ - Notify      │
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │ Notifiers     │
                     │ (Slack/email/ │
                     │  webhook)     │
                     └───────────────┘
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| **FastAPI app** | HTTP API surface — auth, CRUD, search, ingestion, analytics. No heavy processing. |
| **PostgreSQL** | Single source of truth. Logs, clusters, rules, users, alerts. With pgvector extension. |
| **Redis** | Celery broker. Also caches recent query results and rate-limit counters. |
| **Celery worker** | All async work: parsing batches, computing embeddings, evaluating rules, sending notifications, dropping old partitions. |
| **Celery beat** | Scheduler. Fires rule evaluation every 30s, partition maintenance daily. |
| **Agent** | Standalone CLI tool. Tails log files via subprocess, batches, ships to API. |

### Why this architecture

- **FastAPI for async I/O.** Ingestion is I/O bound; async lets us handle thousands of concurrent connections without threads.
- **Celery for CPU-bound work.** Embeddings, parsing, rule evaluation are not millisecond ops. They belong off the request path.
- **PostgreSQL only, not Elasticsearch.** Postgres can do full-text search (tsvector) and vector search (pgvector) competently up to millions of rows. Adding Elasticsearch would be premature optimization and operational overhead.
- **Redis for queue, not RabbitMQ.** Simpler, one fewer service, fine at this scale.

---

## 8. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | The job is Python. Modern features (`Self`, better generics, `tomllib`). |
| Web framework | FastAPI | Async-native, automatic OpenAPI, Pydantic integration, type-friendly. |
| ORM | SQLAlchemy 2.0 (async) | Industry standard, async support, mature. |
| Migrations | Alembic | Same family as SQLAlchemy, autogenerate works well. |
| Validation | Pydantic v2 | Built into FastAPI, fast, type-safe. |
| Async work | Celery + Redis | Battle-tested, well-documented, the JD asks for it. |
| Database | PostgreSQL 16 + pgvector | Single store for relational and vector data. |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | 384-dim, fast on CPU, 22MB model. |
| Numerical | NumPy | For percentile calculations, statistical operations. |
| Charting | matplotlib | Server-side PNG generation. The JD mentions it. |
| Config | pydantic-settings | Env var driven, type-safe config. |
| Logging | structlog | Structured JSON logs (eat your own dogfood). |
| Testing | pytest + testcontainers | Real Postgres+Redis in tests, not mocks. |
| Type checking | mypy --strict | Catches bugs at edit time. |
| Linting | ruff | Fast, comprehensive. |
| Container | Docker + docker-compose | Standard. |
| CI | GitHub Actions | Lint, type-check, test on every push. |

---

## 9. Data Model

### `organizations`

```sql
CREATE TABLE organizations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           CITEXT NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'member',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (role IN ('admin', 'member'))
);
```

### `applications`

```sql
CREATE TABLE applications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    api_key_hash    VARCHAR(64) NOT NULL UNIQUE,
    parser_type     VARCHAR(50) NOT NULL DEFAULT 'json',
    parser_config   JSONB NOT NULL DEFAULT '{}',
    retention_days  INTEGER NOT NULL DEFAULT 30,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, name)
);
```

### `logs` (partitioned by month)

```sql
CREATE TABLE logs (
    id              BIGSERIAL,
    application_id  UUID NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    level           VARCHAR(10) NOT NULL,
    service         VARCHAR(255),
    message         TEXT NOT NULL,
    message_tsv     TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', message)) STORED,
    raw             TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    cluster_id      UUID,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_logs_app_ts ON logs (application_id, timestamp DESC);
CREATE INDEX idx_logs_metadata ON logs USING GIN (metadata);
CREATE INDEX idx_logs_message ON logs USING GIN (message_tsv);
CREATE INDEX idx_logs_cluster ON logs (cluster_id) WHERE cluster_id IS NOT NULL;
```

### `log_clusters`

```sql
CREATE TABLE log_clusters (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id          UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    centroid                VECTOR(384) NOT NULL,
    representative_message  TEXT NOT NULL,
    first_seen              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    member_count            BIGINT NOT NULL DEFAULT 1,
    label                   VARCHAR(255),
    is_acknowledged         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_clusters_centroid ON log_clusters
    USING hnsw (centroid vector_cosine_ops);
CREATE INDEX idx_clusters_app ON log_clusters (application_id);
```

### `alert_rules`

```sql
CREATE TABLE alert_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    rule_type       VARCHAR(50) NOT NULL,
    config          JSONB NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    cooldown_seconds INTEGER NOT NULL DEFAULT 900,
    last_fired_at   TIMESTAMPTZ,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (rule_type IN ('threshold', 'regex', 'rate_of_change', 'novelty', 'anomaly'))
);
```

### `alert_events`

```sql
CREATE TABLE alert_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    fired_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    severity        VARCHAR(20) NOT NULL,
    payload         JSONB NOT NULL,
    sample_log_ids  BIGINT[]
);

CREATE INDEX idx_events_rule_time ON alert_events (rule_id, fired_at DESC);
```

### `notification_channels` and bindings

```sql
CREATE TABLE notification_channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    channel_type    VARCHAR(50) NOT NULL,
    config          JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (channel_type IN ('email', 'slack', 'webhook', 'console'))
);

CREATE TABLE rule_channel_bindings (
    rule_id    UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
    PRIMARY KEY (rule_id, channel_id)
);
```

---

## 10. API Design

All endpoints under `/api/v1`. JSON request/response unless noted.

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create org + first user |
| POST | `/auth/login` | Returns access + refresh JWT |
| POST | `/auth/refresh` | Exchange refresh for new access |

### Applications

| Method | Path | Description |
|---|---|---|
| GET | `/applications` | List apps in org |
| POST | `/applications` | Create app, returns API key (shown once) |
| GET | `/applications/{id}` | Detail |
| PATCH | `/applications/{id}` | Update name, parser, retention |
| DELETE | `/applications/{id}` | Soft delete |
| POST | `/applications/{id}/rotate-key` | Generate new API key |

### Ingestion

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/logs/ingest` | Bulk ingest log entries | API key (header) |

Request:
```json
{
  "entries": [
    {
      "timestamp": "2026-06-20T14:32:11Z",
      "level": "ERROR",
      "service": "payments",
      "message": "Connection to db-host-1 failed after 3.2s",
      "metadata": {"user_id": 4521, "trace_id": "abc123"}
    }
  ]
}
```

Response: `202 Accepted` with `{"accepted": N, "rejected": [...]}`. Processing is async.

### Search

| Method | Path | Description |
|---|---|---|
| POST | `/logs/search` | Search logs (filters + pagination) |
| GET | `/logs/{id}` | Get single log with context |

Search body:
```json
{
  "application_id": "uuid",
  "from": "2026-06-20T00:00:00Z",
  "to": "2026-06-20T23:59:59Z",
  "filters": {
    "level": [">=ERROR"],
    "service": ["payments"],
    "metadata.user_id": [4521],
    "message_contains": "timeout"
  },
  "cluster_id": "uuid-or-null",
  "limit": 100,
  "cursor": "opaque-token"
}
```

### Clusters

| Method | Path | Description |
|---|---|---|
| GET | `/clusters` | List clusters for app |
| GET | `/clusters/{id}` | Detail with sample messages |
| PATCH | `/clusters/{id}` | Set label, acknowledge |

### Rules, channels, alerts

Standard CRUD. Listed in the data model section.

### Analytics

| Method | Path | Description |
|---|---|---|
| GET | `/analytics/timeline.png` | Log volume over time, returns image/png |
| GET | `/analytics/summary` | JSON summary stats |
| GET | `/analytics/top-errors.png` | Bar chart |

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Checks DB + Redis connectivity |
| GET | `/health/ready` | Kubernetes-style readiness |

---

## 11. Detailed Component Specs

### 11.1 The Agent

A standalone Python CLI installable via pip. Lives in a separate package (`agent/`).

**Responsibilities:**
- Tail one or more log files (uses `subprocess.Popen(['tail', '-F', path])`).
- Batch lines (size-based or time-based, whichever hits first).
- Ship batches to the ingestion API.
- Buffer to local disk if the network fails.
- Rotate buffer files.

**CLI:**
```
pulsemetrics-agent \
    --api-key XYZ \
    --url https://pulse.example.com \
    --file /var/log/myapp.log \
    --batch-size 100 \
    --batch-interval 5 \
    --buffer-dir /var/lib/pulsemetrics
```

Uses `argparse`. The buffer uses `pathlib` for file management.

### 11.2 Ingestion API

A FastAPI router that:
1. Authenticates via API key header.
2. Validates payload with Pydantic.
3. Writes entries to a "raw_logs" Redis queue (lightweight).
4. Returns 202 immediately.

A Celery worker (`process_raw_logs_task`) drains the queue, parses each entry, computes embeddings, finds/creates clusters, inserts into `logs`.

### 11.3 Parser

```python
class LogParser(ABC):
    @abstractmethod
    def parse(self, raw: str) -> ParsedLog: ...

class JSONParser(LogParser):
    def parse(self, raw: str) -> ParsedLog:
        data = json.loads(raw)
        return ParsedLog(
            timestamp=parse_timestamp(data.get("timestamp")),
            level=data.get("level", "INFO").upper(),
            service=data.get("service"),
            message=data["message"],
            metadata={k: v for k, v in data.items()
                      if k not in {"timestamp", "level", "service", "message"}},
        )

class SyslogParser(LogParser):
    # RFC 5424 regex
    ...

class RegexParser(LogParser):
    def __init__(self, pattern: str, field_map: dict[str, str]): ...
    def parse(self, raw: str) -> ParsedLog: ...

class PlainTextParser(LogParser):
    # Heuristic timestamp + level extraction
    ...
```

A `ParserFactory.from_application(app)` returns the right parser for an app's config.

### 11.4 Storage layer

Repository pattern. One repo per aggregate.

```python
class LogRepository:
    def __init__(self, session: AsyncSession): ...
    async def bulk_insert(self, logs: list[Log]) -> None: ...
    async def search(self, query: LogQuery) -> SearchResult: ...
    async def get_with_context(self, log_id: int) -> LogWithContext: ...

class ClusterRepository:
    async def find_nearest(self, app_id: UUID, embedding: np.ndarray) -> Cluster | None: ...
    async def create(self, cluster: Cluster) -> Cluster: ...
    async def update_centroid(self, cluster_id: UUID, new_member: np.ndarray) -> None: ...
```

Services depend on repositories, not on SQLAlchemy directly. This makes testing trivial.

### 11.5 Rules engine

```python
class AlertRule(ABC):
    @abstractmethod
    async def evaluate(self, ctx: EvaluationContext) -> AlertOutcome: ...

class ThresholdRule(AlertRule):
    def __init__(self, config: ThresholdConfig): ...
    async def evaluate(self, ctx):
        count = await ctx.log_repo.count_matching(
            app_id=self.app_id,
            filters=self.config.filters,
            window=self.config.window,
        )
        if count > self.config.threshold:
            return AlertOutcome.fire(
                payload={"count": count, "threshold": self.config.threshold},
                sample_logs=await ctx.log_repo.sample_matching(..., limit=5),
            )
        return AlertOutcome.no_fire()

class NoveltyRule(AlertRule):
    async def evaluate(self, ctx):
        new_clusters = await ctx.cluster_repo.find_created_after(
            app_id=self.app_id,
            since=ctx.window_start,
        )
        if new_clusters:
            return AlertOutcome.fire(
                payload={"new_clusters": [c.id for c in new_clusters]},
                sample_logs=[c.representative_message for c in new_clusters],
            )
        return AlertOutcome.no_fire()
```

The evaluator iterates enabled rules and dispatches each to a Celery task. Cooldowns are enforced before evaluation.

### 11.6 Notification service

```python
class Notifier(ABC):
    @abstractmethod
    async def send(self, alert: AlertEvent) -> NotificationResult: ...

class SlackNotifier(Notifier):
    def __init__(self, webhook_url: str): ...
    async def send(self, alert):
        message = self._format(alert)
        async with httpx.AsyncClient() as client:
            response = await client.post(self.webhook_url, json=message)
            response.raise_for_status()
        return NotificationResult.success()
```

`NotifierFactory.from_channel(channel)` returns the right notifier. Sends are Celery tasks with `autoretry_for=(httpx.HTTPError,)`, `retry_backoff=True`, `max_retries=5`.

### 11.7 Clustering service

```python
class ClusteringService:
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self, model: SentenceTransformer, cluster_repo: ClusterRepository):
        self.model = model
        self.cluster_repo = cluster_repo

    async def assign(self, app_id: UUID, message: str) -> tuple[UUID, bool]:
        normalized = self._normalize(message)
        embedding = self.model.encode(normalized, normalize_embeddings=True)
        nearest = await self.cluster_repo.find_nearest(app_id, embedding)
        if nearest and nearest.similarity > self.SIMILARITY_THRESHOLD:
            await self.cluster_repo.update_centroid(nearest.id, embedding)
            return nearest.id, False
        new_cluster = await self.cluster_repo.create(Cluster(
            application_id=app_id,
            centroid=embedding,
            representative_message=message,
        ))
        return new_cluster.id, True  # second value = is_new

    def _normalize(self, message: str) -> str:
        # Replace UUIDs, numbers, timestamps with placeholders
        msg = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
                    '<UUID>', message)
        msg = re.sub(r'\b\d+(\.\d+)?\b', '<NUM>', msg)
        msg = re.sub(r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S*\b', '<TIMESTAMP>', msg)
        return msg.lower()
```

The model is loaded once per worker process (initialization cost ~1s, then ~5ms per inference on CPU).

---

## 12. Alert Rules — Configuration Examples

### Threshold rule

```json
{
  "name": "Payment error spike",
  "rule_type": "threshold",
  "config": {
    "filters": {
      "level": ">=ERROR",
      "service": "payments"
    },
    "window_seconds": 300,
    "threshold": 10
  },
  "cooldown_seconds": 900,
  "channels": ["slack-eng-alerts"]
}
```

### Regex rule

```json
{
  "name": "Out of memory",
  "rule_type": "regex",
  "config": {
    "pattern": "OutOfMemory|cannot allocate memory",
    "case_sensitive": false
  }
}
```

### Novelty rule

```json
{
  "name": "New error pattern in production",
  "rule_type": "novelty",
  "config": {
    "min_severity": "WARNING"
  }
}
```

### Anomaly rule

```json
{
  "name": "Unusual error volume",
  "rule_type": "anomaly",
  "config": {
    "filters": {"level": ">=ERROR"},
    "baseline_hours": 24,
    "sensitivity_stddev": 3.0
  }
}
```

The anomaly rule maintains a per-hour rolling baseline (mean + stddev) and fires when the current window exceeds `mean + sensitivity_stddev * stddev`. NumPy is used for the calculations — concrete use of a JD-mentioned library.

---

## 13. Security

- **Passwords:** bcrypt with cost factor 12.
- **JWT:** access tokens 24h, refresh tokens 30d. Signed with HS256, secret in env var.
- **API keys:** Generated as 32 random bytes (base64-encoded), stored as SHA-256 hash. Shown to user only once at creation.
- **Multi-tenancy:** Enforced at the repository layer. Every query for tenant data takes `organization_id` as a required parameter. Postgres row-level security is documented as a future improvement, not implemented in v1.
- **Rate limiting:** Redis-backed sliding window. Per-API-key for ingestion, per-user for dashboard API.
- **Input validation:** Pydantic everywhere. Max payload sizes enforced at FastAPI level.
- **SQL injection:** All queries via SQLAlchemy parameterized. No raw string interpolation.
- **CORS:** Configurable allowed origins. Default deny.
- **Secrets:** All via env vars + pydantic-settings. `.env.example` committed, `.env` gitignored.

---

## 14. Observability (eat your own dogfood)

PulseMetrics monitors itself. The Docker Compose setup includes a sample app that emits logs to PulseMetrics, demonstrating the loop.

- **Structured logging** via structlog. Every log line is JSON.
- **Correlation IDs** propagated via FastAPI middleware. Every request gets an ID; it flows into Celery tasks via task headers.
- **Metrics endpoint** at `/metrics` exposing Prometheus-format counters: requests, ingestion rate, evaluation duration, embedding latency.
- **Health check** at `/health` that pings DB and Redis.

---

## 15. Performance & Scale Targets

Single-node, 4 vCPU, 8 GB RAM:

| Metric | Target |
|---|---|
| Ingestion throughput | 1,000+ entries/sec sustained |
| Search latency p95 | <500ms over 24h window, 10M logs |
| Rule evaluation latency | <5s for 1000 enabled rules |
| Embedding latency | <10ms per message |
| End-to-end (log arrival → alert) | <30s |

**Bottlenecks and mitigations:**

| Bottleneck | Mitigation |
|---|---|
| Embedding model on the request path | Move to Celery worker, batch process |
| Vector search over millions of clusters | HNSW index (sub-linear), cluster pruning |
| `logs` table grows unbounded | Monthly partitioning + retention job |
| Full-text search on huge windows | tsvector GIN index + time-range pre-filter |
| Notification fan-out | Celery task per channel, parallel |

---

## 16. Deployment

### Docker Compose

Services:
- `api` — FastAPI app
- `worker` — Celery worker (1 replica in dev, scale horizontally in prod)
- `beat` — Celery beat scheduler (exactly 1)
- `postgres` — Postgres 16 with pgvector extension
- `redis` — Redis 7

Volumes:
- `postgres_data`
- `model_cache` (sentence-transformers downloads on first start)

Environment file:
```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://redis:6379/0
JWT_SECRET=...
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LOG_LEVEL=INFO
DEFAULT_RETENTION_DAYS=30
```

### Production deployment

- Single VM (4 vCPU, 8 GB, 100 GB SSD) running `docker compose up`.
- Caddy or Traefik in front for HTTPS.
- Daily Postgres backup via `pg_dump` cron.

Documented but not implemented in scope: Kubernetes manifests, Postgres HA, horizontal Celery scaling.

---

## 17. Testing Strategy

### Unit tests
- Every parser class with sample inputs.
- Every rule class with synthetic log data.
- Every notifier with httpx mock.
- The clustering normalizer and similarity logic.

### Integration tests
- Use `testcontainers` to spin real Postgres + Redis.
- End-to-end: ingest → process → search → rule evaluation → alert event.
- Multi-tenancy isolation tests.

### Load tests
- A `scripts/load_test.py` using `httpx` async to push 1000+ logs/sec.
- Record latency distribution with NumPy, plot with matplotlib.
- Result lives in the README.

### Targets
- `pytest` runs in <2 minutes locally.
- `mypy --strict app/` is clean.
- `ruff check` is clean.
- GitHub Actions runs all of the above on every PR.

---

## 18. Five-Day Build Plan

### Day 1 — Foundation
- Repo scaffold, pyproject.toml, ruff, mypy, pytest configs.
- Docker Compose with all 5 services starting clean.
- FastAPI hello-world.
- Postgres schema + Alembic initial migration (organizations, users, applications).
- JWT auth: register, login, dependency for protected endpoints.
- Health endpoint that actually checks DB and Redis.

**End-of-day:** `docker compose up` works. Can register a user and log in via curl.

### Day 2 — Ingestion + Storage
- Logs table with monthly partitioning.
- Ingestion endpoint with API key auth.
- Celery worker that drains the raw_logs queue.
- All four parser classes with tests.
- LogRepository with bulk insert + basic search.
- The agent CLI (subprocess-based tailing, batching, shipping).

**End-of-day:** Can run the agent against a sample log file and see entries in Postgres.

### Day 3 — Clustering + Search
- pgvector extension, log_clusters table.
- Embedding model loaded in worker.
- ClusteringService with normalize → embed → find nearest → assign/create.
- Search API with filters, full-text, cluster scope, pagination.
- Clusters API.

**End-of-day:** Logs are clustered. A novel log creates a new cluster. Search returns results filtered by cluster.

### Day 4 — Rules + Notifications + Analytics
- All five rule classes with tests.
- Celery beat schedule for rule evaluation.
- Cooldown enforcement.
- All four notifier classes.
- Rule → channel binding.
- Analytics endpoints with matplotlib PNG generation.
- Anomaly rule using NumPy for statistical baseline.

**End-of-day:** A rule fires, a Slack message arrives. The analytics endpoint returns a real PNG.

### Day 5 — Tests, polish, docs, deploy
- Integration tests with testcontainers.
- Load test script + results.
- README with architecture diagram, run instructions, design decisions, demo gif.
- Deploy to a Render/Railway/Fly.io instance.
- Record a 2-minute demo video.
- Push to GitHub with a clean commit history.

### Cut lines (if time crunched)

In order of what to drop first:
1. Anomaly rule (keep the simpler ones).
2. Dashboard UI (API + curl + Postman collection is fine).
3. Webhook notifier (Slack + console are enough).
4. Load test (have the script ready but don't sweat the chart).

**Never cut:** clustering, novelty rule, OOP class hierarchies, tests, README. Those are the differentiators.

---

## 19. Future Roadmap (v2 — for the interview "what's next" question)

1. **Horizontal scale.** Sharding logs by application across multiple Postgres instances; Redis Streams instead of in-process queue.
2. **Multi-region.** Read replicas, cross-region replication.
3. **Distributed tracing.** Ingest OpenTelemetry spans, link to logs via trace ID.
4. **Custom metrics.** First-class numeric metrics alongside logs.
5. **Smarter clustering.** Incremental online clustering (e.g., DBSCAN variants), cluster splitting/merging.
6. **LLM-generated alert summaries.** When an alert fires with 100 logs, an LLM writes a one-paragraph summary. This is the *right* use of an LLM — expensive per-event, valuable, not on the hot path.
7. **Browser SDK.** JavaScript SDK for shipping browser-side errors.
8. **RBAC.** Granular roles beyond admin/member.
9. **Audit log.** Who created/modified rules, when.
10. **Saved searches and shared dashboards.**

---

## 20. Interview Talking Points

What to lead with when an interviewer asks about this project:

### The 60-second pitch
"PulseMetrics is a log monitoring service I built to learn production Python engineering. It ingests logs from any source, stores them in Postgres with a partitioning strategy, evaluates configurable alert rules in Celery, and notifies users via Slack or email. The differentiated feature is semantic log clustering — it embeds each log message with a sentence transformer, finds the nearest existing cluster via pgvector, and creates new clusters for novel messages. That lets you alert on patterns you've never seen before, which is a class of error that traditional rule-based monitoring misses entirely."

### Technical decisions to be ready to defend

| Decision | The defense |
|---|---|
| Postgres for vectors instead of Pinecone/Weaviate | One fewer service. Vector search is a feature of Postgres now via pgvector. At my scale (millions of vectors, not billions) it is more than adequate. |
| Celery instead of asyncio background tasks | Durability. If the API process dies mid-task, Celery retries. asyncio background tasks die with the process. |
| Sentence-transformers locally instead of OpenAI embeddings | Cost and latency. Embedding 1000 logs/sec via OpenAI is $$$. Local inference is 5ms and free. |
| Monthly partitioning on logs | Retention drops via `DROP PARTITION` is O(1). Without partitioning, deletes are expensive and cause bloat. |
| Repository pattern | Decouples services from SQLAlchemy. Made testing 10x easier — I can test business logic with a fake repo. |
| matplotlib for charts instead of a JS library | Server-rendered means the API is the only public surface. Charts work from curl, in emails, in PDF reports. |

### Tradeoffs to acknowledge

- "Single-node architecture is a real limitation. I documented the path to horizontal scale but didn't implement it — that would be the first thing I'd do for production."
- "The clustering threshold (0.85) is hand-tuned. In production I'd want a feedback loop where users can mark clusters as too coarse or too fine and the system adapts."
- "I made the dashboard minimal on purpose. A real product needs a much better UX, and I'd want to involve a designer."
- "I don't handle backpressure on the ingestion path. If Redis fills up, the API will start failing. A production version needs a proper queue with disk overflow."

### Questions to ask the interviewer

- "How does your team handle observability for the Python services?"
- "What's the team's approach to async — pure asyncio, Celery, something else?"
- "How do you balance build-vs-buy decisions for infrastructure tools?"

---

## 21. Repository Structure

```
pulsemetrics/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # auth dependencies
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── applications.py
│   │       ├── ingestion.py
│   │       ├── search.py
│   │       ├── clusters.py
│   │       ├── rules.py
│   │       ├── channels.py
│   │       ├── alerts.py
│   │       └── analytics.py
│   ├── core/
│   │   ├── config.py               # pydantic-settings
│   │   ├── logging.py              # structlog setup
│   │   ├── security.py             # JWT, bcrypt, API keys
│   │   └── exceptions.py           # custom exception hierarchy
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy declarative base
│   │   ├── session.py              # async engine, session factory
│   │   └── models/
│   │       ├── organization.py
│   │       ├── user.py
│   │       ├── application.py
│   │       ├── log.py
│   │       ├── cluster.py
│   │       ├── rule.py
│   │       └── alert.py
│   ├── repositories/
│   │   ├── base.py
│   │   ├── log_repo.py
│   │   ├── cluster_repo.py
│   │   └── ...
│   ├── parsers/
│   │   ├── base.py                 # abstract LogParser
│   │   ├── json_parser.py
│   │   ├── syslog_parser.py
│   │   ├── regex_parser.py
│   │   ├── plaintext_parser.py
│   │   └── factory.py
│   ├── rules/
│   │   ├── base.py                 # abstract AlertRule
│   │   ├── threshold.py
│   │   ├── regex.py
│   │   ├── novelty.py
│   │   ├── rate_of_change.py
│   │   ├── anomaly.py
│   │   └── factory.py
│   ├── notifiers/
│   │   ├── base.py                 # abstract Notifier
│   │   ├── slack.py
│   │   ├── email.py
│   │   ├── webhook.py
│   │   ├── console.py
│   │   └── factory.py
│   ├── services/
│   │   ├── clustering.py
│   │   ├── ingestion.py
│   │   ├── search.py
│   │   ├── rule_evaluator.py
│   │   └── analytics.py
│   ├── tasks/
│   │   ├── celery_app.py
│   │   ├── ingestion_tasks.py
│   │   ├── rule_tasks.py
│   │   ├── notification_tasks.py
│   │   └── maintenance_tasks.py    # partition mgmt, retention
│   └── schemas/                    # Pydantic models
│       ├── auth.py
│       ├── log.py
│       ├── rule.py
│       └── ...
├── agent/
│   ├── pyproject.toml              # separate package
│   ├── pulsemetrics_agent/
│   │   ├── __init__.py
│   │   ├── cli.py                  # argparse entry
│   │   ├── tailer.py               # subprocess tail -F
│   │   ├── batcher.py
│   │   ├── shipper.py
│   │   └── buffer.py
│   └── tests/
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py                 # testcontainers fixtures
│   ├── unit/
│   ├── integration/
│   └── load/
├── scripts/
│   ├── seed_data.py
│   ├── load_test.py
│   └── partition_check.py
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.agent
│   └── docker-compose.yml
├── docs/
│   ├── PRD.md                      # this document
│   ├── ARCHITECTURE.md
│   └── images/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

---

## Closing

This document is the single source of truth for the v1 build. When in doubt, re-read it. When tempted to add a feature not listed here, write it down for v2 and move on. The risk on a 5-day project is not under-scoping — it's over-scoping and shipping nothing.

The point of this project is not to replace Datadog. It is to demonstrate that you can:

1. Design a non-trivial system end to end.
2. Make defensible architectural choices and articulate the tradeoffs.
3. Write Python that uses the language well — type hints, dataclasses, async, OOP that earns its place.
4. Use PostgreSQL beyond CRUD — partitioning, vector search, full-text search.
5. Ship a thing that actually works, with tests, docs, and a deploy.

That is what the JD is asking for.
