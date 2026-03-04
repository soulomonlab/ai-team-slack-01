# User Activity Feed - Spec

Status: Draft
Priority: P1
Owner: Marcus (backend)

Summary

Provide a per-user activity feed (read + mark-read) with cursor-based pagination, filters, and strong performance SLOs. Designed for realtime-ish UX with read-replicas, Redis caching for hot users, and background precomputation for heavy/expensive feeds.

Acceptance highlights

- Endpoints:
  - GET /api/v1/users/{id}/feed  (cursor pagination)
  - POST /api/v1/users/{id}/feed/mark-read  (body: cursor or list of item ids)
- Filters: type (enum list), since_cursor, unread_only (bool), page_size (default 20, max 100)
- Auth: Bearer. Users may only read their own feed; admins may read any user's feed.
- Response: items[] with { id, type, payload (JSON), created_at, read (bool) }
- Perf SLO: reads p99 < 200ms. Cache hot users in Redis (TTL 5m). Precompute heavy feeds via Celery tasks.
- DB: events table (user_id, type, payload jsonb, created_at, read boolean) + indexes on (user_id, created_at DESC), partial index for unread.
- Pagination: cursor (opaque base64 of created_at + id) — no offset.
- Edge cases: deleted users, duplicate events, payload size limit 10KB.

API contract (high level)

GET /api/v1/users/{id}/feed
- Auth: Bearer token
- Query params: cursor (opaque), page_size (int, <=100), type (csv of types), unread_only (bool), since_cursor
- Response 200:
  {
    "items": [
      {"id": "uuid", "type": "comment|like|follow|system", "payload": {...}, "created_at": "ISO8601", "read": false}
    ],
    "next_cursor": "opaque or null",
    "prev_cursor": "opaque or null",
    "total_count": null  // not required; avoid COUNT for large tables
  }

POST /api/v1/users/{id}/feed/mark-read
- Body: { "cursors": ["opaque"], "ids": ["uuid"] } (either cursors OR ids)
- Response 204 No Content on success

Cursor format

- Opaque cursor = base64("{created_at ISO8601}|{id}")
- Comparison semantics: (created_at DESC, id DESC) ordering. Server decodes and queries: WHERE (created_at,id) < (cursor_created_at, cursor_id) ORDER BY created_at DESC, id DESC LIMIT page_size
- since_cursor: return items newer than the provided cursor (i.e. > (created_at,id))

DB schema (recommended)

CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read BOOLEAN NOT NULL DEFAULT false
);

-- Indexes
CREATE INDEX idx_events_user_created_desc ON events (user_id, created_at DESC, id DESC);
CREATE INDEX idx_events_user_unread ON events (user_id) WHERE (read = false);

Notes:
- payload limited to 10KB (enforce in application layer; reject >10KB with 413)
- Consider partitioning (by user_id hash or time) if volume grows

Caching & precompute

- Redis: cache GET results for hot users (key includes user_id + filters + cursor page identifier), TTL 5m. Cache must be invalidated on mark-read and on new event insertion for that user (or use short TTL to avoid complex invalidation).
- Precompute: use Celery to precompute heavy feeds (e.g. aggregated system feeds or feeds that join many tables). Store precomputed pages in Redis or a materialized table.

Scaling & architecture

- Read replicas: direct read traffic to read-replicas; writes go to primary.
- Use connection pool and pagination queries to avoid large scans.
- Monitor p99 latency and cache hit rate; auto-scale read replicas when necessary.

Auth & Authorization

- Bearer token required. Token must identify the requesting user.
- Rule: if requesting_user.id != {id} AND not is_admin(requesting_user) => 403
- Rate-limit endpoint per user to protect DB.

Edge cases

- Deleted users: if user is deleted, reads should return 404. Mark-read attempts return 404.
- Duplicate events: enforce deduping at producer level where possible. Optionally add a dedupe_key column with unique constraint for idempotency of event ingestion.
- Payload size: enforce 10KB limit.
- Missing cursor / malformed cursor: return 400.

Testing & QA

- Functional: pagination, filters, unread_only, since_cursor, marking read
- Auth: access denied for non-owner and allowed for admin
- Edge: deleted users, malformed cursors, oversized payloads
- Performance: load test reads to validate p99 < 200ms (with cache warm)

Migration plan

1. Add events table + indexes
2. Backfill (if needed) from existing event sources
3. Implement API + mark-read
4. Add Redis caching and Celery precompute
5. Monitor and iterate

Key decisions

- Schema-first: single events table with JSONB payload to keep schema flexible
- Cursor pagination (opaque base64 of created_at+id) — no offset
- Redis cache for hot users (5m TTL) + background precompute (Celery)
- Use read-replicas for scaling reads

Open questions / TODOs

- List of allowed 'type' enum values (Marcus)
- Mark-read semantics: mark-by-id vs mark-by-cursor range (decide API shape)
- Metrics to collect (per-endpoint latency, cache hit, mark-read errors)

Files produced

- output/specs/user_activity_feed.md (this file)

Request

- Marcus: please create a GitHub issue and start the DB migration branch. I'll follow up with frontend API contract + example request/response.

