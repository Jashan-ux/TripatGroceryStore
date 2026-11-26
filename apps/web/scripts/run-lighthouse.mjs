#!/usr/bin/env node
/**
 * Build-time Lighthouse smoke audit for the production bundle. The separate
 * deployment-host audit is still required before release; this catches mobile
 * performance and accessibility regressions in CI without staging credentials.
 */
import { writeFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';

import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';
import { chromium } from '@playwright/test';

const port = Number(process.env.LIGHTHOUSE_PORT ?? 4173);
const url = process.env.LIGHTHOUSE_URL ?? `http://127.0.0.1:${port}/contact`;
const reportPath = process.env.LIGHTHOUSE_REPORT ?? '/tmp/tripat-lighthouse-report.html';
const preview = new URL(`http://127.0.0.1:${port}`);

const viteBin = resolve(process.cwd(), '../../node_modules/vite/bin/vite.js');
const server = spawn(
  process.execPath,
  [viteBin, 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'],
  { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'pipe'] },
);
let serverOutput = '';
server.stdout.setEncoding('utf8').on('data', (chunk) => (serverOutput += chunk));
server.stderr.setEncoding('utf8').on('data', (chunk) => (serverOutput += chunk));

let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (server.exitCode !== null) {
      throw new Error(`Vite preview exited before becoming ready:\n${serverOutput}`);
    }
    try {
      const response = await fetch(preview);
      ready = response.ok;
      if (ready) break;
    } catch {
      // The preview server is still starting.
    }
    await delay(500);
  }
  if (!ready) throw new Error(`Vite preview did not become ready:\n${serverOutput}`);

  browser = await launch({
    chromePath: chromium.executablePath(),
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage'],
  });
  const result = await lighthouse(url, {
    port: browser.port,
    output: 'html',
    onlyCategories: ['performance', 'accessibility'],
    formFactor: 'mobile',
    throttlingMethod: 'simulate',
    screenEmulation: {
      mobile: true,
      width: 360,
      height: 800,
      deviceScaleFactor: 1,
      disabled: false,
    },
    logLevel: 'error',
  });
  if (!result) throw new Error('Lighthouse returned no report.');

  await writeFile(reportPath, result.report);
  const performance = Math.round((result.lhr.categories.performance?.score ?? 0) * 100);
  const accessibility = Math.round((result.lhr.categories.accessibility?.score ?? 0) * 100);
  console.log(
    `Mobile simulated-4G Lighthouse: Performance ${performance}, Accessibility ${accessibility}`,
  );
  console.log(`Full HTML report: ${reportPath}`);
  const summary = [
    '### Lighthouse mobile simulated-4G',
    '',
    `- Performance: **${performance}** (target ≥ 85)`,
    `- Accessibility: **${accessibility}** (target ≥ 95)`,
    `- HTML report: \`${reportPath}\` (also uploaded as a workflow artifact)`,
  ].join('\n');
  if (process.env.GITHUB_STEP_SUMMARY) {
    const { appendFile } = await import('node:fs/promises');
    await appendFile(process.env.GITHUB_STEP_SUMMARY, `${summary}\n`);
  }

  if (performance < 85 || accessibility < 95) {
    const message = `Lighthouse below target: Performance ${performance}/85, Accessibility ${accessibility}/95.`;
    console.error(message);
    process.stderr.write(`::error title=Lighthouse scores below target::${message}\n`);
    process.exitCode = 1;
  }
} finally {
  await browser?.kill();
  server.kill('SIGTERM');
}
