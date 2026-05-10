from __future__ import annotations
import zipfile
from copy import copy
from io import BytesIO
from pathlib import Path
from lxml import etree

DOCX_DOCUMENT_PART = "word/document.xml"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS}
XML_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False)



def _w_namespaced(local_name: str) -> str:
    return etree.QName(WORDPROCESSINGML_NS, local_name).text


def _xpath_namespaces(root: etree._Element) -> dict[str, str]:
    namespaces = {
        prefix: uri
        for prefix, uri in root.nsmap.items()
        if prefix is not None and uri is not None
    }
    namespaces.setdefault("w", WORDPROCESSINGML_NS)
    return namespaces


def _serialize_xml(root: etree._Element) -> bytes:
    document_info = root.getroottree().docinfo
    encoding = document_info.encoding or "UTF-8"
    standalone = None if document_info.standalone is None else bool(document_info.standalone)
    return etree.tostring(
        root,
        encoding=encoding,
        pretty_print=False,
        standalone=standalone,
        xml_declaration=True,
    )


def _require_target_text_element(root: etree._Element, text_xpath: str) -> tuple[etree._Element, etree._Element]:
    targets = root.xpath(text_xpath, namespaces=_xpath_namespaces(root))
    if not targets:
        raise ValueError(f"Text element not found for xpath: {text_xpath}")
    target = targets[0]
    if not isinstance(target, etree._Element):
        raise ValueError(f"XPath must resolve to an element: {text_xpath}")
    if target.tag != _w_namespaced("t"):
        raise ValueError(f"XPath must resolve to a w:t element: {text_xpath}")

    run = target.getparent()
    if run is None:
        raise ValueError("Target text element has no parent run")
    if run.tag != _w_namespaced("r"):
        raise ValueError("Target text element must be a direct child of w:r")
    return run, target


def _resolve_symbol_font(run: etree._Element) -> str:
    r_fonts = run.find("w:rPr/w:rFonts", XML_NAMESPACES)
    if r_fonts is None:
        raise ValueError("Run does not define w:rFonts for symbol conversion")

    font_attributes = tuple(_w_namespaced(attribute) for attribute in ("ascii", "hAnsi", "cs", "eastAsia"))
    for attribute_name in font_attributes:
        font_name = r_fonts.get(attribute_name)
        if font_name:
            return font_name
    raise ValueError("Run w:rFonts is present but does not define a usable font")


def replace_text_with_symbols(document_xml: bytes, text_xpath: str) -> tuple[bytes, int]:
    root = etree.fromstring(document_xml, parser=XML_PARSER)
    run, target = _require_target_text_element(root, text_xpath)
    text_value = target.text or ""
    insert_at = list(run).index(target)
    run.remove(target)

    if text_value:
        symbol_font = _resolve_symbol_font(run)
        for offset, character in enumerate(text_value):
            symbol = etree.Element(_w_namespaced("sym"), nsmap=run.nsmap)
            symbol.set(_w_namespaced("font"), symbol_font)
            symbol.set(_w_namespaced("char"), f"{ord(character):04X}")
            run.insert(insert_at + offset, symbol)

    updated_document_xml = _serialize_xml(root)
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