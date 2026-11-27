// Cloudflare Pages: US TOP20 price-move headlines written to R2 by the DigitalOcean
// job backend/us_move_news.py ("엔비디아가 상승률 5%를 돌파했어요"). Read-only.
const OBJECT_KEY = 'news/stocks/us/MOVEFEED.json';
const SYMBOL = /^[A-Z][A-Z0-9.-]{0,14}$/;
const text = (value, max) => (typeof value === 'string' ? value.trim().slice(0, max) : '');
const CACHE = { 'Cache-Control': 'public, max-age=30, s-maxage=30' };

export async function onRequestGet({ env }) {
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'moves_unavailable', items: [] }, { status: 503 });
  }
  let object;
  try {
    object = await env.DATA_R2.get(OBJECT_KEY);
  } catch (_) {
    return Response.json({ ok: false, error: 'moves_unavailable', items: [] }, { status: 503 });
  }
  if (!object) return Response.json({ ok: true, items: [] }, { headers: CACHE });
  try {
    const data = await object.json();
    if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid');
    const items = data.items.map(raw => {
      const title = text(raw?.title, 80);
      const published = text(raw?.published_at, 40);
      const id = text(raw?.id, 60);
      if (!title || !SYMBOL.test(String(raw?.symbol || '')) || !/^[A-Za-z0-9.-]{5,60}$/.test(id)
          || Number.isNaN(Date.parse(published))) return null;
      return { id: 'move:' + id, symbol: raw.symbol, title, published_at: published };
    }).filter(Boolean).slice(0, 120);
    return Response.json({ ok: true, items }, { headers: CACHE });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_moves', items: [] }, { status: 502 });
  }
}
