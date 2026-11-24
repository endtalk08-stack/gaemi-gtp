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
  const allFiles = new Map();
  async function walk(directory, relativeDirectory = '') {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      const relative = relativeDirectory ? relativeDirectory + '/' + entry.name : entry.name;
      if (entry.isDirectory()) {
        await walk(absolute, relative);
      } else if (entry.isFile()) {
        allFiles.set(relative, { relative, absolute });
      } else {
        throw new Error('Unsupported frontend filesystem entry: ' + relative);
      }
    }
  }
  await walk(FRONTEND_ROOT);
  if (!allFiles.has('index.html')) throw new Error('frontend/index.html is missing');

  // Validate references in every HTML, CSS and JS file, not just the homepage.
  for (const file of allFiles.values()) {
    const extension = path.extname(file.relative).toLowerCase();
    if (!['.html', '.css', '.js', '.mjs'].includes(extension)) continue;
    const content = await fs.readFile(file.absolute, 'utf8');
    for (const reference of referencesIn(content, extension)) {
      const child = resolveLocalReference(reference.value, file.relative, reference.importOnly);
      if (child && !allFiles.has(child)) {
        throw new Error('Missing local reference: ' + child + ' (referenced by ' + file.relative + ')');
      }
    }
  }
  return [...allFiles.values()].sort((a, b) => a.relative.localeCompare(b.relative));
}
