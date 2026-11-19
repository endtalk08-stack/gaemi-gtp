// Read reported Nasdaq/QQQ catalysts from the existing published news snapshot.
const MAX_NEWS_AGE = 24 * 60 * 60 * 1000;
const CACHE_SECONDS = 300;
const NASDAQ_RISE = /(?:\bQQQ\b|\bNasdaq(?:[- ]?100| Composite)?\b|나스닥(?:\s*[-–]?\s*100|\s*종합)?(?:\s*지수)?)(?:는|은|이|가|도)?\s*(?:(?:전장보다|전일 대비|장중)\s*)?(?:\d+(?:[.,]\d+)?\s*%\s*(?:이상\s*)?)?(?:상승|급등|반등|오름세|올랐|↑)/iu;
const CAUSE_BEFORE_INDEX = /^(.{5,120}?)(에\s*힘입어|영향으로|덕분에|면서|하자|시키자|호재에)\s*[,·…]?\s*(?:(?:미국|뉴욕)\s*증시(?:와|,)?\s*|S&P\s*500(?:\s*지수)?(?:와|,|·)\s*)?$/iu;
const CAUSE_AFTER_INDEX = /^[^.?!…]{0,40}[…·,:]\s*(.{5,100}?)\s*(?:영향|덕분|호재)[.!]?\s*$/u;
const NAMED_EVENT = /실적|가이던스|금리|물가|고용|국채|반도체|기술주|AI|인플레|엔비디아|관세|협상|수주|매수|발표/iu;
const NON_CURRENT_REPORT = /[?？]|상승 전망|오를 전망|상승 전환 가능|상승할|지난주|주간|연간|선물|이틀 전|전날 나스닥|전일 나스닥|반면|에도 불구하고/iu;

function reasonFromTitle(title) {
  if (typeof title !== 'string' || NON_CURRENT_REPORT.test(title)) return '';
  const clean = title.replace(/\s+/g, ' ').replace(/([가-힣]+)\(\1\)/gu, '$1').trim();
  const move = NASDAQ_RISE.exec(clean);
  if (!move) return '';
  const prefix = clean.slice(0, move.index).replace(/^\[[^\]]+\]\s*/u, '');
  const before = CAUSE_BEFORE_INDEX.exec(prefix);
  if (before) return before[1] + (before[2] === '면서' ? '며' : before[2]) + ' 상승';

  const shortCause = /^(.{5,95})에\s*[,·…]?\s*$/u.exec(prefix);
  if (shortCause && NAMED_EVENT.test(shortCause[1])) return shortCause[1] + '에 상승';

  const after = CAUSE_AFTER_INDEX.exec(clean.slice(move.index + move[0].length));
  return after && NAMED_EVENT.test(after[1]) ? after[1] + ' 영향' : '';
}

function reportedReasons(data, now) {
  if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid_news_snapshot');
  const reasons = [];
  for (const item of data.items) {
    const publishedAt = Date.parse(item?.published_at);
    if (!(publishedAt <= now && publishedAt >= now - MAX_NEWS_AGE)) continue;
    const sections = Array.isArray(item?.news_sections) ? item.news_sections : [];
    if (item?.news_section !== 'market' && !sections.includes('market')) continue;
    if (typeof item.source !== 'string' || !item.source.trim() || typeof item.url !== 'string') continue;
    const text = reasonFromTitle(item.title);
    if (!text) continue;
    let url;
    try { url = new URL(item.url); } catch (_) { continue; }
    if (url.protocol !== 'https:') continue;
    reasons.push({ text, publishedAt, source: item.source.slice(0, 100), url: url.href });
  }
  return reasons.sort((a, b) => b.publishedAt - a.publishedAt).slice(0, 20);
}

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = globalThis.caches?.default;
  const cacheKey = new Request(new URL('/market/qqq-reason', request.url));
  const cached = await cache?.match(cacheKey).catch(() => undefined);
  if (cached) return cached;

  try {
    const object = await env.DATA_R2.get('news/latest.json');
    const items = object ? reportedReasons(await object.json(), Date.now()) : [];
    const response = Response.json({ ok: true, items }, {
      headers: { 'Cache-Control': 'public, max-age=' + CACHE_SECONDS }
    });
    if (cache) waitUntil(cache.put(cacheKey, response.clone()).catch(() => {}));
    return response;
  } catch (_) {
    return Response.json({ ok: false, items: [] }, { status: 503 });
  }
}
