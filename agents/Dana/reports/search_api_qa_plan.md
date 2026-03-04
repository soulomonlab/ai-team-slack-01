Search API QA Plan

Files referenced:
- Frontend draft: output/code/search.ts
- Frontend assumptions: output/code/SEARCH_API_ASSUMPTIONS.md

Goal
- Validate search endpoints behavior, paging (opaque cursor), filtering, facets, suggest, auth, and error handling.

Acceptance criteria (ask backend to confirm exact thresholds):
- Correctness: results match query + filters; total_count accuracy or clear guidance if omitted.
- Paging: next_cursor returned when more results exist; client can pass next_cursor to get next page. Define whether server uses next_cursor OR has_more + page_token.
- Latency: p95 < 300ms for typical queries (confirm target).
- Auth: requests with credentials: 'include' authenticate and return user-scoped results.

Required from #ai-backend (Marcus) before QA starts:
1) Concrete JSON examples for endpoints (full success and error responses): POST /search, GET /search/facets, GET /search/suggest. Include field names, types, total_count behavior, next_cursor vs has_more, and error codes.
2) Repo default branch name (main/trunk/develop) so frontend can open feat/search-filters branch/PR.
3) Any rate-limit headers or caching headers to expect.

Test scenarios (planned: ~18 tests)
- Happy path: basic search returns results + next_cursor when > page_size.
- Paging: iterate pages until end, validate no duplicates and stable ordering.
- Cursor edge cases (P2/P1):
  - invalid cursor -> 400 with clear error
  - expired/stale cursor -> 410 or meaningful error
  - client reuses cursor concurrently -> deterministic behavior
- page_size extremes: 0, 1, large (max allowed) -> validate server limits
- Filters: valid JSON filter string -> correct subset; malformed JSON -> 400
- Facets: GET /search/facets with filters -> correct buckets; empty result facets behavior
- Suggest: debounce behavior test (frontend), limit parameter, special chars
- Auth: requests without credentials vs with credentials -> access differences
- Injection/XSS: q and filter values containing script chars should be escaped
- Error handling: server 500 -> client shows retry/error state
- Performance: response time under SLA for sample queries
- Race conditions: multiple quick paginate calls -> no missed/duplicated items

Severity expectations (QA):
- P1: crash, incorrect auth (data leak), data loss, ambiguous cursor semantics causing duplication/loss
- P2: incorrect filtering, wrong total_count, unclear error codes
- P3: suggest UX polish, minor header issues

Next steps / handoffs
- #ai-backend (Marcus): provide the JSON examples + default branch name. I will not start automated tests until those are supplied.
- #ai-frontend (Kevin): open PR for feat/search-filters and ping me the PR number when ready. I will create runnable tests and run pytest.

I created this plan: output/reports/search_api_qa_plan.md

Ready to start QA once backend confirms API shapes and branch/PR exist.