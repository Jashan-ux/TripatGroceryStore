#!/usr/bin/env node
/** Build the workspace package's public declaration entry point. */
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const tsc = process.platform === 'win32' ? 'tsc.cmd' : 'tsc';

execFileSync(tsc, ['-p', 'tsconfig.build.json'], {
  cwd: packageRoot,
  stdio: 'inherit',
});

// TypeScript consumes the generated schema declaration but does not copy input
// .d.ts files into outDir. Preserve the relative import from dist/src/index.d.ts.
const generatedOut = join(packageRoot, 'dist', 'generated');
mkdirSync(generatedOut, { recursive: true });
copyFileSync(join(packageRoot, 'generated', 'schema.d.ts'), join(generatedOut, 'schema.d.ts'));
console.log('✓ API client declarations written to packages/api-client/dist');
