# User Activity Feed — Spec

Status: Draft
Priority: P1

Owner: Marcus (backend)
QA owner: Dana

Overview
--------
Introduce a per-user activity feed that surfaces events relevant to a user. Reads must be low-latency (p99 < 200ms). Heavy/expensive feeds are precomputed in background; hot users cached in Redis.

Acceptance Criteria (highlights)
-------------------------------
- Endpoints:
  - GET /api/v1/users/{id}/feed (cursor pagination)
  - POST /api/v1/users/{id}/feed/mark-read (body: list of item ids or cursor)
- Filters: type, since_cursor, unread_only, page_size (max 100)
- Auth: Bearer token. Users may only read their own feed. Admins can read any user's feed.
- Response items: id, type, payload (JSON), created_at (ISO8601), read (boolean)
- Perf SLO: reads p99 < 200ms. Cache hot users in Redis (TTL 5m). Precompute heavy feeds via Celery.
- DB: events table (user_id, type, payload jsonb, created_at, read boolean). Indexes on (user_id, created_at DESC) and partial index for unread.
- Pagination: cursor only. Cursor is opaque base64 of "created_at: id". No offset/limit-based pagination.
- Edge cases: deleted users, duplicate events, payload size limit 10KB

API: GET /api/v1/users/{id}/feed
--------------------------------
Query params:
- cursor (optional) — opaque cursor from previous response
- page_size (optional, default 25, max 100)
- type (optional, repeated or comma-separated)
- unread_only (optional, boolean)

Auth: Authorization: Bearer <token>
Authorization: user_id in token must match {id} OR user role == admin

Response (200):
{
  "items": [
    {"id": "evt_123", "type":"message", "payload": {...}, "created_at":"2026-03-01T12:00:00Z", "read": false}
  ],
  "next_cursor": "<base64>"  // null if no more
}

Notes:
- page_size controls returned item count; server enforces max 100.
- next_cursor encodes the last item's created_at and id to avoid duplicates.

API: POST /api/v1/users/{id}/feed/mark-read
-------------------------------------------
Body (JSON):
- item_ids: ["evt_123", ...] OR
- cursor: "<cursor>" and mark_all_up_to_cursor: true

Response: 200 {"marked": N}

DB Schema (proposal)
--------------------
SQL (example):

CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE,
  user_id BIGINT NOT NULL,
  type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  read BOOLEAN NOT NULL DEFAULT false
);

Indexes:
- CREATE INDEX idx_events_user_created_desc ON events (user_id, created_at DESC);
- CREATE INDEX idx_events_user_unread ON events (user_id) WHERE read = false;  -- partial index
- Consider a composite index on (user_id, type, created_at DESC) if type filtering is hot.

Notes on schema:
- Schema-first approach: events table + jsonb payload to support flexible event types.
- event_id (text) is a stable external id (UUID or generated string) used in APIs.

Pagination details
------------------
Cursor format (opaque to clients): base64("<created_at_iso>|<event_id>")
- Sorting: primary sort by created_at DESC, secondary by event_id DESC to make deterministic order when created_at ties.
- When querying older pages: SELECT ... WHERE (created_at, id) < (cursor_created_at, cursor_id) ORDER BY created_at DESC, id DESC LIMIT page_size
- Avoid OFFSET.

Cache & Performance
-------------------
- Perf SLO: reads p99 < 200ms.
- Cache hot users' feeds (precomputed first N pages) in Redis with TTL 5m. Keys per user+filter signature.
- Background precompute: Celery tasks to build feeds for heavy users and warm Redis.
- Use read-replica(s) for scaling reads; write path goes to primary.

Background processing
---------------------
- On event creation: write to events table. For light feeds, no precompute needed; reads will query DB (or Redis fallback). For heavy feeds or aggregated views, queue Celery job to materialize view in Redis.
- Dedup: producer must ensure idempotency; use event_id unique constraint to avoid duplicates.

Limits & Validation
-------------------
- payload size limit: 10KB (reject with 413 if exceeded).
- Validate payload is JSON and only allowed fields depending on type (app-level validation).
- Rate-limit marking-read endpoints to prevent abuse.

Security & Auth
---------------
- Token must be validated; ensure token's user_id matches path or token has admin scope.
- Sanitize/validate payload before storing; never store raw user-supplied HTML.
- RBAC: admin role allowed to read any user feed.

Edge cases
----------
- Deleted users: if user is soft-deleted, allow feed reads if requester is that user or admin. If hard-deleted, return 404.
- Duplicate events: rely on unique event_id to dedupe; log and ignore duplicates.
- Clock skew: created_at should be normalized to server time; cursor comparisons use server timezone.
- Partial writes: on failure to write, ensure no inconsistent precompute artifacts remain.

Operational & Monitoring
------------------------
- Metrics: feed_read_latency_ms (p50/p95/p99), cache_hit_ratio, precompute_task_duration, events_ingested_count
- Alerts: p99 > 200ms sustained for 5m; cache_hit_ratio < 50% for hot users

Key decisions (documented)
--------------------------
- Schema-first: single events table + JSONB payload for flexibility and schema evolution.
- Cursor pagination (opaque base64 of created_at+id) to provide stable paging and avoid OFFSET.
- Cache hot users in Redis (TTL 5m) + background precompute (Celery) for heavy feeds to meet SLO.
- Use read-replica(s) to scale read traffic.

Open questions / TODOs
---------------------
- Exact TTL and number of precomputed pages to store per user (suggest 2 pages).
- Retention policy for events table (e.g., 90 days) — cost vs compliance tradeoff.
- Authorization scope naming (feed:read, feed:admin)

Acceptance tests (outline for QA)
---------------------------------
1. Happy path: return page of events with valid cursor
2. Pagination: follow next_cursor to end, ensure no duplicates/missing
3. Auth: user can read own feed; non-admin cannot read others
4. Unread filtering: unread_only true returns only unread items; marking read updates read flag
5. Performance: mock hot user cache hit and miss; measure latency endpoint p99 < 200ms under test harness
6. Edge cases: deleted user behavior, payload >10KB returns 413, duplicate event_id rejected

Files / Artifacts
-----------------
- Spec: output/specs/user_activity_feed.md
- DB migration: output/code/migrations/xxxx_create_events_table.sql (TBD by Marcus)

Owners / Next steps
-------------------
- Marcus (#ai-backend): implement DB schema + migration, create branch, implement endpoints
- Kevin (#ai-frontend): implement integration using contract & example responses below
- Dana (#ai-qa): write tests for pagination, auth, unread edge cases
- Taylor (#ai-tech-lead): architecture review

Example request/response (frontend-ready)
-----------------------------------------
GET /api/v1/users/123/feed?cursor=&page_size=25&unread_only=true
Authorization: Bearer <token>

200 OK
{
  "items": [
    {"id":"evt_1","type":"like","payload":{"post_id":456},"created_at":"2026-03-01T12:00:00Z","read":false}
  ],
  "next_cursor":"YmFzZV9leGFtcGxl"  
}


