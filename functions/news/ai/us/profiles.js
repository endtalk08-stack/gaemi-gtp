// Cloudflare Pages: one-sentence company intros written by the DigitalOcean job
// (backend/us_news_ai_daily.py), shown under 관련 종목 in news details. Read-only.
const OBJECT_KEY = 'news/ai/us/PROFILES.json';
const SYMBOL = /^[A-Z][A-Z0-9.-]{0,14}$/;
const CACHE = { 'Cache-Control': 'public, max-age=300, s-maxage=300' };

export async function onRequestGet({ env }) {
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'profiles_unavailable', items: {} }, { status: 503 });
  }
  let object;
  try {
    object = await env.DATA_R2.get(OBJECT_KEY);
  } catch (_) {
    return Response.json({ ok: false, error: 'profiles_unavailable', items: {} }, { status: 503 });
  }
  if (!object) return Response.json({ ok: true, items: {} }, { headers: CACHE });
  try {
    const data = await object.json();
    if (data?.ok !== true || !data.items || typeof data.items !== 'object') throw new Error('invalid');
    const items = {};
    for (const [symbol, row] of Object.entries(data.items)) {
      const intro = typeof row?.intro === 'string' ? row.intro.trim() : '';
      if (SYMBOL.test(symbol) && intro.length >= 5 && intro.length <= 160) items[symbol] = intro;
    }
    return Response.json({ ok: true, items }, { headers: CACHE });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_profiles', items: {} }, { status: 502 });
  }
}
