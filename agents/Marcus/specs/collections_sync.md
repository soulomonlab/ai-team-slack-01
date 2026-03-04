# Collections Sync API - Spec

This document captures decisions and example payloads for POST /api/v1/collections/sync used by frontend and QA.

Key decisions
- Endpoint: POST /api/v1/collections/sync
- Auth: Bearer token required. 401 on missing/invalid token.
- Batch limit: max 200 ops per request. If client submits >200, server returns 400 Bad Request with structured error explaining the limit.
- op_id: required for every op in the batch. Server validates presence and uniqueness per-request. If missing -> 400 with error code `missing_op_id`. If duplicate op_id within the same request -> 400 `duplicate_op_id`.
- Idempotency: server persists per-op result keyed by (user_id, op_id) for 24 hours. If the same op_id is retried, server returns the prior op result (same status and details). This covers common retry-after-network-fail scenarios.
- Time format: Server strictly requires RFC3339 UTC (Zulu) format: e.g. `2024-03-01T12:34:56.789Z`. Timezone offsets (e.g. `+01:00`) are rejected with 400 `invalid_timestamp_format`.
- last_modified & deleted_at: last_modified required on client-sent items. deleted_at nullable. Server stores UTC and returns RFC3339 Z.
- Conflict handling: On conflict, per-op result status = `conflict` and response includes `server_last_modified` (RFC3339 Z) and `server_item` full object.
- include_total: query ?include_total=true computes exact total; can be slow. If include_total=true and server returns an estimate, header `X-Total-Estimate: true` will be set (boolean string). When exact, header `X-Total-Estimate: false`.
- Rate limiting: 429 with `Retry-After` header. Add standard rate-limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

Error codes & status summary
- 400 Bad Request: malformed payload, >200 ops, missing op_id, duplicate op_id, invalid timestamp format, validation errors.
- 401 Unauthorized: missing/invalid bearer token
- 413 Payload Too Large: not used for op count overflow; we chose 400 for clarity
- 429 Too Many Requests: rate limit exceeded
- 500/502/503: server errors

Example: Request
POST /api/v1/collections/sync?include_total=false
Authorization: Bearer <token>

{
  "ops": [
    {
      "op_id": "op-1",
      "action": "upsert",
      "item": {
        "id": "item-123",
        "data": {"title":"Hello"},
        "last_modified": "2026-03-04T10:00:00.000Z",
        "deleted_at": null
      }
    },
    {
      "op_id": "op-2",
      "action": "delete",
      "item": {
        "id": "item-456",
        "last_modified": "2026-03-04T09:00:00.000Z",
        "deleted_at": "2026-03-04T09:00:00.000Z"
      }
    }
  ]
}

Example: Successful response
200 OK
{
  "results": [
    {"op_id":"op-1","status":"ok"},
    {"op_id":"op-2","status":"ok"}
  ],
  "has_more": false,
  "next_cursor": null
}

Example: Conflict response (per-op)
200 OK
{
  "results": [
    {
      "op_id":"op-1",
      "status":"conflict",
      "server_last_modified":"2026-03-04T10:05:00.000Z",
      "server_item": {"id":"item-123","data":{"title":"Server title"},"last_modified":"2026-03-04T10:05:00.000Z","deleted_at":null}
    }
  ],
  "has_more": false,
  "next_cursor": null
}

Idempotency example
- Client sends op_id `op-1`. Server processes and stores result.
- If client retries with same op_id within 24h, server returns the stored op result instead of reapplying.

Notes for QA
- Batch boundaries to test: 199, 200, 201 — server should accept 200 and reject 201 with 400.
- Timestamp validation: send offsets and missing Z to confirm rejection.
- Ensure per-op conflict includes `server_item` and `server_last_modified`.
- include_total=true path may set `X-Total-Estimate: true` when approximate.

Implementation artifacts in PR will include example payloads and unit tests covering explicit QA scenarios.
