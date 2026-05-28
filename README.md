# Noroboto

A Unicode obfuscation tool for `.docx` and `.pdf` documents. Every glyph in the body is recoded so text extractors see only Private Use Area characters; the rendered page is unchanged.

## Setup

```bash
pip install -r requirements.txt
```

## Command line

```bash
python noroboto.py input.docx output.docx
python noroboto.py input.pdf  output.pdf
```

For PDFs the body uses the Liberation Sans (or Liberation Serif, when the input PDF's font family is serif) TrueType font embedded from `fonts/`. The disclosure paragraph at the top of page 1 rides the same font with an honest `/ToUnicode` mapping so the disclosure text remains extractable.

## Examples

`examples/full-to-unicode.pdf` is a pre-built artifact demonstrating the full-obfuscation output for readers who don't want to run the tool — it ships in the repo so the `/ToUnicode` mechanism can be inspected directly.

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
