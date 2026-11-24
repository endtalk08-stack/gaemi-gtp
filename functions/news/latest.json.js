/**
 * Cloudflare Pages Function: GET /news/latest.json
 * Read the existing public news snapshot from the shared R2 bucket.
 * This is read-only: no Neon, external news API, or AI calls.
 *
 * Existing gaemigtp-main Pages binding:
 *   DATA_R2 -> gaemigtp-news-data
 */
const OBJECT_KEY = "news/latest.json";

export async function onRequestGet({ request, env }) {
  const bucket = env.DATA_R2;
  if (!bucket || typeof bucket.get !== "function") {
    return new Response(JSON.stringify({ ok: false, error: "news_storage_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  let object;
  try {
    object = await bucket.get(OBJECT_KEY);
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
