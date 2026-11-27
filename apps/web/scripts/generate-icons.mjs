#!/usr/bin/env node
/**
 * Generate every PWA icon from the brand artwork.
 *
 *   npm run icons   (in apps/web)
 *
 * Inputs:  public/brand/logo.svg  (placeholder until the owner's file arrives)
 * Outputs: public/icons/icon-192.png, icon-512.png, icon-maskable-512.png,
 *          apple-touch-icon.png, public/favicon.svg
 *
 * The maskable variant keeps the artwork inside the 80% safe zone required by
 * Android, so the launcher never crops the wordmark.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const source = join(root, 'public/brand/logo.svg');
const outDir = join(root, 'public/icons');

mkdirSync(outDir, { recursive: true });

const svg = readFileSync(source);

async function png(size, file, { padding = 0, background } = {}) {
  const inner = Math.round(size * (1 - padding * 2));
  const logo = await sharp(svg, { density: 512 }).resize(inner, inner).png().toBuffer();
  const canvas = sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: background ?? { r: 0, g: 0, b: 0, alpha: 0 },
    },
  });
  const offset = Math.round((size - inner) / 2);
  await canvas
    .composite([{ input: logo, top: offset, left: offset }])
    .png({ compressionLevel: 9 })
    .toFile(join(outDir, file));
  console.log(`  ${file} (${size}×${size})`);
}

console.log('Generating PWA icons from public/brand/logo.svg');
await png(192, 'icon-192.png');
await png(512, 'icon-512.png');
// Maskable: 20% padding on each side + solid brand background.
await png(512, 'icon-maskable-512.png', { padding: 0.2, background: '#B91C1C' });
await png(180, 'apple-touch-icon.png', { background: '#FFFFFF' });
await png(96, 'icon-96.png');

// Favicon: reuse the artwork but keep it as SVG (crisp at every size).
writeFileSync(join(root, 'public/favicon.svg'), svg);
console.log('  favicon.svg');
console.log('Done.');
