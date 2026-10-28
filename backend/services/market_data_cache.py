"""Bounded process-local cache for public market reads; never persists prices."""
import copy
import functools
import threading
import time
from collections import OrderedDict


class MarketReadCache:
    def __init__(self, max_entries=128):
        self.max_entries = max_entries
        self._entries = OrderedDict()
        self._lock = threading.RLock()

    def clear(self):
        with self._lock:
            self._entries.clear()

    def get_or_load(self, key, load, *, ttl, empty_ttl=5):
        # Hold the lock through a miss: many simultaneous visitors share one read.
        with self._lock:
            now = time.monotonic()
            entry = self._entries.get(key)
            if entry is not None and now < entry[0]:
                self._entries.move_to_end(key)
                return copy.deepcopy(entry[1])
            value = load()  # Raised errors are never cached.
            lifetime = ttl if value is not None and value != [] and value != {} else empty_ttl
            self._entries[key] = (now + lifetime, copy.deepcopy(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            return value


def cached_market_json(*, ttl=300, error_ttl=15):
    """Share JSON GET responses across visitors; access hooks still run first."""
    cache = MarketReadCache()

    def decorate(function):
        from flask import jsonify, make_response, request

        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            key = (request.path, tuple(sorted(request.args.items(multi=True))))
            def load():
                response = make_response(function(*args, **kwargs))
                body = response.get_json(silent=True)
                if body is None or response.status_code >= 500:
                    # Return an explicit short-lived error entry, never a stale success.
                    return {"body": body, "status": response.status_code, "error": True}
                return {"body": body, "status": response.status_code, "error": response.status_code != 200}
            # Cache successes and failures independently so an outage is retried slowly.
            with cache._lock:
                now = time.monotonic()
                entry = cache._entries.get(key)
                if entry is not None and now < entry[0]:
                    result = copy.deepcopy(entry[1])
                    cache._entries.move_to_end(key)
                else:
                    result = load()
                    cache._entries[key] = (now + (error_ttl if result['error'] else ttl), copy.deepcopy(result))
                    while len(cache._entries) > cache.max_entries:
                        cache._entries.popitem(last=False)
            response = jsonify(result['body'])
            response.status_code = result['status']
            response.headers['Cache-Control'] = 'private, max-age=' + str(error_ttl if result['error'] else 60)
            return response
        wrapped.market_cache = cache
        return wrapped
    return decorate
