import os
import json
import hashlib
from typing import Any, Dict, Optional

import redis

# Key pattern: facets:<index>:<sha256(normalized_query+filters)>
FACETS_CHANNEL = "facets_invalidate"
DEFAULT_TTL = int(os.getenv("FACETS_TTL_SECONDS", "300"))  # 5 minutes


def get_redis() -> redis.Redis:
    """Create a redis client (connection pooling handled by redis-py).
    Reads REDIS_URL env var.
    """
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)


def normalize_query_and_filters(query: str, filters: Optional[Dict[str, Any]]) -> str:
    """Return a deterministic string representation used for hashing.
    - query: raw user query string
    - filters: dict of filters (can be nested)
    """
    filters = filters or {}
    # Use json.dumps with sort_keys to ensure deterministic ordering
    return json.dumps({"q": query or "", "f": filters}, sort_keys=True, separators=(",", ":"))


def facets_cache_key(index: str, normalized_query_and_filters: str) -> str:
    h = hashlib.sha256(normalized_query_and_filters.encode("utf-8")).hexdigest()
    return f"facets:{index}:{h}"


def get_facets(redis_client: redis.Redis, index: str, normalized_query_and_filters: str) -> Optional[Dict[str, Any]]:
    key = facets_cache_key(index, normalized_query_and_filters)
    raw = redis_client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # Corrupt data: delete key to avoid repeated failures
        redis_client.delete(key)
        return None


def set_facets(redis_client: redis.Redis, index: str, normalized_query_and_filters: str, value: Dict[str, Any], ttl: int = DEFAULT_TTL) -> None:
    key = facets_cache_key(index, normalized_query_and_filters)
    payload = json.dumps(value, separators=(",", ":"))
    redis_client.set(key, payload, ex=ttl)


def delete_facets(redis_client: redis.Redis, index: str, normalized_query_and_filters: str) -> int:
    key = facets_cache_key(index, normalized_query_and_filters)
    return redis_client.delete(key)


def publish_invalidation(redis_client: redis.Redis, index: str, normalized_query_and_filters: str) -> int:
    message = json.dumps({"index": index, "payload": normalized_query_and_filters})
    return redis_client.publish(FACETS_CHANNEL, message)
