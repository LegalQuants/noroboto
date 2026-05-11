from __future__ import annotations

import random
import zipfile
from copy import copy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fontTools.ttLib import TTFont
from lxml import etree

DOCX_DOCUMENT_PART = "word/document.xml"
DOCX_SETTINGS_PART = "word/settings.xml"
DOCX_FONT_TABLE_PART = "word/fontTable.xml"
DOCX_DOCUMENT_RELS_PART = "word/_rels/document.xml.rels"
DOCX_FONT_TABLE_RELS_PART = "word/_rels/fontTable.xml.rels"
DOCX_EMBEDDED_FONT_PART = "word/fonts/noroboto.odttf"
DOCX_CONTENT_TYPES_PART = "[Content_Types].xml"
DOCX_FONT_TABLE_REL_TARGET = "fontTable.xml"
DOCX_EMBEDDED_FONT_REL_TARGET = "fonts/noroboto.odttf"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PACKAGE_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FONT_RELATIONSHIP_TYPE = f"{OFFICE_RELATIONSHIPS_NS}/font"
FONT_TABLE_RELATIONSHIP_TYPE = f"{OFFICE_RELATIONSHIPS_NS}/fontTable"
OBFUSCATED_FONT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
FONT_TABLE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"
NOROBOTO_FONT_FAMILY = "Noroboto"
NOROBOTO_POSTSCRIPT_NAME = "Noroboto-Regular"
PUA_START = 0xE000
PUA_END = 0xF8FF
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS, "r": OFFICE_RELATIONSHIPS_NS}
XML_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False)


@dataclass(frozen=True)
class NorobotoBuild:
    family_name: str
    mapping: dict[int, int]
    font_bytes: bytes
    obfuscated_font_bytes: bytes
    font_key: str


def _w_namespaced(local_name: str) -> str:
    return etree.QName(WORDPROCESSINGML_NS, local_name).text


def _package_relationship_namespaced(local_name: str) -> str:
    return etree.QName(PACKAGE_RELATIONSHIPS_NS, local_name).text


def _office_relationship_namespaced(local_name: str) -> str:
    return etree.QName(OFFICE_RELATIONSHIPS_NS, local_name).text


def _content_type_namespaced(local_name: str) -> str:
    return etree.QName(CONTENT_TYPES_NS, local_name).text


def _xpath_namespaces(root: etree._Element) -> dict[str, str]:
    namespaces = {
        prefix: uri
        for prefix, uri in root.nsmap.items()
        if prefix is not None and uri is not None
    }
    namespaces.setdefault("w", WORDPROCESSINGML_NS)
    namespaces.setdefault("r", OFFICE_RELATIONSHIPS_NS)
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


def _parse_xml(payload: bytes) -> etree._Element:
    return etree.fromstring(payload, parser=XML_PARSER)


def _create_root(local_name: str, namespace: str, nsmap: dict[str | None, str]) -> etree._Element:
    return etree.Element(etree.QName(namespace, local_name).text, nsmap=nsmap)


def _next_relationship_id(root: etree._Element) -> str:
    highest = 0
    for relationship in root.findall(_package_relationship_namespaced("Relationship")):
        relationship_id = relationship.get("Id", "")
        if relationship_id.startswith("rId"):
            suffix = relationship_id[3:]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"rId{highest + 1}"


def _ensure_package_relationship(
    root: etree._Element,
    relationship_type: str,
    target: str,
    *,
    relationship_id: str | None = None,
) -> str:
    for relationship in root.findall(_package_relationship_namespaced("Relationship")):
        if relationship.get("Type") == relationship_type and relationship.get("Target") == target:
            if relationship_id and relationship.get("Id") != relationship_id:
                relationship.set("Id", relationship_id)
                return relationship_id
            existing_id = relationship.get("Id")
            if existing_id:
                return existing_id
            generated_id = relationship_id or _next_relationship_id(root)
            relationship.set("Id", generated_id)
            return generated_id

    resolved_id = relationship_id or _next_relationship_id(root)
    relationship = etree.Element(_package_relationship_namespaced("Relationship"))
    relationship.set("Id", resolved_id)
    relationship.set("Type", relationship_type)
    relationship.set("Target", target)
    root.append(relationship)
    return resolved_id


