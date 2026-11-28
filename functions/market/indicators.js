const BIQUOTE = 'https://biquote.io/api';
const FRED = 'https://fred.stlouisfed.org/graph/fredgraph.csv';
const CBOE_VIX = 'https://cdn.cboe.com/api/global/delayed_quotes/quotes/_VIX.json';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'public, max-age=30, s-maxage=60, stale-while-revalidate=300'
    }
  });
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { accept: 'application/json' },
    signal: AbortSignal.timeout(8000)
  });
  if (!response.ok) throw new Error('Upstream HTTP ' + response.status);
  return response.json();
}

async function fetchFred(seriesId) {
  const url = FRED + '?id=' + encodeURIComponent(seriesId) + '&cosd=' +
    new Date(Date.now() - 21 * 86400000).toISOString().slice(0, 10);
  const response = await fetch(url, {
    headers: { accept: 'text/csv' },
    signal: AbortSignal.timeout(8000)
  });
  if (!response.ok) throw new Error('FRED HTTP ' + response.status);
  const lines = (await response.text()).trim().split(/\r?\n/).slice(1);
  const rows = lines.map(line => {
    const [date, raw] = line.split(',');
    const value = Number(raw);
    return date && raw && raw !== '.' && Number.isFinite(value) ? { date, value } : null;
  }).filter(Boolean);
  if (!rows.length) throw new Error('FRED returned no observations');
  const latest = rows[rows.length - 1];
  const previous = rows.length > 1 ? rows[rows.length - 2] : null;
  return {
    value: latest.value,
    change: previous ? (latest.value - previous.value) * 100 : null,
    changeUnit: 'bp',
    asOf: latest.date,
    points: rows.slice(-20).map(row => row.value)
  };
}

async function fetchBiquote(symbol) {
  const url = BIQUOTE + '/latest?symbols=' + encodeURIComponent(symbol);
  const payload = await fetchJson(url);
  const tick = payload?.[symbol];
  const value = Number(tick?.mid);
  if (!tick || !Number.isFinite(value) || value <= 0) throw new Error('No quote for ' + symbol);
  const age = Number(tick.quoteAgeSeconds);
  return {
    value,
    change: Number.isFinite(Number(tick.dayDiffPercent)) ? Number(tick.dayDiffPercent) : null,
    changeUnit: '%',
    asOf: tick.timestamp || null,
    fresh: tick.stale !== true && tick.marketState !== 'closed' && Number.isFinite(age) && age <= 120,
    marketState: tick.marketState || null,
    points: []
  };
}

async function fetchVix() {
  const payload = await fetchJson(CBOE_VIX);
  const quote = payload?.data;
  const value = Number(quote?.current_price);
  if (!quote || !Number.isFinite(value) || value <= 0) throw new Error('No CBOE VIX quote');
  return {
    value,
    change: Number.isFinite(Number(quote.price_change_percent)) ? Number(quote.price_change_percent) : null,
    changeUnit: '%',
    asOf: payload.timestamp || quote.last_trade_time || null,
    fresh: true,
    points: []
  };
}

export async function onRequestGet() {
  const jobs = await Promise.allSettled([
    fetchFred('DGS2'),
    fetchFred('DGS10'),
    fetchBiquote('DXY'),
    fetchVix(),
    fetchBiquote('USOIL')
  ]);
  const specs = [
    { id: 'us-2y', symbol: 'US 2Y', name: '미국 2년물 금리', source: 'FRED', delay: '일간' },
    { id: 'us-10y', symbol: 'US 10Y', name: '미국 10년물 금리', source: 'FRED', delay: '일간' },
    { id: 'dxy', symbol: 'DXY', name: '달러인덱스', source: 'BiQuote · MT5 CFD', delay: '시세' },
    { id: 'vix', symbol: 'VIX', name: '변동성지수', source: 'CBOE', delay: '지연 시세' },
    { id: 'wti', symbol: 'WTI', name: 'WTI 원유', source: 'BiQuote · MT5 CFD', delay: '시세' }
  ];
  const items = specs.map((spec, index) => {
    const result = jobs[index];
    if (result.status !== 'fulfilled') {
      return { ...spec, ok: false, error: '데이터를 불러오지 못했습니다.' };
    }
    const quote = result.value;
    return {
      ...spec,
      ok: true,
      value: quote.value,
      change: quote.change,
      change_unit: quote.changeUnit,
      as_of: quote.asOf,
      fresh: quote.fresh !== false,
      market_state: quote.marketState || null,
      points: quote.points || []
    };
  });
  return json({ ok: true, updated_at: new Date().toISOString(), items });
}
