# User Activity Feed — Spec

Priority: P1

Summary
- Provide per-user activity feeds with cursor-based pagination, read/unread semantics, server-side caching, and background precomputation for heavy feeds.

Endpoints (Acceptance)
- GET /api/v1/users/{id}/feed
  - Query params: cursor (opaque), since_cursor, type (string, multiple allowed), unread_only (bool), page_size (int, default 20, max 100)
  - Auth: Bearer token. User may only read their own feed unless admin.
  - Response: { items: [ { id, type, payload (JSON), created_at (ISO8601), read (bool) } ], next_cursor }
  - Pagination: cursor-based only. Cursor = base64(created_at + ":" + id) (opaque)
- POST /api/v1/users/{id}/feed/mark-read
  - Body: { cursor_start?, cursor_end?, event_ids?: [id], mark_all_before_cursor?: cursor }
  - Auth: Bearer token. Only the user or admin may mark read.
  - Response: { marked_count }

Filters & Params
- type: string or comma-separated list
- since_cursor: opaque cursor to filter > cursor
- unread_only: boolean
- page_size: integer, max 100

Auth & Authorization
- Bearer JWT (standard). Service validates user_id in token against path param.
- Admin role can read/modify any user's feed.

Response Schema
- item: { id: UUID, type: string, payload: JSON object (<= 10KB), created_at: ISO8601, read: boolean }
- All payloads stored as jsonb in DB. Reject writes >10KB.

Performance & Scaling
- Perf SLO: p99 < 200ms for read endpoints under production load.
- Cache: Redis for hot users with TTL 5m. Cache key per user + filters (type/unread_only/page_size).
- Precompute: Heavy feeds precomputed by Celery workers into Redis or materialized tables.
- Read-scaling: Use Postgres read-replicas for high read volume.

Database
- events table (Postgres):
  - id UUID PRIMARY KEY
  - user_id UUID NOT NULL
  - type VARCHAR NOT NULL
  - payload JSONB NOT NULL
  - created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
  - read BOOLEAN NOT NULL DEFAULT false
- Indexes:
  - CREATE INDEX ON events (user_id, created_at DESC);
  - Partial index for unread: CREATE INDEX ON events (user_id, created_at DESC) WHERE read = false;
  - Consider BRIN on created_at for very large tables.
- Write path: services write events; mark-read updates read boolean. Use lightweight updates; consider tombstone pattern if write amplification is a problem.

Pagination
- Cursor = opaque base64(created_at + ":" + id). Always query WHERE (created_at,id) < (cursor_created_at,cursor_id) ORDER BY created_at DESC, id DESC LIMIT page_size.
- No offset pagination.

Edge cases
- Deleted users: return 404 for read attempts. Admins can query historical data if allowed (or return 410 if permanently deleted). Document policy.
- Duplicate events: dedupe on write via idempotency key or unique constraint on external_event_id when available.
- Payload size limit: 10KB. Reject larger payloads with 413.

Operational
- Background jobs (Celery) to precompute feeds for heavy users and populate Redis.
- Monitoring: instrument p50/p95/p99, cache hit ratio, Celery lag, DB replication lag.
- Rollout: feature flag behind user_activity_feed; can opt-in subset of users.

Key Decisions
1. Schema-first: single events table + jsonb payload for flexibility.
2. Cursor pagination (opaque base64) — no offset to avoid performance pitfalls.
3. Redis caching for hot users (TTL 5m) + Celery precompute for heavy feeds.
4. Read-replica for scaling reads.

Acceptance Criteria (for QA)
- GET returns correct items with pagination and next_cursor.
- Filters (type, unread_only, since_cursor) work as specified.
- Auth enforced: users cannot access others' feeds unless admin.
- POST mark-read updates read status and is idempotent.
- Perf: p99 < 200ms for reads (cached/hot users); tests for cache TTL and precompute behavior.
- DB indexes exist and prevent full table scans for typical workloads.

Implementation notes
- Service: FastAPI endpoints under /api/v1/users/{id}/feed.
- Background worker: Celery + Redis broker and result backend (or Redis for cache + RabbitMQ for tasks as alternative).
- Pagination helper utilities: encode_cursor(created_at,id) / decode_cursor.
- Testing: unit tests for cursor logic; integration tests for end-to-end pagination + auth + mark-read.

Spec file: output/specs/user_activity_feed.md

