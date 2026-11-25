#!/usr/bin/env node
/**
 * Initial-JS budget gate (acceptance criterion P-01: ≤ 200 KB gzip, admin bundle
 * excluded).
 *
 * "Initial JS" is exactly what the browser must download before the first route
 * paints: the entry script plus every modulepreload in dist/index.html. The
 * admin chunk is lazy-loaded and therefore not counted — but it is still
 * reported for visibility. Exits non-zero when the budget is exceeded so CI
 * fails instead of quietly regressing.
 */
import { readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, '../dist');
const BUDGET_BYTES = 200 * 1024;

function readOrFail(path) {
  try {
    return readFileSync(path, 'utf8');
  } catch {
    console.error(`✗ ${path} not found — run \`npm run build\` first.`);
    process.exit(2);
  }
}

const html = readOrFail(join(dist, 'index.html'));
const assets = new Set();

for (const match of html.matchAll(/<script[^>]+src="([^"]+\.js)"/g)) assets.add(match[1]);
for (const match of html.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="([^"]+\.js)"/g)) {
  assets.add(match[1]);
}
// Handle attribute order variations.
for (const match of html.matchAll(/<link[^>]+href="([^"]+\.js)"[^>]+rel="modulepreload"/g)) {
  assets.add(match[1]);
}

if (assets.size === 0) {
  console.error('✗ No entry scripts found in dist/index.html');
  process.exit(2);
}

let total = 0;
const rows = [];
for (const asset of assets) {
  const file = join(dist, asset.replace(/^\//, ''));
  const raw = statSync(file).size;
  const gzip = gzipSync(readFileSync(file)).length;
  total += gzip;
  rows.push({ asset, raw, gzip });
}

rows.sort((a, b) => b.gzip - a.gzip);
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

console.log('\nInitial JS (gzip):');
for (const row of rows) {
  console.log(`  ${row.asset.padEnd(42)} ${kb(row.gzip).padStart(10)}  (raw ${kb(row.raw)})`);
}
console.log(`  ${'TOTAL'.padEnd(42)} ${kb(total).padStart(10)} / budget ${kb(BUDGET_BYTES)}`);

const adminChunks = [];
try {
  const manifest = JSON.parse(readFileSync(join(dist, '.vite/manifest.json'), 'utf8'));
  for (const [name, entry] of Object.entries(manifest)) {
    if (name.includes('admin')) adminChunks.push(entry.file);
  }
} catch {
  // Manifest is optional; the admin split is verified in the Playwright run.
}
if (adminChunks.length)
  console.log(`  admin bundle (lazy, not counted): ${adminChunks.join(', ')}`);

if (total > BUDGET_BYTES) {
  console.error(`\n✗ Initial JS ${kb(total)} exceeds the ${kb(BUDGET_BYTES)} budget.`);
  process.exit(1);
}
console.log('\n✓ Within budget.\n');
