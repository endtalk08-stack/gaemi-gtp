import fs from 'node:fs/promises';
import { collectLocalAssets } from './pages-assets.mjs';

const rawBase = process.argv[2];
if (!rawBase) throw new Error('Usage: node scripts/pages/verify-pages-deployment.mjs <deployment-url>');
const base = new URL(rawBase);
base.pathname = base.pathname.endsWith('/') ? base.pathname : base.pathname + '/';
base.search = '';
base.hash = '';
// Cloudflare Access (login lock): a service token, when configured, lets the
// check through. Without one, a locked site is reported and skipped.
const accessHeaders = {};
if (process.env.CF_ACCESS_CLIENT_ID && process.env.CF_ACCESS_CLIENT_SECRET) {
  accessHeaders['CF-Access-Client-Id'] = process.env.CF_ACCESS_CLIENT_ID;
  accessHeaders['CF-Access-Client-Secret'] = process.env.CF_ACCESS_CLIENT_SECRET;
}
const probe = await fetch(base, {
  headers: { 'cache-control': 'no-cache', ...accessHeaders },
  signal: AbortSignal.timeout(20000)
});
const probeBody = await probe.text();
if (/cloudflareaccess\.com/i.test(probe.url) || /Cloudflare Access|cloudflareaccess\.com/i.test(probeBody)) {
  if (Object.keys(accessHeaders).length) {
    console.error('Cloudflare Access rejected the service token at ' + base.origin + '.');
    process.exit(1);
  }
  console.log('::warning::' + base.origin + ' is behind Cloudflare Access and no service token is set; asset verification skipped.');
  process.exit(0);
}
const assets = await collectLocalAssets();
const failures = [];
let verified = 0;
const concurrency = 6;
for (let start = 0; start < assets.length; start += concurrency) {
  const batch = assets.slice(start, start + concurrency);
  await Promise.all(batch.map(async asset => {
    const url = new URL(asset.relative, base);
    try {
      const response = await fetch(url, {
        headers: { 'cache-control': 'no-cache', ...accessHeaders },
        signal: AbortSignal.timeout(20000)
      });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const actual = Buffer.from(await response.arrayBuffer());
      const expected = await fs.readFile(asset.absolute);
      if (!actual.equals(expected)) throw new Error('deployed bytes differ from checked-out source');
      verified += 1;
    } catch (error) {
      failures.push(asset.relative + ': ' + error.message);
    }
  }));
}
if (failures.length) {
  console.error('Deployment asset verification failed (' + failures.length + '/' + assets.length + '):');
  for (const failure of failures) console.error(' - ' + failure);
  process.exit(1);
}
console.log('Verified all ' + verified + ' deployed frontend files byte-for-byte at ' + base.origin + '.');
