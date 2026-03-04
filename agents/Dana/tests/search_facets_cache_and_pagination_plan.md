QA Test Plan: Search facets caching & cursor pagination

File: output/tests/search_facets_cache_and_pagination_plan.md

Purpose:
- Verify Redis-based facet caching, TTL behavior, pub/sub invalidation (Celery), and opaque cursor pagination.
- Define acceptance criteria and test scenarios before implementation PRs.

Acceptance criteria (must pass for QA sign-off):
- Cache hit returns correct, up-to-date facet counts within allowed staleness (<=5m).
- After a write that affects facets, pub/sub → Celery invalidator removes/updates cache within 5s.
- /search cursor pagination stable: no duplicate/missing records across pages even during concurrent writes/deletes.
- Fallback to DB when Redis unavailable with no data leakage; endpoints remain functional (may be slower).
- Performance target observable in infra tests: p99 <150ms for /search (read path) under expected load.

Test scenarios (happy path, edge cases, failures):
1) TC01 - Cache hit (Happy)
   - Steps: Populate cache for query Q. Call GET /search/facets for Q.
   - Expect: 200, cached facets identical to previously stored snapshot; X-Cache: HIT.
   - Severity: P2

2) TC02 - Cache miss (Happy)
   - Steps: Ensure no key. Call GET /search/facets.
   - Expect: 200, facets computed from DB and stored to Redis with TTL=5m; X-Cache: MISS.
   - Severity: P2

3) TC03 - TTL expiry
   - Steps: Create cache entry with short TTL (force expire). After TTL, call facets.
   - Expect: Recompute from DB, store new key; stale data not returned beyond TTL.
   - Severity: P2

4) TC04 - Write invalidation (pub/sub → Celery)
   - Steps: Perform write that should change facets. Observe Redis pub/sub message and Celery invalidator action.
   - Expect: Cache key(s) invalidated/updated within 5s; subsequent GET returns updated counts.
   - Severity: P1

5) TC05 - Race: concurrent read during write
   - Steps: Start long-running write or batch updates; concurrently call facets/read.
   - Expect: Either pre-write snapshot or post-write snapshot, but no corrupted/partial counts. No crashes.
   - Severity: P1

6) TC06 - Pub/sub failure / Celery down
   - Steps: Disable Celery worker or block pub/sub delivery then perform write.
   - Expect: System falls back to on-demand recompute on GET, no silent stale for critical flows; generate alert/metric.
   - Severity: P1

7) TC07 - Redis unavailable
   - Steps: Kill Redis. Call /search and /search/facets.
   - Expect: Requests succeed by querying DB directly (graceful fallback), responses slower but correct; no leaked cache-only keys.
   - Severity: P1

8) TC08 - Cache key correctness (fingerprinting)
   - Steps: Send semantically-equal queries with different param orders/whitespace. Verify same fingerprint key used.
   - Expect: Normalization produces identical Redis key.
   - Severity: P2

9) TC09 - Cursor pagination: basic
   - Steps: POST /search (page size N), follow cursors until end.
   - Expect: No duplicates/missing items, final cursor indicates end (null/empty). Ordering stable.
   - Severity: P2

10) TC10 - Cursor edge: invalid/malformed cursor
    - Steps: Call POST /search with random/expired/altered cursor.
    - Expect: 400 or clear error; no server crash, no data leak.
    - Severity: P2

11) TC11 - Cursor with concurrent writes/deletes
    - Steps: Page through results; during paging perform inserts/deletes affecting result set.
    - Expect: Consistent behavior defined by spec (document expected eventual consistency). No duplicates/omissions beyond acceptable staleness.
    - Severity: P1

12) TC12 - Performance/load
    - Steps: Run load test against /search with caching enabled/disabled.
    - Expect: p99 <150ms under expected load for cached reads; measure cache hit ratio and Redis metrics.
    - Severity: P2

13) TC13 - Security: cache poisoning & auth
    - Steps: Attempt to force a cache key collision via crafted params, request facets for user-scoped searches.
    - Expect: Keys salted/tenant-scoped; unauthorized access not possible via cache.
    - Severity: P1

Metrics & Observability checks:
- Ensure metrics exist: cache_hits, cache_misses, invalidations, pubsub_errors, celery_failures, redis_down_count, facet_compute_latency, search_p99_latency.
- Logs: include cache key fingerprints, invalidation events, correlation IDs.

Test artifacts to produce after code is available:
- Automated pytest files: output/tests/test_search_facets_cache.py, test_search_cursor_pagination.py
- Load test scripts (locust or k6) in output/tests/load/

Next actions / handoffs:
- #ai-frontend (Kevin) — please create branch feat/search-filters (or tell me default branch) so I can target PRs. I will prepare test harness once endpoints exist.
- #ai-backend (Marcus) — when you publish Redis helper + Celery invalidator PR, tag me. I will run TC04/TC06/TC11.
- #ai-devops (Noah) — confirm Redis sizes + pub/sub enabled; I will run Redis failure/fallback tests in staging.

When to start QA:
- I will begin automated QA on PR merge to the feature branch. Expected first pass: unit+integration tests (local), then staging run with load tests.

