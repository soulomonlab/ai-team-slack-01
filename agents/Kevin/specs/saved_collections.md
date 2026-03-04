Saved Collections — Spec

Overview
- Feature: Saved Collections (bookmarks + folders, tags, offline sync)
- Goals: intuitive UX, offline-first, scalable per-user (thousands+ items)
- Priority: P1

Acceptance criteria
- Full CRUD in UI for collections and items
- Tagging, folders (collection hierarchy), search, pagination
- Offline create/edit + background sync; conflict policy = last-writer-wins (LWW) with server-side merge hooks
- API endpoints + data model documented below
- Performance target: list queries <200ms for 1,000 items/user (indexes + caching)

Key technical decisions (confirmed)
- API: REST (FastAPI)
- DB: Postgres; user-scoped tables; indexes on (user_id), (user_id, last_modified DESC), full-text for search
- Auth: JWT (Bearer)
- Offline: service worker + Workbox background sync + local IndexedDB (idb). Client queues operations while offline.
- Conflict resolution: LWW (client sends client_modified_at; server compares server_modified_at; server wins when newer; server emits merge hooks for complex merges)
- Pagination: cursor-based (recommended) for stable performance; offset supported for admin/debug
- Rate limiting: per-user (e.g., 100 req/min) and per-endpoint throttling
- Caching: Redis for list endpoints with short TTL and write-time invalidation

Data model (recommended tables)

collections
- id: uuid (PK)
- user_id: uuid (FK) -- indexed
- parent_id: uuid | null (for folder hierarchy)
- name: text
- description: text
- thumbnail_url: text | null
- metadata: jsonb
- item_count: int (denormalized)
- last_modified: timestamptz -- indexed (user_id, last_modified DESC)
- created_at: timestamptz

collection_items
- id: uuid (PK)
- collection_id: uuid (FK) -- indexed
- user_id: uuid -- indexed
- title: text
- url: text
- content_preview: text
- metadata: jsonb
- position: int (optional ordering)
- last_modified: timestamptz -- indexed
- created_at: timestamptz

tags
- id: uuid
- user_id: uuid -- indexed
- name: text (unique per user)

item_tags (join)
- item_id, tag_id

Indexes & performance notes
- Indexes: (user_id), (user_id, last_modified DESC), (collection_id) on items
- Full-text index (GIN) on title + content_preview for search
- Composite indexes for common queries (user_id, tag_id)
- Denormalized counters (item_count) to avoid heavy counts
- Use LIMIT + cursor for pagination to keep queries <200ms at 1k items. Test and tune.

API endpoints (auth: Bearer JWT)

Collection CRUD
- GET /api/v1/collections?cursor=<cursor>&limit=50&parent_id=<id>&q=<query>&tag=<tag>
  - cursor-based pagination: returns { items: [...], next_cursor: "...", has_more: bool }
  - supports filtering by parent_id, search q (fts), tag
- POST /api/v1/collections
  - body: { name, parent_id?, description?, metadata? }
  - returns 201 + created collection
- GET /api/v1/collections/{collection_id}
- PATCH /api/v1/collections/{collection_id}
  - partial update; client MAY include client_modified_at for sync
- DELETE /api/v1/collections/{collection_id}
  - soft-delete recommended (deleted_at) for undo/sync safety

Items CRUD
- GET /api/v1/collections/{collection_id}/items?cursor=&limit=50&q=&tag=
- POST /api/v1/collections/{collection_id}/items
  - body: { title, url, content_preview?, metadata?, tags?: ["t1"], client_id?: string, client_modified_at?: timestamp }
  - client_id: temporary local id (UUID) used when offline; server returns canonical id mapping
- PATCH /api/v1/collections/{collection_id}/items/{item_id}
- DELETE /api/v1/collections/{collection_id}/items/{item_id}

Tags
- GET /api/v1/tags?user_scope=true
- POST /api/v1/tags
- DELETE /api/v1/tags/{id}

Search
- GET /api/v1/search/collections?q=&cursor=&limit=50&scope=(user|all)
  - returns combined results across collections/items; use FTS

Sync & Offline behavior
- Client stores canonical objects in IndexedDB and a pending-ops queue
- Each object has: id (uuid or client-generated UUID), client_modified_at (ISO), last_synced_at, sync_state (synced|pending|conflict)
- Offline create: client generates UUID (prefixed client:) and enqueues POST
- Background sync: Workbox background sync attempts to flush queue; on network restore, sync worker POSTs queued ops
- Conflict detection: server compares incoming client_modified_at with stored last_modified; if server.last_modified > client_modified_at → server considers client stale
- Conflict resolution policy: LWW
  - Server authoritative timestamp wins. Server accepts incoming write only if client_modified_at >= server.last_modified OR server merges fields (simple merge hook) and returns merged object
  - Server returns 409 with current server object and suggested merged object when non-trivial conflict occurs
  - Client shows non-blocking UI indicator for conflicts and allows user to resolve manually if needed
- ID mapping: server returns { client_id, id } to map temporary IDs

Error handling & retry
- Idempotency: clients should send an idempotency key for create operations when retrying in background sync
- Retries: exponential backoff for transient 5xx errors

Security & rate limits
- JWT auth for all endpoints
- Per-user rate limit: default 60-120 req/min
- Throttle heavy endpoints (search) and require pagination

Monitoring & metrics
- Track: list query latency, cache hit rate, sync queue size per user, conflict rate
- Alert: list latency >200ms at 95th percentile for 1k items/user

API examples (abridged)
GET /api/v1/collections?limit=2
Response:
{ "items": [ { "id":"...", "name":"Read Later", "item_count": 42, "last_modified":"2025-10-01T12:34:56Z" } ], "next_cursor": "abc123", "has_more": true }

POST /api/v1/collections
Request: { "name":"Favorites", "parent_id": null }
Response 201: { "id":"uuid", "name":"Favorites", "parent_id": null }

Sync create item (client sends):
POST /api/v1/collections/{cid}/items
Body: { "client_id":"client:tmp-uuid", "title":"Article", "url":"https://...", "client_modified_at":"2026-03-01T12:00:00Z" }
Response 201: { "id":"uuid", "client_id":"client:tmp-uuid", "last_modified":"2026-03-01T12:00:01Z" }

Open questions / frontend asks for #ai-backend
- Cursor format: opaque base64 token or stable cursor (last_modified + id)? Recommend opaque token.
- Should endpoints return total_count? For perf, return optional approximate_count endpoint: GET /api/v1/collections/count
- Rate-limit numbers per endpoint (search vs list)

Frontend responsibilities (#ai-frontend)
- UI components: Collection list, Collection detail, Item card, Tag-picker, Search bar
- Offline: implement service worker + Workbox background sync, IndexedDB schema, conflict UI
- Tests: accessibility, offline flows, sync reconciliation

Backend responsibilities (#ai-backend)
- API endpoints, DB schema, indexes, caching, rate-limits
- Sync hooks + id mapping for client-created IDs
- Implement 409 conflict responses with merge suggestions

Deliverables & timeline
- Spec (this file) — complete
- API contract/Swagger from backend (Marcus) — 3 days
- Frontend prototype + SW integration — 5 days
- End-to-end QA & perf tests — 7 days

Next steps (actions)
- Create GitHub issue labeled [epic, frontend, backend, P1] (branch/PR created) and assign epics:
  - #ai-backend (Marcus): API + DB
  - #ai-frontend (Kevin): UI + Workbox

Files
- output/specs/saved_collections.md (this file)

