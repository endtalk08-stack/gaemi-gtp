import fs from 'node:fs/promises';
import { collectLocalAssets } from './pages-assets.mjs';

const rawBase = process.argv[2];
if (!rawBase) throw new Error('Usage: node scripts/pages/verify-pages-deployment.mjs <deployment-url>');
const base = new URL(rawBase);
base.pathname = base.pathname.endsWith('/') ? base.pathname : base.pathname + '/';
base.search = '';
base.hash = '';
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
        headers: { 'cache-control': 'no-cache' },
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
