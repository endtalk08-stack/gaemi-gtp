-- News data model v1. Additive only; market ranking tables remain untouched.
-- Store article metadata, not third-party full text without redistribution rights.
CREATE TABLE IF NOT EXISTS news_sources (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN ('news','filing','company','economic','other')),
  homepage_url TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS news_articles (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id BIGINT NOT NULL REFERENCES news_sources(id),
  external_id TEXT,
  canonical_url TEXT NOT NULL,
  url_hash TEXT NOT NULL UNIQUE,
  headline TEXT NOT NULL,
  excerpt TEXT,
  language TEXT CHECK (language IN ('ko','en','other')),
  publisher TEXT,
  published_at TIMESTAMPTZ,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  body_storage_policy TEXT NOT NULL DEFAULT 'metadata_only'
    CHECK (body_storage_policy IN ('metadata_only','licensed','owned')),
  licensed_body TEXT,
  CHECK (licensed_body IS NULL OR body_storage_policy IN ('licensed','owned'))
);
CREATE INDEX IF NOT EXISTS news_articles_published_idx ON news_articles (published_at DESC);
CREATE INDEX IF NOT EXISTS news_articles_source_idx ON news_articles (source_id, published_at DESC);
CREATE TABLE IF NOT EXISTS news_article_symbols (
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  market TEXT NOT NULL CHECK (market IN ('KR','US')),
  symbol TEXT NOT NULL,
  relevance TEXT NOT NULL DEFAULT 'related'
    CHECK (relevance IN ('direct','related','marketwide')),
  PRIMARY KEY (article_id,market,symbol)
);
CREATE INDEX IF NOT EXISTS news_symbols_lookup_idx ON news_article_symbols (market,symbol,article_id DESC);
CREATE TABLE IF NOT EXISTS news_categories (
  category_key TEXT PRIMARY KEY,
  parent_key TEXT REFERENCES news_categories(category_key),
  display_name TEXT NOT NULL,
  category_type TEXT NOT NULL CHECK (category_type IN ('topic','event','region','industry'))
);
CREATE TABLE IF NOT EXISTS news_article_categories (
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  category_key TEXT NOT NULL REFERENCES news_categories(category_key),
  method TEXT NOT NULL DEFAULT 'rule' CHECK (method IN ('rule','ai','manual','source')),
  PRIMARY KEY(article_id,category_key,method)
);
CREATE TABLE IF NOT EXISTS news_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_key TEXT NOT NULL UNIQUE,
  market TEXT NOT NULL CHECK (market IN ('KR','US','GLOBAL')),
  event_title TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);
CREATE TABLE IF NOT EXISTS news_event_articles (
  event_id BIGINT NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  PRIMARY KEY(event_id,article_id)
);
CREATE TABLE IF NOT EXISTS news_ai_issues (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  market TEXT NOT NULL CHECK (market IN ('KR','US')),
  symbol TEXT NOT NULL,
  exchange_day DATE NOT NULL,
  event_id BIGINT REFERENCES news_events(id),
  headline TEXT NOT NULL,
  summary TEXT NOT NULL,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  material_type TEXT,
  material_direction TEXT,
  model_id TEXT,
  version TEXT NOT NULL DEFAULT 'v1',
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS news_ai_issues_lookup_idx ON news_ai_issues(market,symbol,exchange_day DESC,generated_at DESC);
CREATE TABLE IF NOT EXISTS news_ai_issue_sources (
  issue_id BIGINT NOT NULL REFERENCES news_ai_issues(id) ON DELETE CASCADE,
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  PRIMARY KEY(issue_id,article_id)
);
CREATE TABLE IF NOT EXISTS news_ai_call_ledger (
  market TEXT NOT NULL CHECK (market IN ('KR','US')),
  symbol TEXT NOT NULL,
  exchange_day DATE NOT NULL,
  request_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'reserved'
    CHECK (status IN ('reserved','completed','invalid','failed')),
  provider TEXT,
  model_id TEXT,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (market,symbol,exchange_day,request_hash)
);
CREATE INDEX IF NOT EXISTS news_ai_call_ledger_day_idx
  ON news_ai_call_ledger(market,symbol,exchange_day);
-- Supports 3-call limit when reservations are inserted under an advisory lock.
INSERT INTO news_categories(category_key,parent_key,display_name,category_type) VALUES
 ('macro',NULL,'거시경제','topic'),
 ('earnings',NULL,'실적','event'),
 ('filing',NULL,'공시','event'),
 ('investment',NULL,'투자·증설','event'),
 ('policy',NULL,'정책·규제','event'),
 ('supply_chain',NULL,'공급망','topic'),
 ('semiconductor',NULL,'반도체','industry'),
 ('ai',NULL,'AI','industry'),
 ('energy',NULL,'에너지','industry'),
 ('biotech',NULL,'바이오','industry'),
 ('kr',NULL,'한국','region'),
 ('us',NULL,'미국','region')
ON CONFLICT (category_key) DO NOTHING;