-- Persist ticker-to-company news identities without changing market price keys.
-- Stock price/rank uses the existing (market,symbol) primary key. News may
-- be shared by verified company_key; unverified symbols stay independent.
ALTER TABLE public.market_instruments ADD COLUMN IF NOT EXISTS company_key text;
ALTER TABLE public.market_instruments ADD COLUMN IF NOT EXISTS news_name text;
ALTER TABLE public.market_instruments ADD COLUMN IF NOT EXISTS identity_status text;
CREATE INDEX IF NOT EXISTS market_instruments_company_key_idx
  ON public.market_instruments(market, company_key);
