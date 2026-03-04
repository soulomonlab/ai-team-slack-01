# Saved Collections — Spec

Status: Draft
Owner: Marcus (backend) — #ai-backend
Frontend owner: Kevin — #ai-frontend
Priority: P1

## Purpose
Provide users with a scalable, offline-first "Saved Collections" feature supporting bookmarks (items), folders (collections), tags, and sync. Must perform p99 < 200ms for listing 1000 items/user.

## Acceptance Criteria
- CRUD for collections and items available via REST API
- Tagging, folder organization, search, pagination
- Offline create/edit/sync with server; documented conflict policy
- API spec + data model included here
- Rate-limited endpoints; DB indexes and caching for performance

## High-level flows
- Create / edit / delete collection (folder) and items
- Tag/untag items and collections
- List collections and list items (keyset cursor pagination)
- Search by title, url, tags (server-side search via postgres trigram + index)
- Offline: client stores operations and syncs using /api/v1/saved/sync

## Key decisions
- API: REST (FastAPI)
- DB: Postgres; user-scoped tables with user_id indexes and last_modified
- Auth: JWT (Authorization: Bearer <token>)
- Pagination: keyset cursor (last_modified + id) for consistent p99 performance
- Offline conflict policy: last-writer-wins using client timestamp; server applies merge hooks for non-destructive merges. Sync endpoint returns per-item resolution metadata.
- Caching: Redis caching for list endpoints (TTL 60s), invalidated on writes
- Rate limiting: per-user token bucket (e.g., 100 req/min default)

## Data model (Postgres)
- users (existing)

- collections
  - id: UUID PK
  - user_id: UUID FK, indexed
  - title: TEXT
  - description: TEXT
  - parent_id: UUID NULL (for nested folders) — indexed
  - metadata: JSONB (ui positions, color, etc.)
  - created_at: timestamptz DEFAULT now()
  - last_modified: timestamptz DEFAULT now(), indexed (for keyset)
  - deleted: boolean DEFAULT false (soft delete)

Indexes:
  - ON collections (user_id, last_modified DESC, id DESC)
  - ON collections (user_id, parent_id)

- items
  - id: UUID PK
  - collection_id: UUID FK -> collections.id, indexed
  - user_id: UUID indexed
  - title: TEXT (indexed via trigram for search)
  - url: TEXT
  - data: JSONB (snapshot of bookmark: favicon, excerpt, attachments)
  - created_at, last_modified, deleted

Indexes:
  - ON items (user_id, last_modified DESC, id DESC)
  - ON items USING gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(url,''))) for full-text
  - pg_trgm index on title for ILIKE searches
  - ON items (collection_id)

- tags
  - id: UUID
  - user_id: UUID
  - name: TEXT
  - created_at
  - UNIQUE(user_id, lower(name))

- item_tags (many-to-many)
  - item_id, tag_id (PK item_id, tag_id)
  - created_at

- collection_tags (many-to-many)

Notes:
- Use soft-delete to support offline deletes and conflict resolution
- last_modified updated by DB trigger or application

## API: Overview
Base path: /api/v1/saved
Auth: Bearer JWT; server must validate token and set current_user_id
Error format (JSON): {"error": {"code": "string", "message": "string", "details": {}}}
Rate limit headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

API endpoints (summary):
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | /collections | Create collection | Bearer |
| GET  | /collections | List collections (keyset) | Bearer |
| GET  | /collections/{id} | Get collection | Bearer |
| PATCH| /collections/{id} | Update collection | Bearer |
| DELETE| /collections/{id} | Soft delete | Bearer |

| POST | /items | Create item | Bearer |
| GET  | /items | List items (filter by collection, tags, search) | Bearer |
| GET  | /items/{id} | Get item | Bearer |
| PATCH| /items/{id} | Update item | Bearer |
| DELETE| /items/{id} | Soft delete | Bearer |

| POST | /tags | Create tag | Bearer |
| GET  | /tags | List tags | Bearer |

| POST | /sync | Sync client changes (batch) | Bearer |

Detailed endpoints with example request/response (examples abbreviated):

