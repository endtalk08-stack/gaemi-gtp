const DO_API_ORIGIN = 'https://quotes.gaemigtp.com';

// Same-origin Pages routes forward only the API request to the existing DO API.
// Keeping the browser request same-origin preserves the site's session cookies.
export async function proxyToDigitalOcean(request) {
  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, DO_API_ORIGIN);
  const headers = new Headers(request.headers);
  for (const name of ['host', 'content-length', 'connection', 'cf-connecting-ip', 'cf-ray']) {
    headers.delete(name);
  }
  const init = {
    method: request.method,
    headers,
    redirect: 'manual',
  };
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    // Buffer the small JSON API payload so the origin receives a Content-Length
    // header that its HTTP/1.1 handler can read reliably.
    init.body = await request.arrayBuffer();
  }
  const upstream = await fetch(target.toString(), init);
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set('Cache-Control', 'no-store');
  responseHeaders.delete('content-length');
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
