# Changelog

## [Unreleased]

### Phase 1 — Render document
- Bring `cornellNDA.docx` in from disk; serve it via Flask at `/current-doc`.
- Render the active document in the browser via Superdoc (UMD bundle, vanilla JS).

### Phase 2 — Highlight + alert
- "Show highlighted text" button reads the active selection (Superdoc editor state, falls back to `window.getSelection()`).
- Click fires a JS alert with the selected text.

### Phase 3 — Dropzone
- Drag-and-drop area accepts `.docx` only (extension + ZIP magic check).
- Dropped file replaces the active document and re-mounts Superdoc.

### Phase 4 — Inject hidden payload
- "Inject payload" button POSTs the current selection to `/inject`.
- Server appends a hidden `<w:r>` (with `w:vanish` + white color) carrying `❌ YOU HAVE BEEN HACKED ❌` plus the echoed selection to `word/document.xml`.
- Viewer re-renders; alert shows selection + banner.
