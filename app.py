from __future__ import annotations

import argparse
import zipfile
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, render_template_string, request, send_file

from noroboto import DEFAULT_TEXT_XPATH, replace_text_element_with_pua_text

INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>noroboto</title>
    <style>
        :root {
            color-scheme: dark;
            --page-bg: #040404;
            --page-glow: rgba(42, 42, 42, 0.4);
            --panel-bg: rgba(10, 10, 10, 0.95);
            --panel-border: #232323;
            --text: #f1f1f1;
            --button-bg: #161616;
            --button-border: #3a3a3a;
            --button-hover: #1f1f1f;
            --error-bg: rgba(70, 18, 18, 0.42);
            --error-border: rgba(176, 76, 76, 0.42);
            --error-text: #e0a1a1;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            color: var(--text);
            font-family: monospace;
        }

        .shell {
            width: min(100%, 560px);
        }

        .corner-logo-link {
            position: fixed;
            right: 24px;
            bottom: 24px;
            display: block;
            line-height: 0;
        }

        .corner-logo-link:focus-visible {
            outline: 1px solid #6c6c6c;
            outline-offset: 4px;
        }

        .corner-logo {
            width: clamp(40px, 6vw, 56px);
            height: auto;
            opacity: 0.92;
            display: block;
            user-select: none;
        }

        .panel {
            padding: 40px 36px;
            border: 1px solid var(--panel-border);
            background: var(--panel-bg);
            text-align: center;
            backdrop-filter: blur(6px);
        }

        h1 {
            margin: 0 0 28px;
            font-size: clamp(2rem, 6vw, 2.7rem);
            line-height: 1.05;
            letter-spacing: -0.03em;
            font-weight: 700;
            text-transform: lowercase;
        }

        .brand {
            display: inline-block;
            color: var(--text);
        }

        .file-input {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }

        .button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 240px;
            min-height: 52px;
            padding: 12px 18px;
            border: 1px solid var(--button-border);
            background: var(--button-bg);
            color: var(--text);
            font: inherit;
            font-weight: 600;
            letter-spacing: 0.02em;
            text-transform: lowercase;
            cursor: pointer;
            transition: border-color 140ms ease, background-color 140ms ease, transform 140ms ease;
        }

        .button:hover,
        .button:focus-visible {
            border-color: #535353;
            background: var(--button-hover);
            transform: translateY(-1px);
        }

        .button[disabled] {
            cursor: default;
            transform: none;
            opacity: 1;
        }

        .button-label {
            display: inline-flex;
        }

        .spinner {
            display: none;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255, 255, 255, 0.18);
            border-top-color: #f1f1f1;
            animation: spin 0.7s linear infinite;
        }

        .button.loading .button-label {
            display: none;
        }

        .button.loading .spinner {
            display: inline-block;
        }

        .error {
            display: none;
            margin: 18px 0 0;
            padding: 12px 14px;
            border: 1px solid var(--error-border);
            background: var(--error-bg);
            color: var(--error-text);
            text-align: left;
        }

        .error.visible {
            display: block;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        @media (max-width: 640px) {
            .panel {
                padding: 28px 22px;
            }

            .button {
                width: 100%;
            }

            .corner-logo-link {
                right: 16px;
                bottom: 16px;
            }

            .corner-logo {
                width: 42px;
            }
        }
    </style>
</head>
<body>
    <main class=\"shell\">
        <section class=\"panel\">
            <h1><span id=\"brand\" class=\"brand\">noroboto</span></h1>
            <form id=\"upload-form\" action=\"{{ url_for('convert_docx') }}\" method=\"post\" enctype=\"multipart/form-data\">
                <input class=\"file-input\" id=\"docx\" name=\"docx\" type=\"file\" accept=\".docx\" required>
                <button id=\"obfuscate-button\" class=\"button\" type=\"button\">
                    <span class=\"button-label\">obfuscate document</span>
                    <span class=\"spinner\" aria-hidden=\"true\"></span>
                </button>
            </form>
            <p id=\"error\" class=\"error{% if error %} visible{% endif %}\">{% if error %}{{ error }}{% endif %}</p>
        </section>
    </main>
    <a class="corner-logo-link" href="https://www.legalquants.com" target="_blank" rel="noopener noreferrer" aria-label="Visit LegalQuants">
        <img class="corner-logo" src="{{ url_for('logo_asset') }}" alt="LQ logo">
    </a>
    <script>
        const uploadForm = document.getElementById('upload-form');
        const fileInput = document.getElementById('docx');
        const obfuscateButton = document.getElementById('obfuscate-button');
        const errorElement = document.getElementById('error');
        const brand = document.getElementById('brand');
        const brandText = 'noroboto';
        const tofuGlyph = '\\uE000';
        const tofuText = tofuGlyph.repeat(Array.from(brandText).length);
        let isLoading = false;

        function showError(message) {
            if (!errorElement) {
                return;
            }

            errorElement.textContent = message;
            errorElement.classList.add('visible');
        }

        function clearError() {
            if (!errorElement) {
                return;
            }

            errorElement.textContent = '';
            errorElement.classList.remove('visible');
        }

        function setLoading(nextLoading) {
            isLoading = nextLoading;
            if (!obfuscateButton) {
                return;
            }

            obfuscateButton.disabled = nextLoading;
            obfuscateButton.classList.toggle('loading', nextLoading);
        }

        function extractFilename(response) {
            const disposition = response.headers.get('Content-Disposition') || '';
            const utf8Match = disposition.match(/filename\\*=UTF-8''([^;]+)/i);
            if (utf8Match) {
                return decodeURIComponent(utf8Match[1]);
            }

            const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
            if (asciiMatch) {
                return asciiMatch[1];
            }

            return 'noroboto.docx';
        }

        function triggerDownload(blob, filename) {
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        }

        async function uploadSelectedFile(file) {
            if (!file || isLoading) {
                return;
            }

            if (!file.name.toLowerCase().endsWith('.docx')) {
                showError('Only .docx files are supported.');
                fileInput.value = '';
                return;
            }

            clearError();
            setLoading(true);

            try {
                const formData = new FormData();
                formData.append('docx', file);

                const response = await fetch(uploadForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'fetch' },
                });

                if (!response.ok) {
                    const message = (await response.text()).trim() || 'Could not process file.';
                    throw new Error(message);
                }

                const blob = await response.blob();
                triggerDownload(blob, extractFilename(response));
            } catch (error) {
                showError(error instanceof Error ? error.message : 'Could not process file.');
            } finally {
                setLoading(false);
                fileInput.value = '';
            }
        }

        function renderBrand(text) {
            if (!brand) {
                return;
            }

            brand.textContent = text;
        }

        if (brand) {
            brand.addEventListener('mouseenter', () => {
                renderBrand(tofuText);
            });

            brand.addEventListener('mouseleave', () => {
                renderBrand(brandText);
            });
        }

        obfuscateButton.addEventListener('click', () => {
            if (!isLoading) {
                fileInput.click();
            }
        });

        fileInput.addEventListener('change', () => {
            const [file] = fileInput.files;
            uploadSelectedFile(file);
        });

        renderBrand(brandText);
    </script>
