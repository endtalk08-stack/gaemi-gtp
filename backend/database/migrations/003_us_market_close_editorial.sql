-- Standalone, one generated US-close article per New York trading session.
-- No third-party article bodies are persisted. Render performs read-only queries.
CREATE TABLE IF NOT EXISTS public.us_market_close_briefs (
    session_date date PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('processing','published','failed')),
    content text,
    source_manifest jsonb NOT NULL DEFAULT '[]'::jsonb,
    model text NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    CONSTRAINT us_close_published_content_check
        CHECK (status <> 'published' OR (content IS NOT NULL AND length(content) > 0))
);
CREATE INDEX IF NOT EXISTS us_market_close_briefs_active
    ON public.us_market_close_briefs (expires_at DESC, session_date DESC)
    WHERE status='published';
