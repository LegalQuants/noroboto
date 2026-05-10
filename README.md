# No Roboto

Proof-of-concept showing that hidden text can be embedded in a `.docx` so it
renders to a human reader (or stays fully invisible) while still being part of
the document text stream that LLM agents and other text extractors will ingest.
The motivating scenario is legal-tech e-signing, where a payload smuggled into
a contract could be acted on by an LLM agent without the human signer ever
seeing it.

See [`FRONTEND-MASTER-PLAN.md`](./FRONTEND-MASTER-PLAN.md) for the design and
[`CHANGELOG.md`](./CHANGELOG.md) for phase-by-phase progress.

## Stack

- **Backend:** Flask (Python 3.10+), single process, in-memory document store.
- **Frontend:** Vanilla JS + [Superdoc](https://github.com/superdoc-dev/superdoc)
  vendored locally via esbuild — zero CDN dependency at runtime.
- **Injection:** Server-side `zipfile` + `xml.etree.ElementTree`. A hidden
  `<w:r>` with `w:vanish` (and white color as belt-and-braces) is appended to
  `word/document.xml`.

## Running

First-time setup (Python venv + Node toolchain for the vendored Superdoc
bundle):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install
npm run build:vendor      # writes static/vendor/superdoc.{mjs,css}
```

Then start the server:

```bash
.venv/bin/python app.py
```

Open http://127.0.0.1:5000 in a browser.

The server listens on `127.0.0.1:5000` with Flask's debug reloader enabled.
You only need to rerun `npm run build:vendor` after bumping the `superdoc`
dependency in `package.json` or changing `scripts/build-vendor.mjs`.

## Using the app

1. The page loads with `cornellNDA.docx` rendered inside Superdoc.
2. **Highlight** any text in the document.
3. Click **Show highlighted text** — a JS alert displays the current selection.
4. Drag a different `.docx` onto the **dropzone** — the viewer reloads with
   the new file. Non-`.docx` files are rejected.
5. Click **Inject payload** — the server appends the hidden banner
   `❌ YOU HAVE BEEN HACKED ❌` (plus the echoed selection) to
   `word/document.xml` and writes the result to `payloadAdded.docx` at the
   repo root. The viewer re-renders (nothing visibly changes), an alert shows
   the selection + banner, and a **Proof of injection** panel appears below
   the viewer with:
   - the **extracted text** view (what an LLM-style text extractor sees —
     the hidden banner is visible here),
   - the **injected XML** view (the literal `<w:p>` subtree appended), and
   - a **Download** button for `payloadAdded.docx`.

## Verifying the payload

The **Proof of injection** panel in the UI already shows both views, but you
can verify externally too — `payloadAdded.docx` is also reachable at
`GET /payload-added`:

```bash
curl -s http://127.0.0.1:5000/payload-added -o out.docx
unzip -p out.docx word/document.xml | grep -c 'YOU HAVE BEEN HACKED'   # → 1
unzip -p out.docx word/document.xml | grep -c 'w:vanish'               # → 1
```

Open `out.docx` in Word — the hidden run is not visible.

## HTTP API

| Method | Path             | Purpose                                                                                                                                |
| ------ | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/`              | Render the single-page app.                                                                                                            |
| GET    | `/current-doc`   | Return the active `.docx` bytes.                                                                                                       |
| POST   | `/upload`        | `multipart/form-data` with field `file`; replaces the active doc.                                                                      |
| POST   | `/inject`        | JSON `{ "selected_text": "..." }`. Appends a hidden run; writes `payloadAdded.docx`; returns `extracted_text`, `injected_xml`, and `download_url`. |
| GET    | `/payload-added` | Download the most recently injected `payloadAdded.docx` (404 until `/inject` has run at least once).                                   |

State is in-memory and process-local — restarting the server resets to
`cornellNDA.docx`.

## Layout

```
app.py                       Flask app + payload injector
templates/index.html         Page shell, Superdoc mount points, buttons, dropzone, proof panel
static/app.js                Superdoc init, selection capture, button + drop handlers, proof panel
static/app.css               Minimal layout
static/vendor/superdoc.mjs   Vendored Superdoc bundle (built; gitignored if you prefer)
static/vendor/superdoc.css   Vendored Superdoc stylesheet
scripts/build-vendor.mjs     esbuild script that produces static/vendor/*
scripts/stub-hocuspocus.mjs  No-op shim for the @hocuspocus/provider collab module
package.json                 Pins superdoc + esbuild for the vendor build
cornellNDA.docx              Default sample document
payloadAdded.docx            Ground-truth artifact written on every /inject (gitignored)
docs/                        Work-process notes and references
CHANGELOG.md                 Phase-by-phase changes
FRONTEND-MASTER-PLAN.md      Design doc
```

## Notes & limitations

- Single-user, single-document, no persistence.
- Superdoc's selection API surface isn't fully documented; the frontend
  reaches into `superdoc.activeEditor.state.selection` and falls back to
  `window.getSelection()`. Verified at runtime in the browser.
- Superdoc is AGPL-3.0; review licensing before any non-PoC use.
- This repo is a security demonstration. Do not use the injection technique
  against documents you don't own.
