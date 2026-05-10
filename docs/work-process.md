# Work process

Links and notes accumulated while building the No Roboto PoC.

## Superdoc
- Repo: https://github.com/superdoc-dev/superdoc
- Docs: https://docs.superdoc.dev
- CDN bundle (used here): https://unpkg.com/superdoc/dist/superdoc.umd.js
- CDN styles: https://unpkg.com/superdoc/dist/style.css
- Examples: https://github.com/superdoc-dev/superdoc/tree/main/examples
- Demos: https://github.com/superdoc-dev/superdoc/tree/main/demos
- License: AGPL-3.0 (commercial license available)

Notes:
- Superdoc is built on ProseMirror/Tiptap; the active editor is reachable via `superdoc.activeEditor` (verify at runtime — public API is partly undocumented).
- `documentMode: 'editing' | 'viewing'`. The PoC uses `editing`.
- `document` constructor option accepts a URL, `File`, `Blob`, or `ArrayBuffer`.

## OOXML hidden text
- `w:vanish` (run property) — Word's native "hidden text" toggle. Suppresses display, retains text in `word/document.xml`.
- Combined with `w:color w:val="FFFFFF"` as belt-and-braces in case a renderer ignores `w:vanish`.
- Spec reference: ECMA-376 §17.3.2.45 (`vanish`).

## Backend choice
- Flask + vanilla JS (CDN Superdoc). No bundler.
- Single in-memory document store keyed by process; no persistence.

## Architecture
See `FRONTEND-MASTER-PLAN.md` at the repo root.
