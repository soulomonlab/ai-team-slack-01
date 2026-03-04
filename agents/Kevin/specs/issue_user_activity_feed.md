Title: User Activity Feed (P1)

Description:
Implement User Activity Feed feature as specified in output/specs/user_activity_feed.md

Acceptance:
- GET /api/v1/users/{id}/feed
- POST /api/v1/users/{id}/feed/mark-read
- Filters: type, since_cursor, unread_only, page_size (max 100)
- Auth rules: user-only, admins allowed
- Response items shape
- DB schema: events table + indexes
- Perf SLO: p99 < 200ms

Assignee: Marcus
Labels: backend, P1

Notes:
Marcus to start DB schema and branch once the issue exists.
