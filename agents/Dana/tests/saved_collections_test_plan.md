QA Test Plan — Saved Collections Batch API

Location: output/tests/saved_collections_test_plan.md

Goal: Validate contract between frontend and backend for batch ops (op batching, idempotency, conflicts, timestamps, include_total)

Acceptance criteria (must pass to start integration):
- op_id is required and unique per request; missing => 400 with JSON error (P1)
- Server enforces max batch size server-side and returns 400 when exceeded (Kevin prefers 400). If 413 used, document in PR. (P2)
- Timestamps (last_modified, deleted_at) must be RFC3339 UTC with trailing "Z"; non-"Z" offsets rejected with 400 and clear message. (P2)
- Idempotency: repeated op with same op_id returns the original op result (including success/failure and any resource data). (P1)
- Conflict response must include: op_id, client_op, server_item (full), server_last_modified. Example JSON must be in PR. (P2)
- include_total: server returns header X-Total-Precision: exact|estimate or X-Total-Estimate: true|false. Document header name in PR. (P2)

Test scenarios (happy + edge + error):
1) Happy path: single create op with op_id => 200, op result in body
2) Batch happy path: N ops (N<=200) with unique op_id => 200, per-op results
3) Oversized batch: 201 ops => expect 400 (or 413 if backend documents). Confirm body explains limit
4) Missing op_id (single + in batch) => 400 + error indicating which op(s) missing (P1)
5) Duplicate op_id within same request => 400 + error (P1)
6) Retry idempotency: send op, then resend same op_id -> response matches original result (P1)
7) Timestamp format: send non-Z offset timestamps => 400 + clear error pointing to field
8) Conflict handling: simulate server-side conflict -> response contains op_id, client_op, server_item, server_last_modified; frontend should surface both. Include exact JSON example in PR
9) include_total header present: verify header value (exact vs estimate) and behavior when missing
10) Partial failure in batch: some ops succeed, some fail (including conflicts); ensure per-op result granularity and overall HTTP code per spec (document expected overall code in PR)
11) Security: ensure no leaked internal stack traces; error bodies must be sanitized (P1)

Required artifacts in PR (feat/saved-collections/backend):
- Endpoint examples and sample request/response payloads
- Concrete conflict response JSON example
- Documented status codes for: oversized batch, missing op_id, duplicate op_id, malformed timestamps
- Header name for include_total precision
- Note on idempotency behavior for retries

Severity definitions (how QA will block):
- P1: op_id not enforced; idempotency not implemented; server returns 5xx or crashes; sensitive data leakage
- P2: timestamp format not strictly enforced; header name differs but documented; response omission of server_last_modified
- P3: error message wording, minor headers

Next steps for QA:
- Wait for PR link on feat/saved-collections/backend with above artifacts
- Once PR posted: implement pytest tests (output/tests/test_saved_collections.py) and run them against the test/staging environment

