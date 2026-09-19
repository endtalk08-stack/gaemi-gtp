# gaemiGTP performance patch — safe2

- Removed the top-level /analyze ThreadPool fan-out because news/disclosure collection already has internal concurrency; stacking thread pools can increase external API contention on Render.
- Kept short TTL caches for quote/trend/Yahoo/volume profile/search.
- Kept news single-flight so duplicate same-stock news fetches collapse to one external request.
- Kept AbortController, with stale loader cleanup fixed.
- Kept X-Analysis-Time-Ms header for real Render timing measurement.

This version prioritizes stable latency over aggressive concurrency.
