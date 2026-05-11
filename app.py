from __future__ import annotations

import argparse
import zipfile
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, render_template_string, request, send_file

from noroboto import DEFAULT_TEXT_XPATH, build_noroboto_builds, replace_text_element_with_pua_text

INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <title>Noroboto</title>
</head>
<body>
    <h1>Noroboto</h1>
    <p>Upload a .docx file to apply Noroboto and download the result.</p>
    {% if error %}
    <p>{{ error }}</p>
    {% endif %}
    <form id=\"upload-form\" action=\"{{ url_for('convert_docx') }}\" method=\"post\" enctype=\"multipart/form-data\">
        <p>
            <label for=\"docx\">Choose a .docx file:</label>
            <input id=\"docx\" name=\"docx\" type=\"file\" accept=\".docx\" required>
        </p>
        <p>
            <button type=\"submit\">Upload and convert</button>
        </p>
    </form>
    <div id=\"drop-zone\" tabindex=\"0\">
        <p>Or drop a .docx file here.</p>
    </div>
    <script>
        const uploadForm = document.getElementById('upload-form');
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('docx');

        function setFile(file) {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
        }

        function submitIfDocx(file) {
            if (file && file.name.toLowerCase().endsWith('.docx')) {
                setFile(file);
                uploadForm.requestSubmit();
            }
        }

        function handleDrop(event) {
            event.preventDefault();
            const [file] = event.dataTransfer.files;
            submitIfDocx(file);
        }

        fileInput.addEventListener('change', () => {
            const [file] = fileInput.files;
            submitIfDocx(file);
        });
        dropZone.addEventListener('dragover', (event) => {
            event.preventDefault();
        });
        dropZone.addEventListener('drop', handleDrop);
    </script>
</body>
</html>
"""

app = Flask(__name__)


def _download_name_for_upload(filename: str | None) -> str:
    source_name = Path(filename or "document.docx").name
    if not source_name.lower().endswith(".docx"):
        source_name = f"{source_name}.docx"
    source_path = Path(source_name)
    return f"{source_path.stem}-noroboto.docx"


def _render_index(error: str | None = None, status_code: int = 200) -> Response:
    return Response(render_template_string(INDEX_HTML, error=error), status=status_code)


@app.get("/")
def index() -> Response:
    return _render_index()


@app.post("/convert")
def convert_docx() -> Response:
    uploaded_file = request.files.get("docx")
    if uploaded_file is None or uploaded_file.filename is None or uploaded_file.filename == "":
        return _render_index("Choose a .docx file to upload.", 400)

    if not uploaded_file.filename.lower().endswith(".docx"):
        return _render_index("Only .docx files are supported.", 400)

    try:
        updated_docx, _, _ = replace_text_element_with_pua_text(
            uploaded_file.read(),
            DEFAULT_TEXT_XPATH,
            build_noroboto_builds(),
        )
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        return _render_index(f"Could not process file: {exc}", 400)

    return send_file(
        BytesIO(updated_docx),
        as_attachment=True,
        download_name=_download_name_for_upload(uploaded_file.filename),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Noroboto web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()