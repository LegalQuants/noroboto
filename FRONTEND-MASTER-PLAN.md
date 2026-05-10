# Master Plan — No Roboto PoC

## Context

The project (per `CLAUDE.md`) is a proof-of-concept showing that a `.docx` can carry text that renders to a human reader but is invisible to LLM agents reading the document text stream. The brief lays out four phases: (1) render `cornellNDA.docx` in the browser via [Superdoc](https://github.com/superdoc-dev/superdoc); (2) read the user's text selection and surface it in a JS alert; (3) add a drag-drop dropzone for new `.docx` uploads; (4) add an "Inject payload" button that appends hidden text (`❌ YOU HAVE BEEN HACKED ❌`) into the file and re-renders it.

The repo currently has only the project brief (`CLAUDE.md`), the sample `cornellNDA.docx`, and `.gitignore`. No application code exists yet — this plan starts from scratch.

User decisions captured during planning:
- Try Superdoc's editor API first for selection; fall back to `window.getSelection()`.
- Flask serves `cornellNDA.docx` as the default rendered document on page load.
- Payload injection happens server-side in Python.

## Architecture

```
┌──────────────────────────────────────┐         ┌────────────────────────────┐
│ Browser (single-page, vanilla JS)    │         │ Flask app (app.py, :5000)  │
│  - Superdoc via CDN (UMD bundle)     │ ◀─────▶ │  GET  /            index   │
│  - Drag-drop zone                    │         │  GET  /static/...   assets │
│  - "Show highlighted text" button    │         │  GET  /current-doc  active │
│  - "Inject payload" button           │         │  POST /upload      stash   │
│                                      │         │  POST /inject      mutate  │
└──────────────────────────────────────┘         └────────────────────────────┘
                                                          │
                                                          ▼
                                                  In-memory docx store
                                                  (single active doc, bytes)
```

Single-process, single-user PoC — no auth, no persistence beyond process memory.

## Implementation

### Files to create

- `app.py` — Flask app, routes, in-memory docx store, payload injector.
- `templates/index.html` — page shell, Superdoc mount points, buttons, dropzone.
- `static/app.js` — Superdoc init, selection capture, button handlers, drag-drop.
- `static/app.css` — minimal layout (toolbar / editor / dropzone).
- `requirements.txt` — `flask`.
- `docs/` — work-process notes per the brief's documentation requirement.
- `CHANGELOG.md` — updated at each phase per the brief.

### Backend (`app.py`)

Routes:
- `GET /` → render `index.html`.
- `GET /current-doc` → return the active `.docx` bytes with `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`. On first request, lazy-loads `cornellNDA.docx` from disk into the in-memory store.
- `POST /upload` → accept `multipart/form-data` with a `.docx` file; reject anything whose filename doesn't end in `.docx` or whose magic bytes aren't a ZIP (`PK\x03\x04`); replace the active doc bytes; respond `204`.
- `POST /inject` → JSON body `{ "selected_text": "..." }`; mutate the active doc to append a hidden run carrying `❌ YOU HAVE BEEN HACKED ❌` plus the echoed selected text; respond `204`. Frontend then re-fetches `/current-doc`.

Injection (`inject_payload(docx_bytes, selection_text) -> bytes`):
- Open the docx as a `zipfile.ZipFile` in memory.
- Parse `word/document.xml` with `xml.etree.ElementTree`, namespace `w = http://schemas.openxmlformats.org/wordprocessingml/2006/main`.
- Find `w:body` and append a new `w:p` containing a `w:r` with `w:rPr` that sets `w:vanish/` (Word's "hidden text" run property) and `w:color w:val="FFFFFF"` as a belt-and-braces measure.
- The `w:r` contains a `w:t xml:space="preserve"` with the payload string. UTF-8 is the default XML encoding so the ❌ emoji round-trips correctly; ensure the serializer is invoked with `encoding="utf-8"` and `xml_declaration=True`.
- Re-zip all parts, returning the new bytes. Use `ZIP_DEFLATED`.

Notes on the chosen technique: `w:vanish` is the OOXML-native "hidden text" toggle. Word renders nothing for it by default, but the text is present in `document.xml` and is exactly what an unsuspecting LLM ingesting the doc's text stream would see — which is the point of the demo. (The brief says "invisible to the user and from LLM agents", but the demonstrable injection here is the inverse: visible to the LLM, invisible to the user. That's the actual deceptive case for legal-tech e-signing scenarios. Flag this framing to the user during implementation if they intended the symmetric case.)

### Frontend (`static/app.js`)

Init:
```js
const superdoc = new SuperDoc({
  selector: '#superdoc',
  toolbar: '#superdoc-toolbar',
  document: '/current-doc',
  documentMode: 'editing',
});
```

Selection capture (try Superdoc first, fall back to native):
```js
function getSelectedText() {
  // Superdoc is ProseMirror/Tiptap-based; the active editor exposes state.selection.
  const editor = superdoc?.activeEditor ?? superdoc?.getInstance?.()?.activeEditor;
  if (editor?.state) {
    const { from, to } = editor.state.selection;
    if (from !== to) return editor.state.doc.textBetween(from, to, ' ');
  }
  return window.getSelection()?.toString() ?? '';
}
```
The exact path to the editor instance needs to be verified at runtime by `console.log(superdoc)` once the bundle is loaded — Superdoc's public API surface for this isn't fully documented. The fallback to `window.getSelection()` covers the case where the internal handle moves.

Buttons:
- **Show highlighted text** → `alert(getSelectedText() || '(no selection)')`.
- **Inject payload** → capture `getSelectedText()`, `POST /inject` with it, then on success rebuild the SuperDoc instance pointing at `/current-doc?t=${Date.now()}` (cache-bust) and `alert(selected + '\n\n❌ YOU HAVE BEEN HACKED ❌')`.

Dropzone:
- A `<div>` with `dragover`/`drop` handlers, `.docx` extension check on the dropped file, `POST /upload` as multipart, then re-mount SuperDoc against `/current-doc`.

### `index.html`

Two containers (`#superdoc-toolbar`, `#superdoc`), two buttons, one dropzone, the Superdoc CDN tags:
```html
<link rel="stylesheet" href="https://unpkg.com/superdoc/dist/style.css" />
<script type="module" src="https://unpkg.com/superdoc/dist/superdoc.umd.js"></script>
```

## Verification

End-to-end manual test (no automated tests in scope for a PoC):

1. `pip install -r requirements.txt && python app.py` — server comes up on `:5000`.
2. Open `http://localhost:5000` — `cornellNDA.docx` renders inside Superdoc.
3. Highlight a sentence; click **Show highlighted text** — alert shows the exact selection.
4. Drag a different `.docx` onto the dropzone — viewer reloads with the new file. Drop a `.txt` — rejected with an alert.
5. Highlight some text; click **Inject payload** — alert shows `<selection>\n\n❌ YOU HAVE BEEN HACKED ❌`. Viewer re-renders; nothing visible changes.
6. Confirm the payload is actually in the file: `curl -s http://localhost:5000/current-doc -o out.docx && unzip -p out.docx word/document.xml | grep -c 'YOU HAVE BEEN HACKED'` → `1`.
7. Confirm a typical LLM-ingest path sees the hidden text: same `unzip -p ... | grep -o 'HACKED'` returns a hit while opening `out.docx` in Word shows nothing extra.

## Phase 5 — Prove the payload is really in the file

**Problem.** Phases 1–4 inject the hidden run server-side and re-render the
doc in Superdoc. Superdoc strips the hidden run from its rendered DOM (that's
the whole point of `w:vanish`), so the browser's web inspector shows nothing
useful — the user has no way to verify the injection happened without leaving
the app and running `unzip -p` manually. Phase 5 closes that gap.

### Output artifact

On every successful `/inject`, the server writes the modified bytes to
`payloadAdded.docx` (sibling of `cornellNDA.docx` at the repo root, gitignored)
in addition to mutating the in-memory active doc. The file is the ground truth:
the user can open it in Word, attach it to an email, or drop it into an LLM
chat to demonstrate the asymmetric visibility.

### New backend additions (`app.py`)

- In `/inject`, after `_set_active_doc(new_bytes)`, also
  `(REPO_ROOT / "payloadAdded.docx").write_bytes(new_bytes)`.
- Extract the text-only view of `word/document.xml` for the response:
  walk all `w:t` elements (this is what `python-docx`, `docx2txt`, and most
  LLM-feeding text extractors see) and concatenate their contents. Include
  this in the JSON response as `extracted_text` so the front-end can show it.
- Locate the injected `<w:r>` and serialize just that subtree as
  `injected_xml` in the response, so the user can see the exact OOXML payload
  that was appended.
- New route `GET /payload-added` → serves `payloadAdded.docx` with
  `Content-Disposition: attachment; filename="payloadAdded.docx"`. Returns
  `404` if the user hasn't injected yet.

### New frontend additions (`static/app.js`, `templates/index.html`)

Add a collapsible **Proof** panel beneath the Superdoc viewer with three
elements, populated after `/inject` succeeds:

1. **Download** button → links to `/payload-added`. Lets the user grab the
   file for external verification.
2. **Extracted text** `<pre>` → renders the `extracted_text` string from the
   inject response. The hidden banner appears here because text extractors
   don't honor `w:vanish`. This is the "what an LLM sees" view.
3. **Injected XML** `<pre>` → renders the `injected_xml` snippet, syntax
   shown literally. This is the "what got added to the docx" view.

The existing post-injection alert stays but becomes a confirmation; the panel
is where the real demonstration happens.

### Why this works as proof

- **Browser view (Superdoc)**: payload is invisible → human signer doesn't see
  it.
- **Extracted-text view (Proof panel)**: payload is visible → LLM agent sees
  it.
- **Downloaded file**: payload survives outside the demo, openable in Word
  (still invisible) and grep-able from the shell (visible). The file artifact
  prevents accusations that the proof panel is hand-waving.

### Files changed/added

- `app.py` — `/inject` writes `payloadAdded.docx` + returns extracted text and
  injected XML; new `/payload-added` download route.
- `static/app.js` — populate the new Proof panel after injection.
- `templates/index.html` — markup for the panel and a hidden Download button.
- `static/app.css` — styling for the panel.
- `.gitignore` — add `payloadAdded.docx`.

### Verification (Phase 5)

1. Boot server, render `cornellNDA.docx`.
2. Highlight a sentence, click **Inject payload**.
3. Proof panel populates: extracted text contains `YOU HAVE BEEN HACKED` and
   the echoed selection; injected XML shows the `<w:r>` with `w:vanish`.
4. Click **Download** — `payloadAdded.docx` saves locally.
5. `unzip -p payloadAdded.docx word/document.xml | grep -c 'HACKED'` → `1`.
6. Open `payloadAdded.docx` in Word — no visible change vs. the original.

## Out of scope (deliberate)

- Persistence across server restarts.
- Multi-user / multi-document state.
- PDF support (the brief mentions it as a stretch goal but only `.docx` is required by the phase checklist).
- Tests, CI, lint config.
- Auth, CSRF, file-size limits beyond the obvious sanity checks.
