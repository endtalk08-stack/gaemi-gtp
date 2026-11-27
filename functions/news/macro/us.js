// Cloudflare Pages: US macro headlines (Fed, White House, BEA) translated to Korean,
// written to R2 by the DigitalOcean job backend/us_macro_news.py. Read-only.
const OBJECT_KEY = 'news/stocks/us/MACROFEED.json';
const CATEGORIES = new Set(['연준·금리', '정책·규제', '경제지표']);
const text = (value, max) => (typeof value === 'string' ? value.trim().slice(0, max) : '');
const CACHE = { 'Cache-Control': 'public, max-age=60, s-maxage=60' };

function cleanItem(raw) {
  const title = text(raw?.title, 200);
  const url = text(raw?.url, 500);
  const published = text(raw?.published_at, 40);
  if (!title || !/^https:\/\//.test(url) || Number.isNaN(Date.parse(published))) return null;
  if (!/^[a-f0-9]{16}$/.test(String(raw.id || ''))) return null;
  return {
    id: 'macro:' + raw.id, title, title_en: text(raw.title_en, 300), url, published_at: published,
    source: text(raw.source, 20) || '미국 정부',
    category: CATEGORIES.has(raw.category) ? raw.category : '정책·규제'
  };
}

export async function onRequestGet({ env }) {
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'macro_news_unavailable', items: [] }, { status: 503 });
  }
  let object;
  try {
    object = await env.DATA_R2.get(OBJECT_KEY);
  } catch (_) {
    return Response.json({ ok: false, error: 'macro_news_unavailable', items: [] }, { status: 503 });
  }
  if (!object) return Response.json({ ok: true, generated_at: null, items: [] }, { headers: CACHE });
  try {
    const data = await object.json();
    if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid');
    return Response.json({ ok: true, generated_at: text(data.generated_at, 40) || null,
      items: data.items.map(cleanItem).filter(Boolean).slice(0, 200) }, { headers: CACHE });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_macro_news', items: [] }, { status: 502 });
  }
}
