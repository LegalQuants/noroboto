"""Flask backend for the No Roboto PoC.

Serves a single-page Superdoc viewer, accepts `.docx` uploads via drag-and-drop,
and exposes an injection endpoint that smuggles a hidden run into the active
document's `word/document.xml`. State is in-memory and process-local; restarting
the server resets the active document to `cornellNDA.docx`.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

from flask import Flask, abort, jsonify, render_template, request, send_file

REPO_ROOT = Path(__file__).parent
DEFAULT_DOC = REPO_ROOT / "cornellNDA.docx"
PAYLOAD_ADDED_DOC = REPO_ROOT / "payloadAdded.docx"

# OOXML WordprocessingML namespace. Constants are duplicated as `{ns}tag` form
# (`W`) and as a prefix map (`NS`) because ElementTree wants the former for
# element construction and the latter for XPath lookups.
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORDPROCESSINGML_NS}}}"
NS = {"w": WORDPROCESSINGML_NS}
# Without this, ElementTree serializes the namespace with an auto-generated
# `ns0:` prefix, which Word tolerates but which breaks any downstream tooling
# that grep's for `w:` element names (including the verification steps in the
# README).
ET.register_namespace("w", WORDPROCESSINGML_NS)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ZIP_MAGIC = b"PK\x03\x04"
HACK_BANNER = "❌ YOU HAVE BEEN HACKED ❌"

app = Flask(__name__, static_folder="static", template_folder="templates")

# Single in-memory slot for "the document being viewed". The PoC is single-user
# by design — see README for scope. Wrapped in a dict so module-level rebinding
# isn't needed to mutate it.
_state: dict[str, bytes] = {}


def _active_doc() -> bytes:
    # Lazy-load on first access so server startup doesn't fail if the default
    # file is missing in some hypothetical environment — the error surfaces on
    # the first GET /current-doc instead.
    if "doc" not in _state:
        _state["doc"] = DEFAULT_DOC.read_bytes()
    return _state["doc"]


def _set_active_doc(payload: bytes) -> None:
    _state["doc"] = payload


def _extract_visible_text(root: ET.Element) -> str:
    """Concatenate every `w:t` text element under `root`, joined by spaces.

    This is the view that naive docx text extractors (python-docx's
    `paragraph.text`, docx2txt, most LLM ingest pipelines) produce — they
    don't honor `w:vanish`, so hidden runs leak into their output.
    """
    return " ".join((t.text or "") for t in root.iterfind(".//w:t", NS))


def inject_payload(docx_bytes: bytes, selection_text: str) -> tuple[bytes, str, str]:
    """Append a hidden run to the body. Return (new_bytes, injected_xml, extracted_text).

    The technique: a `.docx` is a ZIP of XML parts; `word/document.xml` carries
    the visible text. We append a new `<w:p><w:r>` whose `w:rPr` contains
    `w:vanish` (OOXML's "hidden text" toggle, ECMA-376 §17.3.2.45). Word renders
    nothing for it, but the text is still present in the XML stream that LLM
    text extractors and `unzip -p` will see — which is the whole point of the
    demo.

    `injected_xml` is the serialized `<w:p>` subtree that was appended (for the
    Proof panel). `extracted_text` is what `_extract_visible_text` produces
    against the modified document, i.e. what an LLM would see.
    """
    in_buf = BytesIO(docx_bytes)
    out_buf = BytesIO()

    # Read every part into memory so we can re-emit the archive after mutating
    # `word/document.xml`. ZipFile in append mode would leave the original
    # entry behind alongside the new one.
    with ZipFile(in_buf, mode="r") as src:
        names = src.namelist()
        if "word/document.xml" not in names:
            raise ValueError("word/document.xml missing from docx")
        document_xml = src.read("word/document.xml")
        other_parts = {name: src.read(name) for name in names if name != "word/document.xml"}

    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("w:body not found in document.xml")

    # Echo the selection alongside the banner so the demo can prove the
    # injected text is parameterized, not just a static string.
    payload_text = HACK_BANNER
    if selection_text:
        payload_text = f"{HACK_BANNER} :: {selection_text}"

    paragraph = ET.SubElement(body, f"{W}p")
    run = ET.SubElement(paragraph, f"{W}r")
    rpr = ET.SubElement(run, f"{W}rPr")
    ET.SubElement(rpr, f"{W}vanish")
    # Belt-and-braces: even renderers that ignore w:vanish will draw white-on-
    # white, keeping the payload off-screen.
    color = ET.SubElement(rpr, f"{W}color")
    color.set(f"{W}val", "FFFFFF")
    text = ET.SubElement(run, f"{W}t")
    # Without xml:space=preserve, leading/trailing whitespace in the run text
    # (likely once selections include spaces) gets stripped by conformant
    # parsers per the XML spec.
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = payload_text

    injected_xml = ET.tostring(paragraph, encoding="unicode")
    extracted_text = _extract_visible_text(root)
    new_document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    with ZipFile(out_buf, mode="w", compression=ZIP_DEFLATED) as dst:
        for name, data in other_parts.items():
            dst.writestr(name, data)
        dst.writestr("word/document.xml", new_document_xml)

    return out_buf.getvalue(), injected_xml, extracted_text


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    # Browsers request /favicon.ico unconditionally; respond 204 so it doesn't
    # show up as a 404 in DevTools.
    return ("", 204)


@app.get("/current-doc")
def current_doc():
    return send_file(
        BytesIO(_active_doc()),
        mimetype=DOCX_MIME,
        as_attachment=False,
        download_name="current.docx",
    )


@app.post("/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        abort(400, "no file")
    if not file.filename.lower().endswith(".docx"):
        abort(400, "only .docx accepted")
    payload = file.read()
    # Extension is user-controlled; check the ZIP magic bytes too so the
    # injection path doesn't crash on a renamed text file.
    if not payload.startswith(ZIP_MAGIC):
        abort(400, "not a valid .docx (bad zip magic)")
    _set_active_doc(payload)
    return ("", 204)


@app.post("/inject")
def inject():
    body = request.get_json(silent=True) or {}
    selection = (body.get("selected_text") or "").strip()
    new_bytes, injected_xml, extracted_text = inject_payload(_active_doc(), selection)
    _set_active_doc(new_bytes)
    # Phase 5: write a ground-truth artifact to disk so the user (or a
    # downstream tool) can verify the payload without going through the
    # Superdoc-rendered DOM, which strips hidden runs.
    PAYLOAD_ADDED_DOC.write_bytes(new_bytes)
    return jsonify({
        "ok": True,
        "banner": HACK_BANNER,
        "selected_text": selection,
        "injected_xml": injected_xml,
        "extracted_text": extracted_text,
        "download_url": "/payload-added",
    })


@app.get("/payload-added")
def payload_added():
    if not PAYLOAD_ADDED_DOC.exists():
        abort(404, "no payloadAdded.docx yet — run /inject first")
    return send_file(
        PAYLOAD_ADDED_DOC,
        mimetype=DOCX_MIME,
        as_attachment=True,
        download_name="payloadAdded.docx",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
