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
DOCX_CONTENT_TYPES_PART = "[Content_Types].xml"
DOCX_FONT_TABLE_REL_TARGET = "fontTable.xml"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PACKAGE_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FONT_RELATIONSHIP_TYPE = f"{OFFICE_RELATIONSHIPS_NS}/font"
FONT_TABLE_RELATIONSHIP_TYPE = f"{OFFICE_RELATIONSHIPS_NS}/fontTable"
OBFUSCATED_FONT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
FONT_TABLE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"
PUA_START = 0xE000
PUA_END = 0xF8FF
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS, "r": OFFICE_RELATIONSHIPS_NS}
XML_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False)


@dataclass(frozen=True)
class NorobotoVariant:
    family_key: str
    family_name: str
    subfamily_name: str
    postscript_name: str
    base_font_path: Path
    embedded_font_part: str
    embedded_font_rel_target: str
    word_family: str
    embed_element_name: str

    @property
    def display_name(self) -> str:
        if self.subfamily_name == "Regular":
            return self.family_name
        return f"{self.family_name} {self.subfamily_name}"


def _build_variant(
    family_key: str,
    family_name: str,
    subfamily_name: str,
    postscript_name: str,
    base_font_filename: str,
    embedded_font_filename: str,
    word_family: str,
    embed_element_name: str,
) -> NorobotoVariant:
    return NorobotoVariant(
        family_key=family_key,
        family_name=family_name,
        subfamily_name=subfamily_name,
        postscript_name=postscript_name,
        base_font_path=Path(base_font_filename),
        embedded_font_part=f"word/fonts/{embedded_font_filename}",
        embedded_font_rel_target=f"fonts/{embedded_font_filename}",
        word_family=word_family,
        embed_element_name=embed_element_name,
    )


NOROBOTO_VARIANTS = {
    "serif_regular": _build_variant(
        "serif",
        "Noroboto Serif",
        "Regular",
        "NorobotoSerif-Regular",
        "./liberation-serif-regular.ttf",
        "noroboto-serif.odttf",
        "roman",
        "embedRegular",
    ),
    "serif_bold": _build_variant(
        "serif",
        "Noroboto Serif",
        "Bold",
        "NorobotoSerif-Bold",
        "./liberation-serif-bold.ttf",
        "noroboto-serif-bold.odttf",
        "roman",
        "embedBold",
    ),
    "serif_italic": _build_variant(
        "serif",
        "Noroboto Serif",
        "Italic",
        "NorobotoSerif-Italic",
        "./liberation-serif-italic.ttf",
        "noroboto-serif-italic.odttf",
        "roman",
        "embedItalic",
    ),
    "serif_bold_italic": _build_variant(
        "serif",
        "Noroboto Serif",
        "Bold Italic",
        "NorobotoSerif-BoldItalic",
        "./liberation-serif-bold-italic.ttf",
        "noroboto-serif-bold-italic.odttf",
        "roman",
        "embedBoldItalic",
    ),
    "sans_regular": _build_variant(
        "sans",
        "Noroboto Sans",
        "Regular",
        "NorobotoSans-Regular",
        "./liberation-sans-regular.ttf",
        "noroboto-sans.odttf",
        "swiss",
        "embedRegular",
    ),
    "sans_bold": _build_variant(
        "sans",
        "Noroboto Sans",
        "Bold",
        "NorobotoSans-Bold",
        "./liberation-sans-bold.ttf",
        "noroboto-sans-bold.odttf",
        "swiss",
        "embedBold",
    ),
    "sans_italic": _build_variant(
        "sans",
        "Noroboto Sans",
        "Italic",
        "NorobotoSans-Italic",
        "./liberation-sans-italic.ttf",
        "noroboto-sans-italic.odttf",
        "swiss",
        "embedItalic",
    ),
    "sans_bold_italic": _build_variant(
        "sans",
        "Noroboto Sans",
        "Bold Italic",
        "NorobotoSans-BoldItalic",
        "./liberation-sans-bold-italic.ttf",
        "noroboto-sans-bold-italic.odttf",
        "swiss",
        "embedBoldItalic",
    ),
}

ARIAL_FONT_NAMES = {"Arial"}
WORD_FALSE_VALUES = {"0", "false", "off"}


@dataclass(frozen=True)
class NorobotoBuild:
    variant: NorobotoVariant
    mapping: dict[int, int]
    font_bytes: bytes
    obfuscated_font_bytes: bytes
    font_key: str

    @property
    def family_name(self) -> str:
        return self.variant.family_name

    @property
    def display_name(self) -> str:
        return self.variant.display_name


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