- POST /api/v1/saved/collections
Request:
{
  "title": "Read Later",
  "description": "Articles",
  "parent_id": null,
  "metadata": {"color":"#FF0"}
}
Response 201:
{
  "id": "uuid",
  "user_id": "...",
  "title": "Read Later",
  "description": "Articles",
  "parent_id": null,
  "metadata": {...},
  "created_at": "...",
  "last_modified": "..."
}

- GET /api/v1/saved/items?collection_id=<>&cursor=<>&limit=50&search=term&tags=tag1,tag2
Response 200:
{
  "items": [ {id, title, url, data, last_modified, deleted}, ... ],
  "next_cursor": "base64(cursor)"
}
Notes: cursor encodes (last_modified, id) of the last item returned. Provide stable ordering: last_modified DESC, id DESC

- PATCH /api/v1/saved/items/{id}
Body: {"title": "new", "data": {...}, "last_modified": "2024-01-01T...Z"}
Server will compare last_modified to detect concurrent edits. If client's last_modified < server's, server performs LWW: server keeps latest; but server can accept client update if client's timestamp is newer.

- POST /api/v1/saved/sync
Purpose: Offline client syncs batched operations and receives server updates.
Request:
{
  "last_sync": "2024-01-01T...Z", // optional
  "operations": [
    {"op_id":"uuid-local","type":"create_item","payload":{...},"client_modified":"..."},
    {"op_id":"uuid-local","type":"update_item","id":"...","payload":{...},"client_modified":"..."},
    {"op_id":"uuid-local","type":"delete_item","id":"...","client_modified":"..."}
  ]
}
Response:
{
  "applied": [ {"op_id":"...","status":"applied","server_id":"...","server_last_modified":"..."}, ... ],
  "conflicts": [ {"op_id":"...","resolution":"server_kept","server_value":{...},"client_value":{...}} ],
  "changes": { "items": [ ... server-side changes since last_sync ...], "collections": [...]} ,
  "new_sync_token": "..."
}
Sync rules:
- For non-conflicting ops, apply in order and return applied mapping.
- If both client and server modified same resource: use last-writer-wins by comparing client_modified vs server_last_modified. If client is newer -> apply client; else -> keep server and return conflict record.
- For merges that are safe (e.g., merging tags arrays), server may merge arrays and mark resolution=merged.

## Performance & scaling
- Target: list queries for 1000 items/user p99 < 200ms
- Use keyset pagination and indexes on (user_id, last_modified DESC, id DESC)
- Limit max page size (limit <= 200); default 50
- Use Redis caching for list endpoints. Cache keys: saved:list:items:{user_id}:{collection_id}:{cursor_hash}:{limit}:{filters_hash}
- Cache TTL: 60s; invalidate on mutations (writes) to user's saved content
- Use connection pooling and prepared statements; run EXPLAIN on heavy queries and add indexes if slow

## Security
- Authenticate all endpoints with JWT and verify user_id claim matches operations
- Validate ownership: any access to item/collection must check item.user_id == current_user_id
- Input validation and size limits (max metadata 64KB, max data JSONB 512KB)
- Prevent user enumeration by normalizing error messages

## Observability
- Metrics: request latency, DB query times, cache hit rate, items per user distribution
- Tracing: add span for DB queries and sync processing
- Logging: audit log for create/update/delete with user_id, op_id

## Migration notes
- Create tables with migrations (alembic)
- Backfill tags dedup logic if existing bookmarks present

## Offline & Client hints
- Clients should maintain operation queue with op_id and client_modified timestamps
- Use exponential backoff on sync failures; show local-only UI state
- Conflict UX: show last_updated and let user manually resolve if the server kept a different value

## Next steps / Tasks
- Backend: implement DB schema, REST endpoints, sync logic, caching, rate-limiting (#ai-backend — Marcus)
- Frontend: UI + service worker/workbox integration, offline storage, sync UI (#ai-frontend — Kevin)
- QA: test offline flows, conflict cases, performance at 1k items/user (#ai-qa — Dana)

Spec file path: output/specs/saved_collections.md
