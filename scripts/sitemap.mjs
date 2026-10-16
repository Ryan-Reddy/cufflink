#!/usr/bin/env node
// Writes <dist>/sitemap.xml at build time, so it can never go stale.
//
//   node scripts/sitemap.mjs --dist dist --base https://example.com [--routes sitemap.routes.json]
//
// Pages come from two places:
// - every .html file in <dist> (except 404.html), for static and prerendered sites
// - sitemap.routes.json, for single-page apps whose routes have no file of their own:
//     [{"path": "/contact", "source": "src/pages/contact.ts", "images": ["/og.png"]}]
//   "source" (optional) gives lastmod from that file's last commit; "images" (optional)
//   adds <image:image> entries. Without a source, lastmod is the build date.
import {execFileSync} from 'node:child_process';
import {readdirSync, readFileSync, statSync, writeFileSync, existsSync} from 'node:fs';
import {join, relative, sep} from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) =>
  a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1]]] : acc, []));
const dist = args.dist || 'dist';
const base = (args.base || '').replace(/\/$/, '');
if (!base) {
  console.error('sitemap: --base https://your.site is required');
  process.exit(1);
}
const today = new Date().toISOString().slice(0, 10);

function lastCommit(file) {
  try {
    const d = execFileSync('git', ['log', '-1', '--format=%cs', '--', file], {encoding: 'utf8'}).trim();
    return d || today;
  } catch {
    return today;
  }
}

function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return htmlFiles(full);
    return name.endsWith('.html') && name !== '404.html' ? [full] : [];
  });
}

const pages = new Map();
for (const file of existsSync(dist) ? htmlFiles(dist) : []) {
  let path = '/' + relative(dist, file).split(sep).join('/');
  path = path.replace(/index\.html$/, '').replace(/\.html$/, '');
  pages.set(path, {path, lastmod: today, images: []});
}
if (args.routes && existsSync(args.routes)) {
  for (const r of JSON.parse(readFileSync(args.routes, 'utf8'))) {
    pages.set(r.path, {path: r.path, lastmod: r.source ? lastCommit(r.source) : today, images: r.images || []});
  }
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const abs = (p) => (p.startsWith('http') ? p : base + p);
const urls = [...pages.values()].sort((a, b) => a.path.localeCompare(b.path)).map((p) =>
  `  <url>\n    <loc>${esc(abs(p.path))}</loc>\n    <lastmod>${p.lastmod}</lastmod>\n` +
  p.images.map((i) => `    <image:image><image:loc>${esc(abs(i))}</image:loc></image:image>\n`).join('') +
  '  </url>');

writeFileSync(join(dist, 'sitemap.xml'),
  '<?xml version="1.0" encoding="UTF-8"?>\n' +
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' +
  urls.join('\n') + '\n</urlset>\n');
console.log(`sitemap: ${pages.size} pages -> ${join(dist, 'sitemap.xml')}`);
