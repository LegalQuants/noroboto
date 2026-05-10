from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Iterator
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

DOCX_DOCUMENT_PART = "word/document.xml"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS}
WORD_TAG_PREFIX = f"{{{WORDPROCESSINGML_NS}}}"

ET.register_namespace("w", WORDPROCESSINGML_NS)


def _normalize_part_name(part_name: str) -> str:
    return part_name.lstrip("/")


def _serialize_xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _iter_text_elements(root: ET.Element) -> Iterator[ET.Element]:
    yield from root.iterfind(".//w:t", XML_NAMESPACES)


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _require_target_text_element(root: ET.Element, text_xpath: str) -> tuple[ET.Element, ET.Element]:
    target = root.find(text_xpath, XML_NAMESPACES)
    if target is None:
        raise ValueError(f"Text element not found for xpath: {text_xpath}")
    if target.tag != f"{WORD_TAG_PREFIX}t":
        raise ValueError(f"XPath must resolve to a w:t element: {text_xpath}")

    parent_map = _build_parent_map(root)
    try:
        run = parent_map[target]
    except KeyError as error:
        raise ValueError("Target text element has no parent run") from error
    if run.tag != f"{WORD_TAG_PREFIX}r":
        raise ValueError("Target text element must be a direct child of w:r")
    return run, target


def _resolve_symbol_font(run: ET.Element) -> str:
    r_fonts = run.find("w:rPr/w:rFonts", XML_NAMESPACES)
    if r_fonts is None:
        raise ValueError("Run does not define w:rFonts for symbol conversion")

    font_attributes = (
        f"{WORD_TAG_PREFIX}ascii",
        f"{WORD_TAG_PREFIX}hAnsi",
        f"{WORD_TAG_PREFIX}cs",
        f"{WORD_TAG_PREFIX}eastAsia",
    )
    for attribute_name in font_attributes:
        font_name = r_fonts.get(attribute_name)
        if font_name:
            return font_name
    raise ValueError("Run w:rFonts is present but does not define a usable font")


def replace_text_with_symbols(root: ET.Element, text_xpath: str) -> int:
    run, target = _require_target_text_element(root, text_xpath)
    text_value = target.text or ""
    insert_at = list(run).index(target)
    run.remove(target)

    if not text_value:
        return 0

    symbol_font = _resolve_symbol_font(run)
    for offset, character in enumerate(text_value):
        symbol = ET.Element(f"{WORD_TAG_PREFIX}sym")
        symbol.set(f"{WORD_TAG_PREFIX}font", symbol_font)
        symbol.set(f"{WORD_TAG_PREFIX}char", f"{ord(character):04X}")
        run.insert(insert_at + offset, symbol)
    return len(text_value)


@dataclass(slots=True)
class DocxPackage:
    parts: dict[str, bytes] = field(default_factory=dict)

    @classmethod
    def from_bytes(cls, payload: bytes) -> "DocxPackage":
        with ZipFile(BytesIO(payload), mode="r") as archive:
            parts = {
                item.filename: archive.read(item.filename)
                for item in archive.infolist()
                if not item.is_dir()
            }
        return cls(parts=parts)

    @classmethod
    def from_file(cls, path: str | Path) -> "DocxPackage":
        return cls.from_bytes(Path(path).read_bytes())

    def list_parts(self) -> list[str]:
        return sorted(self.parts)

    def read_bytes(self, part_name: str) -> bytes:
        normalized_name = _normalize_part_name(part_name)
        try:
            return self.parts[normalized_name]
        except KeyError as error:
            raise KeyError(f"DOCX part not found: {normalized_name}") from error

    def write_bytes(self, part_name: str, payload: bytes) -> None:
        self.parts[_normalize_part_name(part_name)] = payload

    def read_xml(self, part_name: str) -> ET.Element:
        return ET.fromstring(self.read_bytes(part_name))

    def write_xml(self, part_name: str, root: ET.Element) -> None:
        self.write_bytes(part_name, _serialize_xml(root))

    def document_root(self) -> ET.Element:
        return self.read_xml(DOCX_DOCUMENT_PART)

    def replace_text_element_with_symbols(self, text_xpath: str) -> int:
        document_root = self.document_root()
        replacement_count = replace_text_with_symbols(document_root, text_xpath)
        self.write_xml(DOCX_DOCUMENT_PART, document_root)
        return replacement_count

    def to_bytes(self) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for part_name in sorted(self.parts):
                archive.writestr(part_name, self.parts[part_name])
        return buffer.getvalue()

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())

if __name__ == '__main__':
    package = DocxPackage.from_file("nda.docx")
    package.replace_text_element_with_symbols(".//w:r/w:t")
    package.save("output.docx")
