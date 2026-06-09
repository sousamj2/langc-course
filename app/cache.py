


import hashlib
import time
from typing import Optional

class ResponseCache:
    """
    In-memory reponse cache with TTL (time-to-live):

    In production, replace this with Redis for:
    - Persistence across restarts
    - Shared cache across instances
    - Built-in TTL management
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0


    
    def _make_key(self, query: str) -> str:
        """
        Create a normalized cache key from message and thread_id.

        Uses SHA-256 hash of:
        normalized_query
        """
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # 'What is Python?' and 'what is python?' should map to the same cache key

    def get(self, query: str) -> Optional[dict]:
        """
        Get a cached response if available and not expired.

        Args:
            message: User message
            thread_id: Conversation thread ID

        Returns:
            Cached response dict or None if not found/expired
        """
        key = self._make_key(query)

        if key in self._cache:
            entry = self._cache[key]
            # Check if cache entry has expired
            if time.time() - entry["timestamp"] < self.ttl:
                # Valid entry found
                self._hits += 1
                return entry["response"]
            else:
                # Remove expired entry
                del self._cache[key]

        self._misses += 1
        return None

    def set(self, query: str, response: dict) -> None:
        """
        Cache a response.

        Args:
            message: User message
            thread_id: Conversation thread ID
            response: Response to cache
        """
        key = self._make_key(query)
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "query": query,
        }

    @property
    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict with stats
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
      
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "cached_entries": len(self._cache),
        }


