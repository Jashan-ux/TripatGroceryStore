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
  const performanceScore = result.lhr.categories.performance?.score;
  const accessibilityScore = result.lhr.categories.accessibility?.score;
  const performance = Number.isFinite(performanceScore) ? Math.round(performanceScore * 100) : null;
  const accessibility = Number.isFinite(accessibilityScore)
    ? Math.round(accessibilityScore * 100)
    : null;
  const scoreLabel = (score) => (score === null ? 'unavailable' : String(score));
  console.log(
    `Mobile simulated-4G Lighthouse: Performance ${scoreLabel(performance)}, Accessibility ${scoreLabel(accessibility)}`,
  );
  console.log(`Full HTML report: ${reportPath}`);
  const weakPerformanceAudits = (result.lhr.categories.performance?.auditRefs ?? [])
    .filter((ref) => ref.weight > 0)
    .map((ref) => result.lhr.audits[ref.id])
    .filter((audit) => audit.score !== null && audit.score < 0.9)
    .map((audit) => `${audit.title}: ${audit.displayValue ?? `score ${audit.score}`}`);
  const layoutShiftSources = await readLayoutShiftSources(url);
  const summary = [
    '### Lighthouse mobile simulated-4G',
    '',
    `- Performance: **${scoreLabel(performance)}** (target ≥ 85)`,
    `- Accessibility: **${scoreLabel(accessibility)}** (target ≥ 95)`,
    ...(weakPerformanceAudits.length
      ? [
          '',
          '**Performance audits below 90%:**',
          ...weakPerformanceAudits.map((audit) => `- ${audit}`),
        ]
      : []),
    ...(layoutShiftSources.length
      ? [
          '',
          '**Largest layout-shift elements:**',
          ...layoutShiftSources.map((source) => `- \`${source}\``),
        ]
      : []),
    '',
    `- HTML report: \`${reportPath}\` (also uploaded as a workflow artifact)`,
  ].join('\n');
  if (process.env.GITHUB_STEP_SUMMARY) {
    const { appendFile } = await import('node:fs/promises');
    await appendFile(process.env.GITHUB_STEP_SUMMARY, `${summary}\n`);
  }
  const cls = result.lhr.audits['cumulative-layout-shift']?.displayValue ?? 'n/a';
  const lcp = result.lhr.audits['largest-contentful-paint']?.displayValue ?? 'n/a';
  const tbt = result.lhr.audits['total-blocking-time']?.displayValue ?? 'n/a';
  const shiftSummary = layoutShiftSources.length
    ? `; layout-shift elements ${layoutShiftSources.join(' | ')}`
    : '';
  process.stderr.write(
    `::notice title=Lighthouse mobile metrics::Performance ${scoreLabel(performance)}; Accessibility ${scoreLabel(accessibility)}; CLS ${cls}; LCP ${lcp}; TBT ${tbt}${shiftSummary}.\n`,
  );

  const failedAudits = Object.entries(result.lhr.audits)
    .filter(([, audit]) => audit.scoreDisplayMode === 'error' || audit.errorMessage)
    .slice(0, 8)
    .map(([id, audit]) => `${id}: ${audit.errorMessage ?? audit.explanation ?? audit.title}`);
  const runtimeError = result.lhr.runtimeError
    ? `${result.lhr.runtimeError.code}: ${result.lhr.runtimeError.message}`
    : '';
  if (performance === null || performance < 85 || accessibility === null || accessibility < 95) {
    const details = [
      ...(runtimeError ? [`Lighthouse runtime error: ${runtimeError}`] : []),
      ...failedAudits,
      ...weakPerformanceAudits.slice(0, 5),
      ...layoutShiftSources.map((source) => `layout shift: ${source}`),
    ].join('; ');
    const message =
      `Lighthouse below target: Performance ${scoreLabel(performance)}/85, Accessibility ${scoreLabel(accessibility)}/95. ${details}`.slice(
        0,
        2000,
      );
    console.error(message);
    process.stderr.write(`::error title=Lighthouse scores below target::${message}\n`);
    process.exitCode = 1;
  }
} finally {
  await browser?.kill();
  server.kill('SIGTERM');
}

async function readLayoutShiftSources(targetUrl) {
  let probe;
  try {
    probe = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const page = await probe.newPage({ viewport: { width: 360, height: 800 } });
    await page.addInitScript(() => {
      window.__layoutShiftEntries = [];
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.hadRecentInput) continue;
          window.__layoutShiftEntries.push({
            value: entry.value,
            sources: (entry.sources ?? []).map(({ node, previousRect, currentRect }) => ({
              selector: node
                ? `${node.tagName?.toLowerCase() ?? ''}${node.id ? `#${node.id}` : ''}${
                    node.classList?.length
                      ? `.${Array.from(node.classList).slice(0, 2).join('.')}`
                      : ''
                  }`
                : 'unknown node',
              text: node?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) ?? '',
              from: previousRect
                ? [previousRect.x, previousRect.y, previousRect.width, previousRect.height]
                : [],
              to: currentRect
                ? [currentRect.x, currentRect.y, currentRect.width, currentRect.height]
                : [],
            })),
          });
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3500);
    return await page.evaluate(() =>
      window.__layoutShiftEntries
        .flatMap((entry) =>
          entry.sources.map(
            (source) => `${entry.value.toFixed(3)}: ${source.selector} “${source.text}”`,
          ),
        )
        .slice(0, 8),
    );
  } catch (error) {
    console.warn(`Could not collect CLS element sources: ${error.message}`);
    return [];
  } finally {
    await probe?.close();
  }
}