def _ensure_content_type_override(root: etree._Element, part_name: str, content_type: str) -> None:
    for override in root.findall(_content_type_namespaced("Override")):
        if override.get("PartName") == part_name:
            override.set("ContentType", content_type)
            return

    override = etree.Element(_content_type_namespaced("Override"))
    override.set("PartName", part_name)
    override.set("ContentType", content_type)
    root.append(override)


def _ensure_run_uses_font(run: etree._Element, font_name: str) -> None:
    run_properties = run.find("w:rPr", XML_NAMESPACES)
    if run_properties is None:
        run_properties = etree.Element(_w_namespaced("rPr"), nsmap=run.nsmap)
        run.insert(0, run_properties)

    r_fonts = run_properties.find("w:rFonts", XML_NAMESPACES)
    if r_fonts is None:
        r_fonts = etree.Element(_w_namespaced("rFonts"), nsmap=run.nsmap)
        run_properties.insert(0, r_fonts)

    for attribute in ("ascii", "hAnsi", "cs", "eastAsia"):
        r_fonts.set(_w_namespaced(attribute), font_name)


def _guid_key_bytes(font_key: str) -> bytes:
    return bytes.fromhex(font_key.strip("{}").replace("-", ""))[::-1]


def _obfuscate_font_bytes(font_bytes: bytes, font_key: str) -> bytes:
    obfuscated = bytearray(font_bytes)
    key_bytes = _guid_key_bytes(font_key)
    for start in (0, 16):
        for index, key_byte in enumerate(key_bytes):
            if start + index >= len(obfuscated):
                break
            obfuscated[start + index] ^= key_byte
    return bytes(obfuscated)


def _set_font_names(font: TTFont, family_name: str) -> None:
    name_table = font["name"]
    full_name = f"{family_name} Regular"
    unique_name = f"{family_name};RandomizedSymbolEncoding"
    values = {
        1: family_name,
        2: "Regular",
        3: unique_name,
        4: full_name,
        6: NOROBOTO_POSTSCRIPT_NAME,
        16: family_name,
        17: "Regular",
    }
    for name_id, value in values.items():
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 1, 0, 0)


def _eligible_codepoints(best_cmap: dict[int, str]) -> list[int]:
    return [
        codepoint
        for codepoint in sorted(best_cmap)
        if 0x20 <= codepoint <= 0xFFFF and not (PUA_START <= codepoint <= PUA_END)
    ]


