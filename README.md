# Noroboto

A Unicode obfuscation tool for `.docx` and `.pdf` documents. Every glyph in the body is recoded so text extractors see only Private Use Area characters; the rendered page is unchanged.

## Setup

```bash
pip install -r requirements.txt
```

## Command line

```bash
python noroboto.py input.[docx|pdf] output.[docx|pdf]
```

## Run the tests

```bash
python -m unittest discover tests
```

The corpus test runs the CLI over every `.docx` and `.pdf` it finds under `docs/`.

## Run the server

```bash
python app.py
```

Then open `http://127.0.0.1:5000`. The upload accepts both `.docx` and `.pdf`.
