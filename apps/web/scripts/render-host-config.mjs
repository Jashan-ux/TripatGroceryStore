#!/usr/bin/env node
/**
 * Render host config from a template.
 *
 * Neither Vercel nor Netlify interpolates environment variables inside its
 * config file, and the backend origin differs per environment. So the templates
 * live in git (`vercel.json.template`, `netlify.toml.template`) and this script
 * writes the real file at deploy time.
 *
 *   API_ORIGIN=https://api.staging.example node scripts/render-host-config.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const origin = (process.env.API_ORIGIN ?? '').replace(/\/$/, '');

if (!origin) {
  console.error('✗ API_ORIGIN is required, e.g. https://tripat-api.onrender.com');
  process.exit(2);
}
if (!/^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(origin)) {
  console.error(`✗ API_ORIGIN must be an https origin without a path: ${origin}`);
  process.exit(2);
}

for (const [template, output] of [
  ['vercel.json.template', 'vercel.json'],
  ['netlify.toml.template', 'netlify.toml'],
]) {
  const source = readFileSync(join(root, template), 'utf8');
  if (!source.includes('__API_ORIGIN__')) {
    console.error(`✗ ${template} has no __API_ORIGIN__ placeholder`);
    process.exit(2);
  }
  writeFileSync(join(root, output), source.replaceAll('__API_ORIGIN__', origin));
  console.log(`✓ ${output} → ${origin}`);
}
