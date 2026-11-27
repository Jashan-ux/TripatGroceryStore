/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as {
  version: string;
};

/** Backend origin for the dev server proxy. In production Vercel rewrites /api/*. */
const API_ORIGIN = process.env.VITE_PROXY_API_ORIGIN ?? 'http://127.0.0.1:8000';

export default defineConfig({
  // Keep the Supabase NEXT_PUBLIC_* keys usable in this Vite SPA without exposing
  // unrelated NEXT_PUBLIC_* variables; VITE_* remains the default app prefix.
  envPrefix: ['VITE_', 'NEXT_PUBLIC_SUPABASE_'],
  plugins: [
    react(),
    VitePWA({
      // `prompt`: a new deploy never swaps the app under the user's feet. The
      // app shows an "update available" toast; see src/lib/serviceWorker.ts.
      registerType: 'prompt',
      injectRegister: false,
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png', 'robots.txt'],
      manifest: {
        id: '/',
        name: 'Tripat Pansari · MSG Store',
        short_name: 'MSG',
        description:
          'Groceries, herbs, spices and daily essentials delivered in Mandi Dabwali. Cash on delivery.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#FFFFFF',
        theme_color: '#B91C1C',
        lang: 'en-IN',
        dir: 'ltr',
        categories: ['shopping', 'food'],
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          {
            src: '/icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
        shortcuts: [
          { name: 'My orders', url: '/orders', description: 'Track a delivery' },
          { name: 'Cart', url: '/cart', description: 'Finish your order' },
        ],
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,png,webp,woff2}'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
      devOptions: { enabled: false },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    // The sandbox preview proxies to this port; bind all interfaces and accept
    // the preview hostname.
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': { target: API_ORIGIN, changeOrigin: true },
      '/healthz': { target: API_ORIGIN, changeOrigin: true },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    allowedHosts: true,
  },
  build: {
    target: 'es2020',
    cssCodeSplit: true,
    sourcemap: false,
    reportCompressedSize: true,
    rollupOptions: {
      output: {
        // Only what the first paint needs may live in a chunk the entry
        // preloads. Form/validation code is reachable from the lazy auth pages
        // and Supabase from the sign-in client, so they get their own chunks and
        // load when a route actually asks for them.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('react-router')) return 'router';
          if (id.includes('@tanstack')) return 'query';
          if (id.includes('lucide-react')) return 'icons';
          if (id.includes('zod') || id.includes('react-hook-form') || id.includes('@hookform')) {
            return 'forms';
          }
          if (id.includes('@supabase')) return 'supabase';
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/admin/**'],
    },
  },
});
