/**
 * Cloudflare Pages Function: GET /news/latest.json
 * Read the existing private R2 news snapshot; no API, Neon, or AI calls.
 *
 * Required Pages R2 binding (same Cloudflare account as the bucket):
 *   Variable name: NEWS_R2
 *   Bucket: gaemigtp-news-data
 *
 * A Pages deployment is not created by committing this file.
 */
const OBJECT_KEY = "news/latest.json";

export async function onRequestGet({ request, env }) {
  if (!env.NEWS_R2 || typeof env.NEWS_R2.get !== "function") {
    return new Response(JSON.stringify({ ok: false, error: "news_storage_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  let object;
  try {
    object = await env.NEWS_R2.get(OBJECT_KEY);
  } catch (error) {
    console.error("news_r2_read_failed", error?.name || "Error");
    return new Response(JSON.stringify({ ok: false, error: "news_storage_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  if (!object) {
    return new Response(JSON.stringify({ ok: false, error: "news_not_found" }), {
      status: 404,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  const etag = object.httpEtag;
  if (etag && request.headers.get("If-None-Match") === etag) {
    return new Response(null, { status: 304, headers: { ETag: etag, "Cache-Control": "public, max-age=60" } });
  }

  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=60, stale-while-revalidate=60",
    "X-Content-Type-Options": "nosniff",
  });
  if (etag) headers.set("ETag", etag);
  return new Response(object.body, { status: 200, headers });
}
