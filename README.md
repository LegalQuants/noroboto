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
  loaded from CDN — no bundler.
- **Injection:** Server-side `zipfile` + `xml.etree.ElementTree`. A hidden
  `<w:r>` with `w:vanish` (and white color as belt-and-braces) is appended to
  `word/document.xml`.

## Running

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open http://127.0.0.1:5000 in a browser.

The server listens on `127.0.0.1:5000` with Flask's debug reloader enabled.

## Using the app

1. The page loads with `cornellNDA.docx` rendered inside Superdoc.
2. **Highlight** any text in the document.
3. Click **Show highlighted text** — a JS alert displays the current selection.
4. Drag a different `.docx` onto the **dropzone** — the viewer reloads with
   the new file. Non-`.docx` files are rejected.
5. Click **Inject payload** — the server appends the hidden banner
   `❌ YOU HAVE BEEN HACKED ❌` (plus the echoed selection) to
   `word/document.xml`. The viewer re-renders; nothing visibly changes. An
   alert shows the selection and banner.

## Verifying the payload

After clicking **Inject payload**, save the current doc and inspect its XML:

```bash
curl -s http://127.0.0.1:5000/current-doc -o out.docx
unzip -p out.docx word/document.xml | grep -c 'YOU HAVE BEEN HACKED'   # → 1
unzip -p out.docx word/document.xml | grep -c 'w:vanish'               # → 1
```

Open `out.docx` in Word — the hidden run is not visible.

## HTTP API

| Method | Path           | Purpose                                                              |
| ------ | -------------- | -------------------------------------------------------------------- |
| GET    | `/`            | Render the single-page app.                                          |
| GET    | `/current-doc` | Return the active `.docx` bytes.                                     |
| POST   | `/upload`      | `multipart/form-data` with field `file`; replaces the active doc.    |
| POST   | `/inject`      | JSON `{ "selected_text": "..." }`; appends a hidden run to the doc.  |

State is in-memory and process-local — restarting the server resets to
`cornellNDA.docx`.

## Layout

```
app.py                 Flask app + payload injector
templates/index.html   Page shell, Superdoc mount points, buttons, dropzone
static/app.js          Superdoc init, selection capture, button + drop handlers
static/app.css         Minimal layout
cornellNDA.docx        Default sample document
docs/                  Work-process notes and references
CHANGELOG.md           Phase-by-phase changes
FRONTEND-MASTER-PLAN.md Design doc
```

## Notes & limitations

- Single-user, single-document, no persistence.
- Superdoc's selection API surface isn't fully documented; the frontend
  reaches into `superdoc.activeEditor.state.selection` and falls back to
  `window.getSelection()`. Verified at runtime in the browser.
- Superdoc is AGPL-3.0; review licensing before any non-PoC use.
- This repo is a security demonstration. Do not use the injection technique
  against documents you don't own.
