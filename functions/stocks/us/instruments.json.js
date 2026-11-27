// Serve the existing R2 instrument/industry snapshot to the Pages sidebar.
// No collection, Neon query, or R2 writes.
export async function onRequestGet({ env }) {
  if (!env.DATA_R2 || typeof env.DATA_R2.get !== 'function') {
    return Response.json({ ok: false, error: 'industry_source_unavailable' }, { status: 503 });
  }

  let object;
  try {
    object = await env.DATA_R2.get('stocks/us/instruments.json');
  } catch (_) {
    return Response.json({ ok: false, error: 'industry_source_unavailable' }, { status: 503 });
  }
  if (!object) {
    return Response.json({ ok: false, error: 'industry_not_collected' }, { status: 404 });
  }

  try {
    const snapshot = await object.json();
    if (!Array.isArray(snapshot?.items)) throw new Error('invalid_snapshot');
    const items = snapshot.items
      .filter(item => typeof item?.symbol === 'string' &&
        typeof item?.industry === 'string' && item.industry.trim())
      .map(item => ({
        symbol: item.symbol,
        industry: item.industry.trim(),
        // Kiwoom display name/exchange let chat resolve a typed stock name
        // to the same selection as a sidebar click.
        ...(typeof item.name === 'string' && item.name.trim() ? { name: item.name.trim() } : {}),
        ...(['ND', 'NY', 'NA'].includes(item.exchange) ? { exchange: item.exchange } : {})
      }));

    // Walmart's issuer lists WMT under All Other General Merchandise Stores.
    // https://stock.walmart.com/company-information
    if (!items.some(item => item.symbol === 'WMT')) {
      items.push({ symbol: 'WMT', industry: '종합 소매' });
    }
    return Response.json({ ok: true, items }, {
      headers: { 'Cache-Control': 'public, max-age=300, s-maxage=300' }
    });
  } catch (_) {
    return Response.json({ ok: false, error: 'invalid_industry_snapshot' }, { status: 502 });
  }
}
