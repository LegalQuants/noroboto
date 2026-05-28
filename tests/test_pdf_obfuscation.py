from __future__ import annotations

import sys
import unittest
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from noroboto import (  # noqa: E402  (path manipulated above for in-tree import)
    PUA_END,
    PUA_START,
    replace_text_with_pua_text_pdf,
)


def _build_sample_pdf_in_memory() -> bytes:
    """Build a small synthetic PDF the test can run against without a committed fixture."""
    import pikepdf
    from pikepdf import Array, Dictionary, Name, Stream

    lines = [
        ("Mutual Non-Disclosure Agreement", 18, 72, 740),
        ("Agreement Date: April 18, 2026", 11, 72, 700),
        ("Party A: Crestview Analytics LLC", 11, 72, 680),
        ("Party B: Northwind Document Systems Inc.", 11, 72, 662),
        ("Section 3. Settlement Amount.", 12, 72, 624),
        ("The settlement amount is $1,400,000 payable within thirty (30) days of", 11, 72, 600),
        ("execution of this Agreement, subject to the conditions in Schedule A.", 11, 72, 584),
        ("Governing Law: State of Delaware.", 11, 72, 552),
    ]
    pdf = pikepdf.Pdf.new()
    pdf.docinfo["/Producer"] = "noroboto test fixture"
    pdf.docinfo["/Title"] = "noroboto test fixture"
    font = pdf.make_indirect(
        Dictionary(
            Type=Name("/Font"),
            Subtype=Name("/Type1"),
            BaseFont=Name("/Helvetica"),
            Encoding=Name("/WinAnsiEncoding"),
        )
    )
    content = bytearray()
    for text, font_size, x, y in lines:
        body = text.encode("latin-1", errors="replace").hex().upper().encode("ascii")
        content.extend(
            b"BT\n"
            + f"/F1 {font_size} Tf\n1 0 0 1 {x} {y} Tm\n".encode("ascii")
            + b"<" + body + b"> Tj\nET\n"
        )
    page = Dictionary(
        Type=Name("/Page"),
        MediaBox=Array([0, 0, 612, 792]),
        Resources=Dictionary(Font=Dictionary(F1=font)),
        Contents=Stream(pdf, bytes(content)),
    )
    pdf.pages.append(pikepdf.Page(pdf.make_indirect(page)))
    buffer = BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


def _extract_text_with_pdfminer(pdf_bytes: bytes) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(BytesIO(pdf_bytes))


def _extract_text_with_pypdf(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _count_pua_characters(text: str) -> int:
    return sum(1 for character in text if PUA_START <= ord(character) <= PUA_END)


class TotalObfuscationTest(unittest.TestCase):
    def test_total_mode_replaces_visible_text_with_pua_in_extraction(self) -> None:
        pdf_bytes = _build_sample_pdf_in_memory()
        output_bytes, replacement_count, font_family = replace_text_with_pua_text_pdf(
            pdf_bytes, seed=4711,
        )
        self.assertGreater(replacement_count, 0)
        self.assertIn(font_family, ("LiberationSans", "LiberationSerif"))

        pdfminer_text = _extract_text_with_pdfminer(output_bytes)
        pypdf_text = _extract_text_with_pypdf(output_bytes)

        for extractor_name, extracted_text in (
            ("pdfminer.six", pdfminer_text),
            ("pypdf", pypdf_text),
        ):
            with self.subTest(extractor=extractor_name):
                self.assertNotIn("$1,400,000", extracted_text)
                self.assertNotIn("Crestview Analytics", extracted_text)
                self.assertNotIn("Northwind", extracted_text)
                self.assertNotIn("Delaware", extracted_text)
                self.assertGreater(_count_pua_characters(extracted_text), 50)

        for extractor_text in (pdfminer_text, pypdf_text):
            self.assertIn("automated systems", extractor_text)


if __name__ == "__main__":
    unittest.main()