def _ensure_content_type_default(root: etree._Element, extension: str, content_type: str) -> None:
    for default in root.findall(_content_type_namespaced("Default")):
        if default.get("Extension") == extension:
            default.set("ContentType", content_type)
            return

    default = etree.Element(_content_type_namespaced("Default"))
    default.set("Extension", extension)
    default.set("ContentType", content_type)
    root.append(default)


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


def _set_font_names(font: TTFont, variant: NorobotoVariant) -> None:
    name_table = font["name"]
    family_name = variant.family_name
    full_name = variant.display_name
    unique_name = f"{variant.postscript_name};RandomizedSymbolEncoding"
    values = {
        1: family_name,
        2: variant.subfamily_name,
        3: unique_name,
        4: full_name,
        6: variant.postscript_name,
        16: family_name,
        17: variant.subfamily_name,
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


def _run_font_names(run: etree._Element) -> list[str]:
    run_properties = run.find("w:rPr", XML_NAMESPACES)
    if run_properties is None:
        return []

    r_fonts = run_properties.find("w:rFonts", XML_NAMESPACES)
    if r_fonts is None:
        return []

    font_names: list[str] = []
    for attribute in ("ascii", "hAnsi", "cs", "eastAsia"):
        font_name = r_fonts.get(_w_namespaced(attribute))
        if font_name and font_name not in font_names:
            font_names.append(font_name)
    return font_names


def _run_property_is_enabled(run: etree._Element, local_names: tuple[str, ...]) -> bool:
    run_properties = run.find("w:rPr", XML_NAMESPACES)
    if run_properties is None:
        return False

    for local_name in local_names:
        element = run_properties.find(f"w:{local_name}", XML_NAMESPACES)
        if element is None:
            continue
        value = element.get(_w_namespaced("val"))
        if value is None:
            return True
        if value.lower() not in WORD_FALSE_VALUES:
            return True
    return False


def _style_key_for_run(run: etree._Element) -> str:
    is_bold = _run_property_is_enabled(run, ("b", "bCs"))
    is_italic = _run_property_is_enabled(run, ("i", "iCs"))
    if is_bold and is_italic:
        return "bold_italic"
    if is_bold:
        return "bold"
    if is_italic:
        return "italic"
    return "regular"


def _select_build_for_run(run: etree._Element, builds: dict[str, NorobotoBuild]) -> NorobotoBuild:
    run_font_names = set(_run_font_names(run))
    family_key = "sans" if run_font_names & ARIAL_FONT_NAMES else "serif"
    style_key = _style_key_for_run(run)
    return builds[f"{family_key}_{style_key}"]


def _family_mapping_for_variants(variants: list[NorobotoVariant]) -> dict[int, int]:
    eligible_sets: list[set[int]] = []
    for variant in variants:
        font = TTFont(str(variant.base_font_path))
        best_cmap = font["cmap"].getBestCmap() or {}
        eligible_sets.append(set(_eligible_codepoints(best_cmap)))
        font.close()

    eligible_codepoints = sorted(set.intersection(*eligible_sets)) if eligible_sets else []
    available_pua_codepoints = list(range(PUA_START, PUA_END + 1))
    if len(eligible_codepoints) > len(available_pua_codepoints):
        raise ValueError(
            f"Base font family exposes {len(eligible_codepoints)} shared BMP Unicode codepoints, "
            f"but only {len(available_pua_codepoints)} BMP PUA slots are available"
        )

    shuffled_pua = available_pua_codepoints[: len(eligible_codepoints)]
    random.shuffle(shuffled_pua)
    return dict(zip(eligible_codepoints, shuffled_pua))


def build_noroboto_font(variant: NorobotoVariant, mapping: dict[int, int]) -> NorobotoBuild:
    font = TTFont(str(variant.base_font_path))
    best_cmap = font["cmap"].getBestCmap() or {}

    for subtable in font["cmap"].tables:
        if not subtable.isUnicode() or not hasattr(subtable, "cmap"):
            continue
        for source_codepoint, shuffled_codepoint in mapping.items():
            glyph_name = best_cmap.get(source_codepoint)
            if glyph_name is not None:
                subtable.cmap[shuffled_codepoint] = glyph_name

    _set_font_names(font, variant)
    font_buffer = BytesIO()
    font.save(font_buffer)
    font.close()

    font_bytes = font_buffer.getvalue()
    font_key = "{" + str(uuid4()).upper() + "}"
    return NorobotoBuild(
        variant=variant,
        mapping=mapping,
        font_bytes=font_bytes,
        obfuscated_font_bytes=_obfuscate_font_bytes(font_bytes, font_key),
        font_key=font_key,
    )


def _require_target_text_elements(root: etree._Element, text_xpath: str) -> list[tuple[etree._Element, etree._Element]]:
    targets = root.xpath(text_xpath, namespaces=_xpath_namespaces(root))
    if not targets:
        raise ValueError(f"Text element not found for xpath: {text_xpath}")
    resolved_targets: list[tuple[etree._Element, etree._Element]] = []
    for target in targets:
        if not isinstance(target, etree._Element):
            raise ValueError(f"XPath must resolve to elements: {text_xpath}")
        if target.tag != _w_namespaced("t"):
            raise ValueError(f"XPath must resolve to w:t elements: {text_xpath}")

        run = target.getparent()
        if run is None:
            raise ValueError("Target text element has no parent run")
        if run.tag != _w_namespaced("r"):
            raise ValueError("Target text element must be a direct child of w:r")
        resolved_targets.append((run, target))
    return resolved_targets


def replace_text_with_pua_text(document_xml: bytes, text_xpath: str, builds: dict[str, NorobotoBuild]) -> tuple[bytes, int, str]:
    root = _parse_xml(document_xml)
    replacement_count = 0
    selected_family_names: set[str] = set()
    for run, target in _require_target_text_elements(root, text_xpath):
        build = _select_build_for_run(run, builds)
        text_value = target.text or ""
        _ensure_run_uses_font(run, build.family_name)
        remapped_characters: list[str] = []
        for character in text_value:
            codepoint = ord(character)
            shuffled_codepoint = build.mapping.get(codepoint)
            if shuffled_codepoint is None:
                raise ValueError(
                    f"Character {character!r} (U+{codepoint:04X}) is not available in the {build.display_name} mapping"
                )
            remapped_characters.append(chr(shuffled_codepoint))

        target.text = "".join(remapped_characters)
        replacement_count += len(text_value)
        selected_family_names.add(build.family_name)

    updated_document_xml = _serialize_xml(root)
    family_summary = ", ".join(sorted(selected_family_names))
    return updated_document_xml, replacement_count, family_summary


def _update_font_table(
    font_table_xml: bytes | None,
    builds: dict[str, NorobotoBuild],
    font_relationship_ids: dict[str, str],
) -> bytes:
    if font_table_xml is None:
        root = _create_root("fonts", WORDPROCESSINGML_NS, {"w": WORDPROCESSINGML_NS, "r": OFFICE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(font_table_xml)

    for build_key, build in builds.items():
        font_element = None
        for candidate in root.findall("w:font", _xpath_namespaces(root)):
            if candidate.get(_w_namespaced("name")) == build.family_name:
                font_element = candidate
                break
        if font_element is None:
            font_element = etree.Element(_w_namespaced("font"), nsmap=root.nsmap)
            font_element.set(_w_namespaced("name"), build.family_name)
            root.append(font_element)

        for local_name, value in (
            ("charset", "00"),
            ("family", build.variant.word_family),
            ("pitch", "variable"),
        ):
            child = font_element.find(f"w:{local_name}", XML_NAMESPACES)
            if child is None:
                child = etree.Element(_w_namespaced(local_name), nsmap=font_element.nsmap)
                font_element.append(child)
            child.set(_w_namespaced("val"), value)

        embed_element = font_element.find(f"w:{build.variant.embed_element_name}", XML_NAMESPACES)
        if embed_element is None:
            embed_element = etree.Element(_w_namespaced(build.variant.embed_element_name), nsmap=font_element.nsmap)
            font_element.append(embed_element)
        embed_element.set(_office_relationship_namespaced("id"), font_relationship_ids[build_key])
        embed_element.set(_w_namespaced("fontKey"), build.font_key)

    return _serialize_xml(root)


def _update_document_relationships(document_rels_xml: bytes | None) -> bytes:
    if document_rels_xml is None:
        root = _create_root("Relationships", PACKAGE_RELATIONSHIPS_NS, {None: PACKAGE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(document_rels_xml)
    _ensure_package_relationship(root, FONT_TABLE_RELATIONSHIP_TYPE, DOCX_FONT_TABLE_REL_TARGET)
    return _serialize_xml(root)


def _update_font_table_relationships(
    font_table_rels_xml: bytes | None,
    builds: dict[str, NorobotoBuild],
) -> tuple[bytes, dict[str, str]]:
    if font_table_rels_xml is None:
        root = _create_root("Relationships", PACKAGE_RELATIONSHIPS_NS, {None: PACKAGE_RELATIONSHIPS_NS})
    else:
        root = _parse_xml(font_table_rels_xml)

    relationship_ids: dict[str, str] = {}
    for build_key, build in builds.items():
        relationship_ids[build_key] = _ensure_package_relationship(
            root,
            FONT_RELATIONSHIP_TYPE,
            build.variant.embedded_font_rel_target,
        )
    return _serialize_xml(root), relationship_ids


def _update_content_types(content_types_xml: bytes, builds: dict[str, NorobotoBuild]) -> bytes:
    root = _parse_xml(content_types_xml)

    for override in list(root.findall(_content_type_namespaced("Override"))):
        part_name = override.get("PartName") or ""
        if part_name.endswith(".rels") or part_name.startswith("/word/fonts/"):
            root.remove(override)

    _ensure_content_type_default(root, "rels", "application/vnd.openxmlformats-package.relationships+xml")
    _ensure_content_type_default(root, "xml", "application/xml")
    _ensure_content_type_default(root, "odttf", OBFUSCATED_FONT_CONTENT_TYPE)

    _ensure_content_type_override(root, "/word/fontTable.xml", FONT_TABLE_CONTENT_TYPE)
    return _serialize_xml(root)


def replace_text_element_with_pua_text(
    docx_bytes: bytes,
    text_xpath: str,
    builds: dict[str, NorobotoBuild],
) -> tuple[bytes, int, str]:
    input_buffer = BytesIO(docx_bytes)
    output_buffer = BytesIO()
    replacement_count = 0
    document_part_found = False
    selected_family_name = ""

    with zipfile.ZipFile(input_buffer, mode="r") as source_archive:
        original_infos = {info.filename: copy(info) for info in source_archive.infolist()}
        payloads = {info.filename: source_archive.read(info.filename) for info in source_archive.infolist()}

        document_xml = payloads.get(DOCX_DOCUMENT_PART)
        if document_xml is None:
            raise KeyError(f"DOCX part not found: {DOCX_DOCUMENT_PART}")

        payloads[DOCX_DOCUMENT_PART], replacement_count, selected_family_name = replace_text_with_pua_text(
            document_xml,
            text_xpath,
            builds,
        )
        document_part_found = True
        payloads[DOCX_DOCUMENT_RELS_PART] = _update_document_relationships(payloads.get(DOCX_DOCUMENT_RELS_PART))
        payloads[DOCX_FONT_TABLE_RELS_PART], font_relationship_ids = _update_font_table_relationships(
            payloads.get(DOCX_FONT_TABLE_RELS_PART),
            builds,
        )
        payloads[DOCX_FONT_TABLE_PART] = _update_font_table(
            payloads.get(DOCX_FONT_TABLE_PART),
            builds,
            font_relationship_ids,
        )
        payloads[DOCX_CONTENT_TYPES_PART] = _update_content_types(payloads[DOCX_CONTENT_TYPES_PART], builds)


        for build in builds.values():
            payloads[build.variant.embedded_font_part] = build.obfuscated_font_bytes

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

    return output_buffer.getvalue(), replacement_count, selected_family_name


def _write_output_docx(docx_bytes: bytes, output_path: Path) -> Path:
    try:
        output_path.write_bytes(docx_bytes)
        return output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}-generated{output_path.suffix}")
        fallback_path.write_bytes(docx_bytes)
        return fallback_path


if __name__ == '__main__':
    text_xpath = ".//w:t"
    family_mappings = {
        family_key: _family_mapping_for_variants(
            [variant for variant in NOROBOTO_VARIANTS.values() if variant.family_key == family_key]
        )
        for family_key in {variant.family_key for variant in NOROBOTO_VARIANTS.values()}
    }
    builds = {
        key: build_noroboto_font(variant, family_mappings[variant.family_key])
        for key, variant in NOROBOTO_VARIANTS.items()
    }
    updated_docx, replacement_count, selected_font_name = replace_text_element_with_pua_text(
        Path("./nda.docx").read_bytes(),
        text_xpath,
        builds,
    )
    output_path = _write_output_docx(updated_docx, Path("./output.docx"))
    print(
        f"Built {len(builds)} randomized Noroboto embedded fonts in memory; "
        f"used {selected_font_name} for substitution, replaced {replacement_count} characters, "
        f"and wrote {output_path.name}"
    )