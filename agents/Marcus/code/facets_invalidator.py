import os
import json
from typing import Optional

from celery import Celery

from redis_helper import get_redis, delete_facets, set_facets, FACETS_CHANNEL, normalize_query_and_filters

# Celery config: use REDIS_URL as broker and backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("facets_invalidator", broker=REDIS_URL, backend=REDIS_URL)

# Goal: invalidation within ≤5s of publishing


@celery.task(ignore_result=True)
def invalidate_facets(message_json: str, recompute: bool = False) -> None:
    """Consume a pub/sub message payload (JSON: {index, payload}).

    Behavior:
    - Delete the cache key for the given normalized payload.
    - Optionally trigger recompute (placeholder hook) and write back to Redis.
    """
    try:
        data = json.loads(message_json)
        index = data.get("index")
        payload = data.get("payload")
        if not index or payload is None:
            return

        r = get_redis()
        # Delete cached facets
        delete_facets(r, index, payload)

        if recompute:
            # Placeholder: call service to compute facets synchronously or via another task
            # compute_and_store_facets(index, payload)
            # Example stub that writes an empty facets response with short TTL
            set_facets(r, index, payload, {"facets": [], "recomputed": True}, ttl=60)
    except Exception:
        # Swallow exceptions to avoid task crashes; rely on monitoring+DLQ for failures
        return


# Optional: small helper to run a simple Redis subscriber that enqueues tasks


def run_subscriber():
    """Run a blocking subscriber to FACETS_CHANNEL and enqueue invalidate tasks.
    This helper is intended for local/dev testing. In prod we expect app code
    to publish messages and Celery worker(s) to pull tasks.
    """
    r = get_redis()
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(FACETS_CHANNEL)
    for msg in pubsub.listen():
        try:
            if msg and msg.get("type") == "message":
                payload = msg.get("data")
                # enqueue async task
                invalidate_facets.delay(payload)
        except Exception:
            continue
