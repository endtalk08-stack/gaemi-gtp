import { proxyToDigitalOcean } from '../../../_utils/do-proxy.js';

export async function onRequest({ request }) {
  return proxyToDigitalOcean(request);
}