def build_noroboto_font(base_font_path: Path, output_font_path: Path) -> NorobotoBuild:
    font = TTFont(str(base_font_path))
    best_cmap = font["cmap"].getBestCmap() or {}
    eligible_codepoints = _eligible_codepoints(best_cmap)
    available_pua_codepoints = list(range(PUA_START, PUA_END + 1))
    if len(eligible_codepoints) > len(available_pua_codepoints):
        raise ValueError(
            f"Base font exposes {len(eligible_codepoints)} BMP Unicode codepoints, "
            f"but only {len(available_pua_codepoints)} BMP PUA slots are available"
        )

    shuffled_pua = available_pua_codepoints[: len(eligible_codepoints)]
    random.shuffle(shuffled_pua)
    mapping = dict(zip(eligible_codepoints, shuffled_pua))

    for subtable in font["cmap"].tables:
        if not subtable.isUnicode() or not hasattr(subtable, "cmap"):
            continue
        for source_codepoint, shuffled_codepoint in mapping.items():
            glyph_name = best_cmap.get(source_codepoint)
            if glyph_name is not None:
                subtable.cmap[shuffled_codepoint] = glyph_name

    _set_font_names(font, NOROBOTO_FONT_FAMILY)
    font.save(str(output_font_path))
    font.close()

    font_bytes = output_font_path.read_bytes()
    font_key = "{" + str(uuid4()).upper() + "}"
    return NorobotoBuild(
        family_name=NOROBOTO_FONT_FAMILY,
        mapping=mapping,
        font_bytes=font_bytes,
        obfuscated_font_bytes=_obfuscate_font_bytes(font_bytes, font_key),
        font_key=font_key,
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


def replace_text_with_symbols(document_xml: bytes, text_xpath: str, build: NorobotoBuild) -> tuple[bytes, int]:
    root = _parse_xml(document_xml)
    run, target = _require_target_text_element(root, text_xpath)
    text_value = target.text or ""
    insert_at = list(run).index(target)
    _ensure_run_uses_font(run, build.family_name)
    run.remove(target)

    if text_value:
        for offset, character in enumerate(text_value):
            codepoint = ord(character)
            shuffled_codepoint = build.mapping.get(codepoint)
            if shuffled_codepoint is None:
                raise ValueError(f"Character {character!r} (U+{codepoint:04X}) is not available in the Noroboto mapping")
            symbol = etree.Element(_w_namespaced("sym"), nsmap=run.nsmap)
            symbol.set(_w_namespaced("font"), build.family_name)
            symbol.set(_w_namespaced("char"), f"{shuffled_codepoint:04X}")
            run.insert(insert_at + offset, symbol)

    updated_document_xml = _serialize_xml(root)
    return updated_document_xml, len(text_value)


def _update_font_table(font_table_xml: bytes | None, build: NorobotoBuild, font_relationship_id: str) -> bytes:
    if font_table_xml is None:
        root = _create_root("fonts", WORDPROCESSINGML_NS, {"w": WORDPROCESSINGML_NS, "r": OFFICE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(font_table_xml)

    font_element = None
    for candidate in root.findall("w:font", _xpath_namespaces(root)):
        if candidate.get(_w_namespaced("name")) == build.family_name:
            font_element = candidate
            break
    if font_element is None:
        font_element = etree.Element(_w_namespaced("font"), nsmap=root.nsmap)
        font_element.set(_w_namespaced("name"), build.family_name)
        root.append(font_element)

    for local_name, value in (("charset", "00"), ("family", "roman"), ("pitch", "variable")):
        child = font_element.find(f"w:{local_name}", XML_NAMESPACES)
        if child is None:
            child = etree.Element(_w_namespaced(local_name), nsmap=font_element.nsmap)
            font_element.append(child)
        child.set(_w_namespaced("val"), value)

    embed_regular = font_element.find("w:embedRegular", XML_NAMESPACES)
    if embed_regular is None:
        embed_regular = etree.Element(_w_namespaced("embedRegular"), nsmap=font_element.nsmap)
        font_element.append(embed_regular)
    embed_regular.set(_office_relationship_namespaced("id"), font_relationship_id)
    embed_regular.set(_w_namespaced("fontKey"), build.font_key)

    return _serialize_xml(root)


def _update_document_relationships(document_rels_xml: bytes | None) -> bytes:
    if document_rels_xml is None:
        root = _create_root("Relationships", PACKAGE_RELATIONSHIPS_NS, {None: PACKAGE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(document_rels_xml)
    _ensure_package_relationship(root, FONT_TABLE_RELATIONSHIP_TYPE, DOCX_FONT_TABLE_REL_TARGET)
    return _serialize_xml(root)


def _update_font_table_relationships(font_table_rels_xml: bytes | None) -> tuple[bytes, str]:
    if font_table_rels_xml is None:
        root = _create_root("Relationships", PACKAGE_RELATIONSHIPS_NS, {None: PACKAGE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(font_table_rels_xml)
    relationship_id = _ensure_package_relationship(root, FONT_RELATIONSHIP_TYPE, DOCX_EMBEDDED_FONT_REL_TARGET)
    return _serialize_xml(root), relationship_id


def _update_content_types(content_types_xml: bytes) -> bytes:
    root = _parse_xml(content_types_xml)
    _ensure_content_type_override(root, "/word/fontTable.xml", FONT_TABLE_CONTENT_TYPE)
    _ensure_content_type_override(root, "/word/fonts/noroboto.odttf", OBFUSCATED_FONT_CONTENT_TYPE)
    return _serialize_xml(root)


def _update_settings(settings_xml: bytes | None) -> bytes | None:
    if settings_xml is None:
        return None
    root = _parse_xml(settings_xml)
    if root.find("w:embedTrueTypeFonts", XML_NAMESPACES) is None:
        root.append(etree.Element(_w_namespaced("embedTrueTypeFonts"), nsmap=root.nsmap))
    return _serialize_xml(root)


def replace_text_element_with_symbols(docx_bytes: bytes, text_xpath: str, build: NorobotoBuild) -> tuple[bytes, int]:
    input_buffer = BytesIO(docx_bytes)
    output_buffer = BytesIO()
    replacement_count = 0
    document_part_found = False

    with zipfile.ZipFile(input_buffer, mode="r") as source_archive:
        original_infos = {info.filename: copy(info) for info in source_archive.infolist()}
        payloads = {info.filename: source_archive.read(info.filename) for info in source_archive.infolist()}

        document_xml = payloads.get(DOCX_DOCUMENT_PART)
        if document_xml is None:
            raise KeyError(f"DOCX part not found: {DOCX_DOCUMENT_PART}")

        payloads[DOCX_DOCUMENT_PART], replacement_count = replace_text_with_symbols(document_xml, text_xpath, build)
        document_part_found = True
        payloads[DOCX_DOCUMENT_RELS_PART] = _update_document_relationships(payloads.get(DOCX_DOCUMENT_RELS_PART))
        payloads[DOCX_FONT_TABLE_RELS_PART], font_relationship_id = _update_font_table_relationships(
            payloads.get(DOCX_FONT_TABLE_RELS_PART)
        )
        payloads[DOCX_FONT_TABLE_PART] = _update_font_table(payloads.get(DOCX_FONT_TABLE_PART), build, font_relationship_id)
        payloads[DOCX_CONTENT_TYPES_PART] = _update_content_types(payloads[DOCX_CONTENT_TYPES_PART])

        updated_settings = _update_settings(payloads.get(DOCX_SETTINGS_PART))
        if updated_settings is not None:
            payloads[DOCX_SETTINGS_PART] = updated_settings

        payloads[DOCX_EMBEDDED_FONT_PART] = build.obfuscated_font_bytes

        ordered_names = [info.filename for info in source_archive.infolist()]
        for part_name in payloads:
            if part_name not in original_infos:
                ordered_names.append(part_name)

        with zipfile.ZipFile(output_buffer, mode="w") as output_archive:
            for part_name in ordered_names:
                payload = payloads[part_name]
                info = original_infos.get(part_name)
                if info is None:
                    info = zipfile.ZipInfo(part_name)
                    info.compress_type = zipfile.ZIP_DEFLATED
                output_archive.writestr(copy(info), payload)

    if not document_part_found:
        raise KeyError(f"DOCX part not found: {DOCX_DOCUMENT_PART}")

    return output_buffer.getvalue(), replacement_count


if __name__ == '__main__':
    text_xpath = "w:body/w:p/w:r/w:t"
    build = build_noroboto_font(Path("./liberation-serif.ttf"), Path("./noroboto.ttf"))
    updated_docx, replacement_count = replace_text_element_with_symbols(
        Path("./nda.docx").read_bytes(),
        text_xpath,
        build,
    )
    Path("./output.docx").write_bytes(updated_docx)
    print(f"Generated noroboto.ttf with {len(build.mapping)} shuffled duplicate glyph mappings and replaced {replacement_count} characters")