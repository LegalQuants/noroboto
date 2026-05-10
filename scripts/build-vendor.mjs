// Build a single self-contained Superdoc ESM bundle into static/vendor/
// so the front-end has no CDN dependency at runtime.

import { mkdir, copyFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const OUT_DIR = resolve(ROOT, 'static/vendor');

await mkdir(OUT_DIR, { recursive: true });

// Re-export only what app.js needs. A tiny entry shim keeps the bundle small
// and lets esbuild tree-shake everything we don't use.
const entry = resolve(OUT_DIR, '__entry.mjs');
await (await import('node:fs/promises')).writeFile(
  entry,
  "export { SuperDoc } from 'superdoc';\n",
);

await build({
  entryPoints: [entry],
  outfile: resolve(OUT_DIR, 'superdoc.mjs'),
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: ['es2022'],
  minify: true,
  sourcemap: false,
  legalComments: 'none',
  // Hocuspocus is a collaborative-editing provider; we never instantiate it,
  // so stub it out to avoid pulling in y-protocols / ws polyfills.
  alias: { '@hocuspocus/provider': resolve(HERE, 'stub-hocuspocus.mjs') },
  define: { 'process.env.NODE_ENV': '"production"' },
  loader: { '.svg': 'dataurl', '.png': 'dataurl' },
});

// Ship Superdoc's stylesheet alongside the JS so index.html can load it from
// the same /static/vendor/ path.
await copyFile(
  resolve(ROOT, 'node_modules/superdoc/dist/style.css'),
  resolve(OUT_DIR, 'superdoc.css'),
);

console.log('Vendored bundle written to', OUT_DIR);
