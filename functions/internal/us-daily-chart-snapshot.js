// Authenticated server-to-R2 publisher for verified US daily candles.
const SYMBOL = /^[A-Z0-9.-]{1,20}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SOURCE = 'kiwoom:usa06012';

function sameSecret(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string' || left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

export async function onRequestPost({ request, env }) {
  const configured = env.CHART_SYNC_TOKEN;
  const supplied = request.headers.get('Authorization') || '';
  if (!configured || !sameSecret(supplied, 'Bearer ' + configured)) {
    return Response.json({ ok: false, error: 'unauthorized' }, { status: 401 });
  }
  if (!env.DATA_R2 || typeof env.DATA_R2.put !== 'function') {
    return Response.json({ ok: false, error: 'chart_storage_unavailable' }, { status: 503 });
  }
  const declaredLength = Number(request.headers.get('Content-Length') || 0);
  if (declaredLength > 65536) {
    return Response.json({ ok: false, error: 'payload_too_large' }, { status: 413 });
  }
  let data;
  try {
    const raw = await request.text();
    if (raw.length > 65536) throw new Error('payload_too_large');
    data = JSON.parse(raw);
  } catch (error) {
    return Response.json({ ok: false, error: error.message === 'payload_too_large' ? 'payload_too_large' : 'invalid_json' },
      { status: error.message === 'payload_too_large' ? 413 : 400 });
  }

  const symbol = typeof data?.symbol === 'string' ? data.symbol.trim().toUpperCase() : '';
  const candles = data?.candles;
  if (!SYMBOL.test(symbol) || data?.interval !== 'daily' || data?.source !== SOURCE ||
      !Array.isArray(candles) || candles.length < 1 || candles.length > 120 ||
      data.count !== candles.length) {
    return Response.json({ ok: false, error: 'invalid_snapshot' }, { status: 400 });
  }
  let previousDate = '';
  for (const row of candles) {
    if (!row || typeof row.date !== 'string' || !DATE.test(row.date) || row.date <= previousDate ||
        !['open', 'high', 'low', 'close'].every(key => Number.isFinite(row[key]) && row[key] > 0) ||
        !Number.isSafeInteger(row.volume) || row.volume < 0 ||
        row.low > Math.min(row.open, row.close) ||
        row.high < Math.max(row.open, row.close) ||
        row.low > row.high) {
      return Response.json({ ok: false, error: 'invalid_candles' }, { status: 400 });
    }
    previousDate = row.date;
  }

  const snapshot = {
    symbol, interval: 'daily', source: SOURCE,
    count: candles.length, updated_at: new Date().toISOString(), candles
  };
  try {
    await env.DATA_R2.put('charts/us/' + symbol + '/daily.json', JSON.stringify(snapshot), {
      httpMetadata: { contentType: 'application/json; charset=utf-8' },
      customMetadata: { symbol, interval: 'daily', source: SOURCE }
    });
  } catch (_) {
    return Response.json({ ok: false, error: 'chart_storage_write_failed' }, { status: 503 });
  }
  return Response.json({ ok: true, symbol, interval: 'daily', count: candles.length });
}