</body>
</html>
"""

app = Flask(__name__)
LOGO_PATH = Path(__file__).with_name("lq-logo.png")


def _download_name_for_upload(filename: str | None) -> str:
    source_name = Path(filename or "document.docx").name
    if not source_name.lower().endswith(".docx"):
        source_name = f"{source_name}.docx"
    source_path = Path(source_name)
    return f"{source_path.stem}-noroboto.docx"


def _render_index(error: str | None = None, status_code: int = 200) -> Response:
    return Response(render_template_string(INDEX_HTML, error=error), status=status_code)


def _is_async_request() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _render_error(message: str, status_code: int = 400) -> Response:
    if _is_async_request():
        return Response(message, status=status_code, mimetype="text/plain")
    return _render_index(message, status_code)


@app.get("/")
def index() -> Response:
    return _render_index()


@app.get("/lq-logo.png")
def logo_asset() -> Response:
    return Response(LOGO_PATH.read_bytes(), mimetype="image/png")


@app.post("/convert")
def convert_docx() -> Response:
    uploaded_file = request.files.get("docx")
    if uploaded_file is None or uploaded_file.filename is None or uploaded_file.filename == "":
        return _render_error("Choose a .docx file to upload.", 400)

    if not uploaded_file.filename.lower().endswith(".docx"):
        return _render_error("Only .docx files are supported.", 400)

    try:
        updated_docx, _, _ = replace_text_element_with_pua_text(
            uploaded_file.read(),
            DEFAULT_TEXT_XPATH,
        )
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        return _render_error(f"Could not process file: {exc}", 400)

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