Title: Smart Search — Caching & Facet Plan

Goals
- Provide p99 < 150ms for /search/facets and /search responses for common queries.
- Keep facet counts accurate within an acceptable window (eventual consistency ok).
- Support high read QPS with low latency and scalable writes.

High-level design
1) Redis as read cache
   - Use Redis for:
     - Cached facet counts per filter combination (hash key per query fingerprint).
     - Suggestion autocomplete results (hot prefixes).
   - TTLs:
     - Facet counts: 5 minutes default (configurable); 1 minute for very high-traffic collections.
     - Suggests: 1 minute - prewarm on deployment or heavy prefixes.
   - Key design:
     - facets:<index>:<fingerprint>  (fingerprint = sha256 of normalized query + active filters)
     - suggest:<index>:<prefix>
   - Cache invalidation:
     - Time TTL primary.
     - On write events (create/update/delete), publish change via Redis pub/sub
       -> subscriber (Celery worker) invalidates affected keys or increments a "stale" flag.
     - For complex filter combos, we rely on TTL + background recompute. Immediate strict consistency not required.

2) Precomputed / batch-updated facet counts
   - For expensive/global facets (e.g., category counts across millions of rows), maintain materialized views in Postgres
     or a dedicated aggregation table updated by periodic Celery tasks (cron: 30s–5m depending on freshness need).
   - The task computes base counts and writes to Redis; read path prefers Redis.
   - Use Postgres indexes (btree on filter columns, partial indexes) and ANALYZE after large batch updates.

3) On-demand compute fallback
   - If cache miss and no precomputed data, compute facets in DB with optimized query and return response; async worker also writes result to Redis.
   - Use LIMIT/ORDER BY strategies and approximate counts for very large sets (use estimated counts when counts > threshold).

4) Search suggestions
   - Hot prefixes cached in Redis.
   - Cold prefixes hit DB/elastic: use trigram index in Postgres or external search (Elasticsearch/Opensearch).
   - Maintain a write-through pipeline to update suggestion index on content changes.

5) Pagination & cursor
   - Use cursor-based pagination for /search (opaque base64 cursor from last item key + sort values).
   - Ensure cached facets tied to the same cursor/key fingerprint when needed.

6) Monitoring & metrics
   - Metrics: cache hit ratio, facet compute latency, most expensive DB queries, Redis memory usage.
   - Alert on cache hit ratio < 70% or median facet latency > 200ms.

7) Capacity & ops
   - Redis sizing: start with 4GB for staging, 32GB for prod (estimate dependent on product catalog size).
   - Use Redis clusters for sharding if needed. Enable LRU eviction only for suggestion keys; facet keys should use TTL.

Implementation roadmap (short)
- [P0] Implement Redis cache layer and key fingerprinting in search service.
- [P0] Add Celery task to compute and populate facet counts periodically (configurable interval).
- [P1] Implement pub/sub invalidation on write events and lightweight invalidator worker.
- [P1] Add materialized views / aggregation tables for heavy facets.
- [P2] Integrate external search (ES/OS) for advanced suggestions if needed.

Open questions / decisions for stakeholders
- Max staleness SLA for facets (default proposal: 5 minutes).
- Use Postgres-only vs external search cluster for suggestions (tradeoff: infra vs latency/accuracy).

Files I'll create next (if approved)
- output/code/backend/search/cache.py (Redis helpers)
- output/code/backend/tasks/facets.py (Celery tasks)
- Alembic migration for aggregation table

Handoffs
- #ai-frontend: No API changes required to use cached facets; we will return a cache_ttl in /search/facets response header.
- #ai-devops: Need Redis + monitoring config. Please provision.
- #ai-qa: Prepare tests for cache consistency scenarios & cache miss fallback.

Decision log
- Use Redis TTL 5m + background recompute for facets (reason: speed + acceptable eventual consistency). 
- Cursor pagination + fingerprinting for cache keys.

