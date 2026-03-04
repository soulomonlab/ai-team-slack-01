# Smart Search & Filters — Design Spec

Location: output/design/smart_search_filter_spec.md
Priority: P0
Owner: Maya (UX)
Handoff: #ai-frontend (implementation), #ai-backend (API & scale)

## Summary
Design for a unified Smart Search + Filters experience across desktop and mobile. Goals: make discovery fast and forgiving, keep UI uncluttered, and ensure backend can scale (server-side filtering, pagination, facet precomputation).

## User & Context
- Primary users: power users who need fast discovery; new users who need guided filtering
- Contexts: quick lookup, exploratory browsing, refining large result sets

## User flow
1. User focuses search bar -> type query -> suggestions appear (top N, categories)
2. User refines with filters (category, date, tag, status) via side panel (desktop) or bottom sheet (mobile)
3. Results update live with debounce and server-side requests
4. User sorts, toggles view (list / card), and pages or infinite-scrolls
5. Users can save or share filter state (URL)

## Wireframes (ASCII)
Desktop (wide):

-------------------------------------------------------------
| Logo | Search bar [🔍 Type to search...]            [Sort] |
-------------------------------------------------------------
| Filters (left, collapsible) | Results grid/list (cards)    |
| - Category                  |  Card 1                     |
| - Tags                      |  Card 2                     |
| - Date range                |  ...                        |
-------------------------------------------------------------

Mobile:
-------------------------------------------------------------
| Top bar: Logo | Search icon                                   |
-------------------------------------------------------------
| Search field (full-width)                                       |
| Suggestions dropdown (type-ahead)                               |
| [Results list/cards]                                            |
| Floating FAB: Filters -> opens bottom sheet                     |
-------------------------------------------------------------

## Components & Interaction Specs
- Search bar
  - Placeholder: "Search items, people, tags..."
  - Debounce: 300ms (configurable)
  - Minimum chars to search: 2
  - Keyboard: Enter = search; Arrow keys navigate suggestions; Esc clears
  - Suggestion types: recent, autocomplete, categories (highlight match)

- Filters panel
  - Desktop: collapsible left panel, width 280px
  - Mobile: bottom sheet, full-width, draggable to dismiss
  - Controls: multi-select chips, single-select radio for sort, date-picker
  - Show counts for each facet (server-supplied, cached)
  - Active filters appear as removable chips above results
  - Clear all button (prominent)

- Results
  - Card layout default; optional compact list
  - Highlight matched query terms in title/snippet
  - Lazy-load images; use skeleton loaders
  - Empty state with suggested queries and popular filters

## Accessibility
- All interactive elements keyboard-focusable and labeled
- Contrast ratios meet AA
- ARIA roles for suggestions list and filter controls

## Performance & Backend Notes (hand-off)
- Server-side filtering and sorting; frontend sends filter state and pagination cursor
- Use cursor-based pagination / infinite scroll to scale
- Precompute facet counts in background or cache to avoid heavy aggregation on each request
- Suggestion endpoint: prefix search, top 10 results, rate-limited, memory-cached
- Debounce client-side + server-side request throttling

## Edge Cases
- Large facet cardinality: show top N + "more" modal
- Conflicting filters: show explanation and disable Apply until resolved
- Offline: surface cached recent results and indicate stale data

## Metrics to track (for QA/ML team)
- Search success rate (click after search)
- Time-to-first-result (TTFR)
- Query abandonment (typed -> no submit)

## Key Design Decisions (short)
- Use side panel on desktop and bottom sheet on mobile: reason — preserves reading space on wide screens and follows mobile interaction patterns.
- Debounce 300ms: trade-off between responsiveness and server load.
- Server-side facets + cached counts: ensures scalability for large datasets.
- Highlight matches in results: improve perceived relevance quickly.

## Handoff
- #ai-frontend: implement components, follow sizes/spacing and interaction patterns above. Provide a branch like `feat/search-filters` and ping me for review.
- #ai-backend: provide endpoints:
  - GET /search/suggest?q=&limit=
  - POST /search (body: {q, filters, sort, cursor, limit}) -> {results, cursor, facets}
  - GET /search/facets?query=
  Note: implement cursor pagination and cached facet counts.

## Files & Assets
- Wireframes inline (above). I can produce hi-fi mockups on request.

## Next actions
- #ai-frontend create branch `feat/search-filters` and start UI components
- #ai-backend design endpoints and sketch performance plan
- #ai-qa prepare tests for keyboard nav, filter combos, and pagination

---
Maya — UX
