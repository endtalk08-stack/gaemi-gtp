-- Preserve source evidence independently before temporary article metadata expires.
CREATE TABLE IF NOT EXISTS news_issue_evidence (
  issue_id BIGINT NOT NULL REFERENCES news_ai_issues(id) ON DELETE CASCADE,
  url_hash TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  source_headline TEXT,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (issue_id, url_hash)
);
CREATE INDEX IF NOT EXISTS news_issue_evidence_url_idx
  ON news_issue_evidence (url_hash);
