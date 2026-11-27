// Cloudflare Pages: serve the daily US TOP20 AI move analysis written to R2 by
// the DigitalOcean job (backend/us_news_ai_daily.py). Read-only.
const OBJECT_KEY = 'news/ai/us/TOP20.json';
const SYMBOL = /^[A-Z][A-Z0-9.-]{0,14}$/;
const text = (value, max) => (typeof value === 'string' ? value.trim().slice(0, max) : '');
const number = value => (typeof value === 'number' && Number.isFinite(value) ? value : null);

function cleanItem(raw) {
  if (!raw || typeof raw !== 'object' || !SYMBOL.test(String(raw.symbol || ''))) return null;
  const status = raw.status === 'ok' ? 'ok' : raw.status === 'no_news' ? 'no_news' : null;
  if (!status) return null;
  const item = {
    status, symbol: raw.symbol, name: text(raw.name, 60) || raw.symbol,
    rank: Number.isInteger(raw.rank) ? raw.rank : null,
    price: number(raw.price), change_pct: number(raw.change_pct),
    generated_at: text(raw.generated_at, 40)
  };
  if (status === 'ok') {
    const keywords = Array.isArray(raw.keywords) ? raw.keywords.map(k => text(k, 30)).filter(Boolean) : [];
    const lines = Array.isArray(raw.lines) ? raw.lines.map(l => text(l, 220)).filter(Boolean) : [];
    const headline = text(raw.headline_keyword, 30);
    if (keywords.length !== 3 || lines.length !== 3 || !keywords.includes(headline)) return null;
    item.headline_keyword = headline;
    item.keywords = keywords;
    item.lines = lines;
    item.confidence = raw.confidence === 'high' ? 'high' : 'low';
    item.sources = (Array.isArray(raw.sources) ? raw.sources : []).slice(0, 6).map(source => {
      let url = '';
      try {
        const parsed = new URL(String(source?.url || ''));
        if (parsed.protocol === 'https:' || parsed.protocol === 'http:') url = parsed.href;
      } catch (_) {}
      return { title: text(source?.title, 200), source: text(source?.source, 80),
               published_at: text(source?.published_at, 40), url };
    }).filter(source => source.title && source.url);
  }
  return item;
}

export async function onRequestGet({ env }) {
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'analysis_source_unavailable', items: [] }, { status: 503 });
  }
  let object;
  try {
    object = await env.DATA_R2.get(OBJECT_KEY);
  } catch (_) {
    return Response.json({ ok: false, error: 'analysis_source_unavailable', items: [] }, { status: 503 });
  }
  if (!object) {
    // Not generated yet: the widget shows when the next analysis runs.
    return Response.json({ ok: true, exchange_day: null, generated_at: null, items: [] },
      { headers: { 'Cache-Control': 'public, max-age=60, s-maxage=60' } });
  }
  try {
    const data = await object.json();
    if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid_snapshot');
    const items = data.items.map(cleanItem).filter(Boolean);
    return Response.json({
      ok: true, exchange_day: text(data.exchange_day, 10) || null,
      generated_at: text(data.generated_at, 40) || null, items
    }, { headers: { 'Cache-Control': 'public, max-age=300, s-maxage=300' } });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_analysis_snapshot', items: [] }, { status: 502 });
  }
}
