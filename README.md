# Noroboto

A Unicode obfuscation tool for `.docx` and `.pdf` documents.

## Setup

```bash
pip install -r requirements.txt
```

## Command line

Total obfuscation (every glyph in the body is recoded so text extractors see only PUA characters; the rendered page is unchanged):

```bash
python noroboto.py input.docx output.docx
python noroboto.py input.pdf  output.pdf
```

Partial obfuscation (PDF only — only the targeted spans are re-coded; the rest of the document extracts cleanly):

```bash
python noroboto.py input.pdf output.pdf --mode partial \
    --substitute '$1,400,000=$400' \
    --substitute 'Crestview Analytics LLC=ACME Corp'
```

Each `--substitute VISIBLE=EXTRACTED` pair leaves the rendered page reading `VISIBLE` while text-layer extractors recover `EXTRACTED`.

## Run the tests

```bash
python -m unittest discover tests
```

The corpus test runs the CLI over every `.docx` and `.pdf` it finds under `tests/fixtures/` (always populated) and `docs/` (operator-supplied; `.gitignored`).

## Run the server

```bash
python app.py
```

Then open `http://127.0.0.1:5000`. The upload accepts both `.docx` and `.pdf`.
