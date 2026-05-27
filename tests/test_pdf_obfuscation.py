from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from noroboto_pdf import (  # noqa: E402  (path manipulated above for in-tree import)
    PUA_END,
    PUA_START,
    replace_text_with_pua_text_pdf,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_PDF_PATH = FIXTURES_DIR / "sample-agreement.pdf"


def _extract_text_with_pdfminer(pdf_bytes: bytes) -> str:
    from io import BytesIO

    from pdfminer.high_level import extract_text

    return extract_text(BytesIO(pdf_bytes))


def _extract_text_with_pypdf(pdf_bytes: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _count_pua_characters(text: str) -> int:
    return sum(1 for character in text if PUA_START <= ord(character) <= PUA_END)


class TotalObfuscationTest(unittest.TestCase):
    def test_total_mode_replaces_visible_text_with_pua_in_extraction(self) -> None:
        pdf_bytes = SAMPLE_PDF_PATH.read_bytes()
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
