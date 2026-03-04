/*
Frontend API client for search endpoints (GET /search/suggest, POST /search, GET /search/facets)
Assumptions are documented in SEARCH_API_ASSUMPTIONS.md. Update types once backend confirms shapes.
*/

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';

export type OpaqueCursor = string; // base64 opaque cursor from backend

// --- Suggest ---
export interface SuggestRequest {
  q: string;
  limit?: number;
}

export interface SuggestItem {
  id?: string;
  text: string;
  // backend may return score or metadata
  [k: string]: any;
}

export interface SuggestResponse {
  query: string;
  suggestions: SuggestItem[];
}

// --- Search (cursor pagination) ---
export interface SearchFilters {
  [facet: string]: string[]; // e.g. { category: ['books'], tag: ['react'] }
}

export interface SearchRequest {
  q: string;
  filters?: SearchFilters;
  page_size?: number;
  cursor?: OpaqueCursor | null;
}

export interface SearchHit {
  id: string;
  title: string;
  snippet?: string;
  // additional fields
  [k: string]: any;
}

export interface SearchResponse {
  hits: SearchHit[];
  total_count?: number; // optional — backend to confirm
  next_cursor?: OpaqueCursor | null;
  has_more?: boolean; // optional fallback if next_cursor not provided
}

// --- Facets ---
export interface FacetBucket {
  key: string;
  count: number;
}

export interface Facet {
  name: string;
  buckets: FacetBucket[];
  // optional: selected buckets
  selected?: string[];
}

export interface FacetsResponse {
  facets: Facet[];
  // optional metadata
  _meta?: any;
}

// Minimal fetch wrapper
async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + String(input), {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export async function getSuggest(q: string, limit = 6): Promise<SuggestResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return request<SuggestResponse>(`/search/suggest?${params.toString()}`);
}

export async function postSearch(body: SearchRequest): Promise<SearchResponse> {
  return request<SearchResponse>(`/search`, { method: 'POST', body: JSON.stringify(body) });
}

export async function getFacets(q: string, filters?: SearchFilters): Promise<FacetsResponse> {
  const params = new URLSearchParams({ q });
  if (filters) params.append('filters', JSON.stringify(filters));
  return request<FacetsResponse>(`/search/facets?${params.toString()}`);
}

/*
Notes:
- Cursor is treated as opaque string. Client will pass through whatever backend returns in next_cursor.
- We assume JSON error bodies are not required; basic text errors thrown for now.
- Update types once Marcus provides concrete response shapes (total_count presence, facets shape, suggest item fields).
- Will wire this into zustand search store in feat/search-filters branch.
*/
