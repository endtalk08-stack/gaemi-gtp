import fs from 'node:fs/promises';
import path from 'node:path';
import { collectLocalAssets, REPOSITORY_ROOT, FRONTEND_ROOT } from './pages-assets.mjs';

const assets = await collectLocalAssets();
const functionsRoot = path.join(REPOSITORY_ROOT, 'functions');
const expectedFunctions = [
  'market/qqq-reason.js',
  'market/us-daily-chart.js',
  'stocks/us/instruments.json.js'
];
for (const relative of expectedFunctions) {
  const fullPath = path.join(functionsRoot, ...relative.split('/'));
  const stat = await fs.stat(fullPath).catch(() => null);
  if (!stat || !stat.isFile() || stat.size === 0) throw new Error('Missing required Pages Function: functions/' + relative);
}
const functionFiles = [];
async function walk(directory) {
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) await walk(fullPath);
    else if (entry.isFile() && entry.name.endsWith('.js')) functionFiles.push(fullPath);
  }
}
await walk(functionsRoot);
if (!functionFiles.length) throw new Error('No Pages Functions found under repository-root functions/');
const advancedWorker = path.join(FRONTEND_ROOT, '_worker.js');
if (await fs.stat(advancedWorker).then(() => true).catch(() => false)) {
  throw new Error('frontend/_worker.js would override the file-based functions/ routes; review before deploy.');
}
console.log('Validated ' + assets.length + ' local frontend files referenced by index.html, CSS and JS.');
console.log('Validated ' + functionFiles.length + ' Pages Function source files under repository-root functions/.');
console.log('Static output: frontend/ ; Pages Functions source: functions/ ; deploy command must run from repository root.');
