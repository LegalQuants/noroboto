# Changelog

## [Unreleased]

### 2026-05-10 — Vendor Superdoc locally
- Added `package.json` pinning `superdoc@1.32.0` and `esbuild@^0.24`.
- `scripts/build-vendor.mjs` (run via `npm run build:vendor`) bundles
  Superdoc into a single self-contained ESM file at
  `static/vendor/superdoc.mjs` (+ `superdoc.css`).
- `scripts/stub-hocuspocus.mjs` replaces `@hocuspocus/provider` with a no-op,
  keeping y-protocols / websocket code out of the bundle (we don't use the
  collab feature).
- `static/app.js` now imports from `/static/vendor/superdoc.mjs`;
  `templates/index.html` loads the local CSS. Zero CDN dependency at
  runtime.
- Motivation: three separate CDN failures in a row (esm.sh
  `ERR_CONNECTION_CLOSED` on a transitive `@hocuspocus/provider` URL,
  `?bundle` mode inlining a second Vue and breaking template refs, jsdelivr
  `+esm` 404 on `@lifeomic/attempt`). Vendoring eliminates the class of bug.
- `.gitignore`: `node_modules/`, `package-lock.json`, the build's internal
  entry shim.

### 2026-05-10 — Phase 5: prove the payload is really in the file
- `POST /inject` now also writes `payloadAdded.docx` to the repo root and
  returns `extracted_text` (concatenated `w:t` content — what an LLM sees)
  and `injected_xml` (the appended `<w:p>` subtree) in its JSON response.
- New route `GET /payload-added` downloads the most recent
  `payloadAdded.docx` (`404` until the first injection).
- New **Proof of injection** panel in the UI shows the extracted-text view,
  the injected-XML view, and a Download button — closing the gap where
  Superdoc's rendered DOM hides the hidden run from DevTools.
- `.gitignore`: `payloadAdded.docx`.

### 2026-05-10 — Document rendering fix (browser-verified)
- Switched Superdoc loader from non-existent UMD bundle to ESM via
  `https://esm.sh/superdoc@1.32.0` (resolves the CORS-blocked
  `superdoc.umd.js` 404 reported in `ERRORS.md`).
- Removed the now-redundant `window.SuperDoc` polling in `static/app.js`.
- Added a `204 /favicon.ico` handler to silence the unrelated DevTools 404.
- **Browser-verified end-to-end**: document renders, "Show highlighted text"
  alerts the current selection, "Inject payload" appends the hidden banner
  and re-renders the document, drag-and-drop replaces the active file.

### Phase 1 — Render document ✅
- Bring `cornellNDA.docx` in from disk; serve it via Flask at `/current-doc`.
- Render the active document in the browser via Superdoc (ESM via esm.sh, vanilla JS).

### Phase 2 — Highlight + alert ✅
- "Show highlighted text" button reads the active selection (Superdoc editor state, falls back to `window.getSelection()`).
- Click fires a JS alert with the selected text.

### Phase 3 — Dropzone ✅
- Drag-and-drop area accepts `.docx` only (extension + ZIP magic check).
- Dropped file replaces the active document and re-mounts Superdoc.

### Phase 4 — Inject hidden payload ✅
- "Inject payload" button POSTs the current selection to `/inject`.
- Server appends a hidden `<w:r>` (with `w:vanish` + white color) carrying `❌ YOU HAVE BEEN HACKED ❌` plus the echoed selection to `word/document.xml`.
- Viewer re-renders; alert shows selection + banner.
