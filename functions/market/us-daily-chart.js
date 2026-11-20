// Cloudflare Pages: read existing US daily chart snapshots from R2, never Neon.
const SYMBOL = /^[A-Z0-9.-]{1,20}$/;
export async function onRequestGet({ request, env }) {
  const symbol = (new URL(request.url).searchParams.get('symbol') || '').trim().toUpperCase();
  if (!SYMBOL.test(symbol)) {
    return Response.json({ ok: false, error: 'invalid_symbol', rows: [] }, { status: 400 });
  }
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'chart_source_unavailable', rows: [] }, { status: 503 });
  }
  let object;
  try {
    object = await env.DATA_R2.get('charts/us/' + symbol + '/daily.json');
  } catch (_) {
    return Response.json({ ok: false, error: 'chart_source_unavailable', rows: [] }, { status: 503 });
  }
  if (!object) {
    return Response.json({ ok: false, error: 'chart_not_collected', rows: [] }, { status: 404 });
  }
  try {
    const data = await object.json();
    if (data.symbol !== symbol || data.interval !== 'daily' ||
        !Array.isArray(data.candles) || !data.candles.length ||
        data.count !== data.candles.length) {
      throw new Error('invalid_chart_snapshot');
    }
    const rows = data.candles.slice(-120);
    if (!rows.every(row => typeof row.date === 'string' &&
        ['open', 'high', 'low', 'close'].every(key => Number.isFinite(row[key]) && row[key] > 0) &&
        Number.isSafeInteger(row.volume) && row.volume >= 0)) {
      throw new Error('invalid_chart_candles');
    }
    return Response.json({
      ok: true, symbol, name: symbol, source: data.source,
      rows, error: null
    }, { headers: { 'Cache-Control': 'public, max-age=300, s-maxage=300' } });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_chart_snapshot', rows: [] }, { status: 502 });
  }
}
