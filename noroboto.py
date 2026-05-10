from __future__ import annotations
import zipfile
from copy import copy
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET

DOCX_DOCUMENT_PART = "word/document.xml"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS}
WORD_TAG_PREFIX = f"{{{WORDPROCESSINGML_NS}}}"

ET.register_namespace("w", WORDPROCESSINGML_NS)


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


def replace_text_with_symbols(document_xml: bytes, text_xpath: str) -> tuple[bytes, int]:
    root = ET.fromstring(document_xml)
    run, target = _require_target_text_element(root, text_xpath)
    text_value = target.text or ""
    insert_at = list(run).index(target)
    run.remove(target)

    if text_value:
        symbol_font = _resolve_symbol_font(run)
        for offset, character in enumerate(text_value):
            symbol = ET.Element(f"{WORD_TAG_PREFIX}sym")
            symbol.set(f"{WORD_TAG_PREFIX}font", symbol_font)
            symbol.set(f"{WORD_TAG_PREFIX}char", f"{ord(character):04X}")
            run.insert(insert_at + offset, symbol)

    updated_document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return updated_document_xml, len(text_value)


def replace_text_element_with_symbols(docx_bytes: bytes, text_xpath: str) -> tuple[bytes, int]:
    input_buffer = BytesIO(docx_bytes)
    output_buffer = BytesIO()
    replacement_count = 0
    document_part_found = False

    with zipfile.ZipFile(input_buffer, mode="r") as source_archive:
        with zipfile.ZipFile(output_buffer, mode="w") as output_archive:
            for info in source_archive.infolist():
                payload = source_archive.read(info.filename)
                if info.filename == DOCX_DOCUMENT_PART:
                    payload, replacement_count = replace_text_with_symbols(payload, text_xpath)
                    document_part_found = True

                output_archive.writestr(copy(info), payload)

    if not document_part_found:
        raise KeyError(f"DOCX part not found: {DOCX_DOCUMENT_PART}")

    return output_buffer.getvalue(), replacement_count

if __name__ == '__main__':
    text_xpath = "w:body/w:p/w:r/w:t"
    updated_docx, replacement_count = replace_text_element_with_symbols(
        Path("./nda.docx").read_bytes(),
        text_xpath,
    )
    Path("./output.docx").write_bytes(updated_docx)