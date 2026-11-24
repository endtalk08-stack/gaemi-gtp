import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
export const REPOSITORY_ROOT = path.resolve(scriptDirectory, '../..');
export const FRONTEND_ROOT = path.join(REPOSITORY_ROOT, 'frontend');

function resolveLocalReference(rawValue, fromFile, importOnly = false) {
  const value = String(rawValue || '').trim();
  if (!value || /^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i.test(value)) return null;
  if (importOnly && !value.startsWith('./') && !value.startsWith('../') && !value.startsWith('/')) return null;
  if (/^var\(/i.test(value)) return null;
  let pathname = value.split(/[?#]/, 1)[0];
  if (!pathname) return null;
  try { pathname = decodeURIComponent(pathname); } catch (_) { throw new Error('Invalid encoded asset path: ' + value); }
  const fromDirectory = path.posix.dirname(fromFile);
  const relative = path.posix.normalize(pathname.startsWith('/') ? pathname.slice(1) : path.posix.join(fromDirectory, pathname));
  if (!relative || relative === '.' || relative === '..' || relative.startsWith('../') || path.posix.isAbsolute(relative)) {
    throw new Error('Asset reference escapes frontend/: ' + value + ' from ' + fromFile);
  }
  return relative;
}

function referencesIn(content, extension) {
  const refs = [];
  if (extension === '.html') {
    const attr = /\b(?:src|href)=["']([^"']+)["']/gi;
    let match;
    while ((match = attr.exec(content))) refs.push({ value: match[1], importOnly: false });
  } else if (extension === '.css') {
    const url = /url\(\s*(?:"([^"]+)"|'([^']+)'|([^)'"]+))\s*\)/gi;
    let match;
    while ((match = url.exec(content))) refs.push({ value: match[1] || match[2] || match[3], importOnly: false });
    const imported = /@import\s+(?:url\(\s*)?["']([^"']+)["']/gi;
    while ((match = imported.exec(content))) refs.push({ value: match[1], importOnly: false });
  } else if (extension === '.js' || extension === '.mjs') {
    const imported = /(?:\bimport\s+(?:[^'"]*?\s+from\s*)?|\bexport\s+[^'"]*?\s+from\s*)["']([^"']+)["']|\bimport\s*\(\s*["']([^"']+)["']\s*\)/g;
    let match;
    while ((match = imported.exec(content))) refs.push({ value: match[1] || match[2], importOnly: true });
  }
  return refs;
}

export async function collectLocalAssets() {
  const pending = ['index.html'];
  const visited = new Set();
  const files = [];
  while (pending.length) {
    const relative = pending.shift();
    if (visited.has(relative)) continue;
    visited.add(relative);
    const absolute = path.join(FRONTEND_ROOT, ...relative.split('/'));
    let stat;
    try { stat = await fs.stat(absolute); } catch (_) { throw new Error('Missing frontend asset: ' + relative); }
    if (!stat.isFile()) throw new Error('Frontend reference is not a file: ' + relative);
    files.push({ relative, absolute });
    const extension = path.extname(relative).toLowerCase();
    if (!['.html', '.css', '.js', '.mjs'].includes(extension)) continue;
    const content = await fs.readFile(absolute, 'utf8');
    for (const reference of referencesIn(content, extension)) {
      const child = resolveLocalReference(reference.value, relative, reference.importOnly);
      if (child && !visited.has(child)) pending.push(child);
    }
  }
  return files.sort((a, b) => a.relative.localeCompare(b.relative));
}
