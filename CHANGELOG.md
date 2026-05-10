# Changelog

## [Unreleased]

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
