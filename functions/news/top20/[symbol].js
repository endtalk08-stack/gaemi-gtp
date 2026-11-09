/**
 * Read one existing TOP20 stock-news JSON object from NEWS_R2.
 * This endpoint is separate from TradingView /news/latest.json.
 * GET /news/top20/NVDA -> R2 news/top20/NVDA.json
 * No provider, database, AI, or write operations.
 */
export async function onRequestGet({ request, env, params }) {
  const symbol = String(params?.symbol ?? "").toUpperCase();
  if (!/^[A-Z][A-Z0-9.-]{0,15}$/.test(symbol)) {
    return new Response(JSON.stringify({ ok: false, error: "invalid_symbol" }), {
      status: 400,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  if (!env.NEWS_R2 || typeof env.NEWS_R2.get !== "function") {
    return new Response(JSON.stringify({ ok: false, error: "news_storage_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  let object;
  try {
    object = await env.NEWS_R2.get("news/top20/" + symbol + ".json");
  } catch (error) {
    console.error("top20_r2_read_failed", error?.name || "Error");
    return new Response(JSON.stringify({ ok: false, error: "news_storage_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  if (!object) {
    return new Response(JSON.stringify({ ok: false, error: "stock_news_not_found" }), {
      status: 404,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=60, stale-while-revalidate=60",
    "X-Content-Type-Options": "nosniff",
  });
  if (object.httpEtag) {
    headers.set("ETag", object.httpEtag);
    if (request.headers.get("If-None-Match") === object.httpEtag) {
      return new Response(null, { status: 304, headers });
    }
  }
  return new Response(object.body, { status: 200, headers });
}
