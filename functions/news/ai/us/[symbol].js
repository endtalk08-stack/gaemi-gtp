/** Read an existing R2 news object for one verified US ticker.
 * Reuses NEWS_R2; never accesses Neon or invokes news/AI providers.
 * GET /news/ai/us/:symbol
 */
export async function onRequestGet({ request, env, params }) {
  const symbol = String(params.symbol || "").trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9.-]{0,14}$/.test(symbol)) {
    return Response.json({ ok: false, error: "invalid_symbol" }, { status: 400 });
  }
  if (!env.NEWS_R2 || typeof env.NEWS_R2.get !== "function") {
    return Response.json({ ok: false, error: "news_storage_unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" }
    });
  }

  let object;
  try {
    object = await env.NEWS_R2.get("news/ai/us/" + symbol + ".json");
  } catch (error) {
    console.error("news_r2_read_failed", error?.name || "Error");
    return Response.json({ ok: false, error: "news_storage_unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" }
    });
  }
  if (!object) {
    return Response.json({ ok: false, error: "news_not_found" }, {
      status: 404, headers: { "Cache-Control": "no-store" }
    });
  }
  const etag = object.httpEtag;
  if (etag && request.headers.get("If-None-Match") === etag) {
    return new Response(null, {
      status: 304,
      headers: { "ETag": etag, "Cache-Control": "public, max-age=60" }
    });
  }
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=60, stale-while-revalidate=60",
    "X-Content-Type-Options": "nosniff",
  });
  if (etag) headers.set("ETag", etag);
  return new Response(object.body, { status: 200, headers });
}
