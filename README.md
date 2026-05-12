# Noroboto

## Setup

```bash
pip install -r requirements.txt
```

## Command line

```bash
python noroboto.py input.docx output.docx
```

Noroboto keeps the Liberation font variants as the primary glyph source and automatically pulls fallback glyphs from `fonts/noto/` when the input document uses codepoints that Liberation does not cover.

## Run the server

```bash
python app.py
```

Then open `http://127.0.0.1:5000`.
