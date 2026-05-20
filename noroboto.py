from __future__ import annotations

import argparse
import random
import unicodedata
import zipfile
from copy import copy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from lxml import etree

DOCX_DOCUMENT_PART = "word/document.xml"
DOCX_SETTINGS_PART = "word/settings.xml"
DOCX_FONT_TABLE_PART = "word/fontTable.xml"
DOCX_DOCUMENT_RELS_PART = "word/_rels/document.xml.rels"
DOCX_FONT_TABLE_RELS_PART = "word/_rels/fontTable.xml.rels"
DOCX_CONTENT_TYPES_PART = "[Content_Types].xml"
DOCX_FONT_TABLE_REL_TARGET = "fontTable.xml"
DOCX_ENDNOTES_PART = "word/endnotes.xml"
DOCX_FOOTNOTES_PART = "word/footnotes.xml"
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
PUA_VARIANTS_PER_CODEPOINT = 4
XML_NAMESPACES = {"w": WORDPROCESSINGML_NS, "r": OFFICE_RELATIONSHIPS_NS}
XML_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
DEFAULT_TEXT_XPATH = ".//w:t"
NOTO_FONTS_DIR = Path("fonts").joinpath("noto")
COMMON_NOTO_FALLBACK_FILENAMES = (
    "noto/NotoSansSC-Regular.ttf",
    "noto/NotoSansSymbols-Regular.ttf",
    "noto/NotoSansSymbols2-Regular.ttf",
)
STYLE_NOTO_FALLBACK_FILENAMES = {
    "regular": ("noto/NotoSans-Regular.ttf",),
    "bold": ("noto/NotoSans-Bold.ttf", "noto/NotoSans-Regular.ttf"),
    "italic": ("noto/NotoSans-Italic.ttf", "noto/NotoSans-Regular.ttf"),
    "bold_italic": ("noto/NotoSans-BoldItalic.ttf", "noto/NotoSans-Regular.ttf"),
}
DISCLOSURE_PARAGRAPH_TEXT = (
    "This document contains mitigations against review by automated systems. "
    "Recipients should ensure that they have read the contents on screen or in print. "
    "Recipients with bona fide vision impairments may be entitled to unmitigated documents upon request."
)
DISCLOSURE_PARAGRAPH_BUILD_KEY = "serif_regular"


def _discover_noto_fallback_paths(style_key: str) -> tuple[Path, ...]:
    preferred_paths = [
        Path("fonts").joinpath(font_filename)
        for font_filename in (*STYLE_NOTO_FALLBACK_FILENAMES[style_key], *COMMON_NOTO_FALLBACK_FILENAMES)
    ]
    discovered_paths = sorted(path for path in NOTO_FONTS_DIR.rglob("*.ttf") if path.is_file())

    fallback_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path in (*preferred_paths, *discovered_paths):
        if not path.exists() or path in seen_paths:
            continue
        fallback_paths.append(path)
        seen_paths.add(path)
    return tuple(fallback_paths)


@dataclass(frozen=True)
class NorobotoVariant:
    family_key: str
    family_name: str
    subfamily_name: str
    postscript_name: str
    base_font_path: Path
    fallback_font_paths: tuple[Path, ...]
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
    style_key: str,
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
        base_font_path=Path("fonts").joinpath(base_font_filename),
        fallback_font_paths=_discover_noto_fallback_paths(style_key),
        embedded_font_part=f"word/fonts/{embedded_font_filename}",
        embedded_font_rel_target=f"fonts/{embedded_font_filename}",
        word_family=word_family,
        embed_element_name=embed_element_name,
    )


NOROBOTO_VARIANTS = {
    "serif_regular": _build_variant(
        "serif",
        "regular",
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
        "bold",
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
        "italic",
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
        "bold_italic",
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
        "regular",
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
        "bold",
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
        "italic",
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
        "bold_italic",
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
GLYPH_PERTURB_MAX_SHIFT = 1
PUAMapping = dict[int, tuple[int, ...]]


@dataclass(frozen=True)
class NorobotoBuild:
    variant: NorobotoVariant
    mapping: PUAMapping
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


def _insert_root_disclosure_paragraph(document_xml: bytes, font_name: str) -> bytes:
    root = _parse_xml(document_xml)
    body = root.find("w:body", XML_NAMESPACES)
    if body is None:
        raise ValueError("Document body not found")

    body_section_properties = body.find("w:sectPr", XML_NAMESPACES)
    if body_section_properties is None:
        body_section_properties = etree.Element(_w_namespaced("sectPr"), nsmap=body.nsmap)
        body.append(body_section_properties)

    paragraph = etree.Element(_w_namespaced("p"), nsmap=body.nsmap)
    paragraph_properties = etree.SubElement(paragraph, _w_namespaced("pPr"))
    paragraph_section_properties = etree.fromstring(etree.tostring(body_section_properties), parser=XML_PARSER)
    section_type = paragraph_section_properties.find("w:type", XML_NAMESPACES)
    if section_type is None:
        section_type = etree.Element(_w_namespaced("type"), nsmap=paragraph_section_properties.nsmap)
        paragraph_section_properties.insert(0, section_type)
    section_type.set(_w_namespaced("val"), "continuous")
    paragraph_properties.append(paragraph_section_properties)

    run = etree.SubElement(paragraph, _w_namespaced("r"))
    _ensure_run_uses_font(run, font_name)
    text = etree.SubElement(run, _w_namespaced("t"))
    text.text = DISCLOSURE_PARAGRAPH_TEXT

    body.insert(0, paragraph)
    return _serialize_xml(root)


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


def _should_preserve_codepoint(codepoint: int) -> bool:
    character = chr(codepoint)
    if character.isspace():
        return True
    return unicodedata.category(character).startswith("P")


def _eligible_codepoints(best_cmap: dict[int, str]) -> list[int]:
    return [
        codepoint
        for codepoint in sorted(best_cmap)
        if 0x20 <= codepoint <= 0xFFFF
        and not (PUA_START <= codepoint <= PUA_END)
        and not _should_preserve_codepoint(codepoint)
    ]


def _unique_generated_glyph_name(font: TTFont, base_name: str) -> str:
    candidate = base_name
    suffix = 1
    existing_glyph_names = set(font.getGlyphOrder())
    while candidate in existing_glyph_names:
        candidate = f"{base_name}.{suffix}"
        suffix += 1
    return candidate


def _unique_fallback_glyph_name(font: TTFont, codepoint: int) -> str:
    return _unique_generated_glyph_name(font, f"uni{codepoint:04X}.fallback")


def _unique_pua_clone_glyph_name(font: TTFont, source_codepoint: int, shuffled_codepoint: int) -> str:
    return _unique_generated_glyph_name(font, f"uni{source_codepoint:04X}.pua{shuffled_codepoint:04X}")


class _PerturbingPen:
    def __init__(self, out_pen: TTGlyphPen):
        self._out_pen = out_pen
        self._has_perturbed = False

    def _perturb_point(self, point: tuple[float, float]) -> tuple[float, float]:
        if self._has_perturbed:
            return point

        dx = random.choice((-GLYPH_PERTURB_MAX_SHIFT, GLYPH_PERTURB_MAX_SHIFT))
        dy = random.choice((-GLYPH_PERTURB_MAX_SHIFT, GLYPH_PERTURB_MAX_SHIFT))
        self._has_perturbed = True
        return (point[0] + dx, point[1] + dy)

    def moveTo(self, point: tuple[float, float]) -> None:
        self._out_pen.moveTo(point)

    def lineTo(self, point: tuple[float, float]) -> None:
        self._out_pen.lineTo(self._perturb_point(point))

    def qCurveTo(self, *points: tuple[float, float] | None) -> None:
        perturbed_points = list(points)
        for index, point in enumerate(perturbed_points):
            if point is None:
                continue
            perturbed_points[index] = self._perturb_point(point)
            break
        self._out_pen.qCurveTo(*perturbed_points)

    def curveTo(self, *points: tuple[float, float]) -> None:
        perturbed_points = list(points)
        for index, point in enumerate(perturbed_points):
            perturbed_points[index] = self._perturb_point(point)
            break
        self._out_pen.curveTo(*perturbed_points)

    def closePath(self) -> None:
        self._out_pen.closePath()

    def endPath(self) -> None:
        self._out_pen.endPath()

    def addComponent(self, glyph_name: str, transformation: tuple[float, float, float, float, float, float]) -> None:
        self._out_pen.addComponent(glyph_name, transformation)


def _clone_glyph_with_perturbation(font: TTFont, glyph_set, source_glyph_name: str, cloned_glyph_name: str) -> None:
    recording_pen = DecomposingRecordingPen(glyph_set)
    glyph_set[source_glyph_name].draw(recording_pen)

    pen = TTGlyphPen(glyph_set)
    recording_pen.replay(_PerturbingPen(pen))
    font["glyf"].glyphs[cloned_glyph_name] = pen.glyph()


def _copy_fallback_glyphs(font: TTFont, variant: NorobotoVariant, required_codepoints: set[int]) -> dict[int, str]:
    if not required_codepoints:
        return font["cmap"].getBestCmap() or {}

    if "glyf" not in font or "hmtx" not in font:
        raise ValueError(f"Base font does not support fallback glyph injection: {variant.base_font_path.name}")

    best_cmap = dict(font["cmap"].getBestCmap() or {})
    missing_codepoints = {codepoint for codepoint in required_codepoints if codepoint not in best_cmap}
    if not missing_codepoints:
        return best_cmap

    glyph_order = list(font.getGlyphOrder())
    glyph_order_changed = False
    base_units_per_em = font["head"].unitsPerEm
    base_glyph_set = font.getGlyphSet()
    unicode_cmap_tables = [
        subtable
        for subtable in font["cmap"].tables
        if subtable.isUnicode() and hasattr(subtable, "cmap")
    ]

    for fallback_font_path in variant.fallback_font_paths:
        if not missing_codepoints:
            break

        fallback_font = TTFont(str(fallback_font_path))
        try:
            if "glyf" not in fallback_font or "hmtx" not in fallback_font:
                continue

            fallback_cmap = fallback_font["cmap"].getBestCmap() or {}
            fallback_glyph_set = fallback_font.getGlyphSet()
            scale = base_units_per_em / fallback_font["head"].unitsPerEm
            resolved_codepoints = sorted(codepoint for codepoint in missing_codepoints if codepoint in fallback_cmap)
            for codepoint in resolved_codepoints:
                source_glyph_name = fallback_cmap[codepoint]
                new_glyph_name = _unique_fallback_glyph_name(font, codepoint)
                pen = TTGlyphPen(base_glyph_set)
                transform_pen = TransformPen(pen, (scale, 0, 0, scale, 0, 0))
                fallback_glyph_set[source_glyph_name].draw(transform_pen)
                font["glyf"].glyphs[new_glyph_name] = pen.glyph()
                glyph_order.append(new_glyph_name)
                advance_width, left_side_bearing = fallback_font["hmtx"].metrics[source_glyph_name]
                font["hmtx"].metrics[new_glyph_name] = (
                    round(advance_width * scale),
                    round(left_side_bearing * scale),
                )
                for subtable in unicode_cmap_tables:
                    subtable.cmap[codepoint] = new_glyph_name
                best_cmap[codepoint] = new_glyph_name
                missing_codepoints.remove(codepoint)
                glyph_order_changed = True
        finally:
            fallback_font.close()

    if glyph_order_changed:
        font.setGlyphOrder(glyph_order)
        font["glyf"].glyphOrder = glyph_order

    return best_cmap


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


def _family_key_for_run(run: etree._Element) -> str:
    run_font_names = set(_run_font_names(run))
    return "sans" if run_font_names & ARIAL_FONT_NAMES else "serif"


def _select_build_for_run(run: etree._Element, builds: dict[str, NorobotoBuild]) -> NorobotoBuild:
    family_key = _family_key_for_run(run)
    style_key = _style_key_for_run(run)
    return builds[f"{family_key}_{style_key}"]


def _required_codepoints_by_family(document_xml: bytes, text_xpath: str) -> dict[str, set[int]]:
    root = _parse_xml(document_xml)
    required_codepoints = {
        family_key: set()
        for family_key in {variant.family_key for variant in NOROBOTO_VARIANTS.values()}
    }
    for run, target in _require_target_text_elements(root, text_xpath, require_targets=False):
        family_key = _family_key_for_run(run)
        text_value = target.text or ""
        for character in text_value:
            codepoint = ord(character)
            if _should_preserve_codepoint(codepoint):
                continue
            required_codepoints[family_key].add(codepoint)
    return required_codepoints


def _supported_codepoints_for_variant(variant: NorobotoVariant, required_codepoints: set[int]) -> set[int]:
    supported_codepoints: set[int] = set()
    for font_path in (variant.base_font_path, *variant.fallback_font_paths):
        font = TTFont(str(font_path))
        try:
            best_cmap = font["cmap"].getBestCmap() or {}
            supported_codepoints.update(codepoint for codepoint in required_codepoints if codepoint in best_cmap)
        finally:
            font.close()
        if supported_codepoints == required_codepoints:
            break
    return supported_codepoints


def _family_mapping_for_variants(
    variants: list[NorobotoVariant],
    required_codepoints: set[int],
) -> PUAMapping:
    unsupported_codepoints = sorted(
        codepoint
        for codepoint in required_codepoints
        if not (0x20 <= codepoint <= 0xFFFF) or PUA_START <= codepoint <= PUA_END
    )
    if unsupported_codepoints:
        codepoint = unsupported_codepoints[0]
        raise ValueError(f"Character {chr(codepoint)!r} (U+{codepoint:04X}) is outside the supported BMP range")

    if not required_codepoints:
        return {}

    eligible_sets = [_supported_codepoints_for_variant(variant, required_codepoints) for variant in variants]
    eligible_codepoints = sorted(set.intersection(*eligible_sets)) if eligible_sets else []
    missing_codepoints = sorted(required_codepoints.difference(eligible_codepoints))
    if missing_codepoints:
        codepoint = missing_codepoints[0]
        raise ValueError(
            f"Character {chr(codepoint)!r} (U+{codepoint:04X}) is not available in the fallback stack for {variants[0].family_name}"
        )

    available_pua_codepoints = list(range(PUA_START, PUA_END + 1))
    required_pua_codepoints = len(eligible_codepoints) * PUA_VARIANTS_PER_CODEPOINT
    if required_pua_codepoints > len(available_pua_codepoints):
        raise ValueError(
            f"Document requires {required_pua_codepoints} randomized BMP Unicode codepoints, "
            f"but only {len(available_pua_codepoints)} BMP PUA slots are available"
        )

    shuffled_pua = available_pua_codepoints[:required_pua_codepoints]
    random.shuffle(shuffled_pua)
    return {
        codepoint: tuple(
            shuffled_pua[
                index * PUA_VARIANTS_PER_CODEPOINT : (index + 1) * PUA_VARIANTS_PER_CODEPOINT
            ]
        )
        for index, codepoint in enumerate(eligible_codepoints)
    }


def build_noroboto_font(variant: NorobotoVariant, mapping: PUAMapping) -> NorobotoBuild:
    font = TTFont(str(variant.base_font_path))
    best_cmap = _copy_fallback_glyphs(font, variant, set(mapping))
    base_glyph_set = font.getGlyphSet()
    glyph_order = list(font.getGlyphOrder())
    shuffled_glyph_names: dict[tuple[int, int], str] = {}
    for source_codepoint, shuffled_codepoints in mapping.items():
        if source_codepoint not in best_cmap:
            continue
        for shuffled_codepoint in shuffled_codepoints:
            shuffled_glyph_names[(source_codepoint, shuffled_codepoint)] = _unique_pua_clone_glyph_name(
                font,
                source_codepoint,
                shuffled_codepoint,
            )

    for (source_codepoint, _shuffled_codepoint), shuffled_glyph_name in shuffled_glyph_names.items():
        source_glyph_name = best_cmap[source_codepoint]
        _clone_glyph_with_perturbation(font, base_glyph_set, source_glyph_name, shuffled_glyph_name)
        font["hmtx"].metrics[shuffled_glyph_name] = font["hmtx"].metrics[source_glyph_name]
        glyph_order.append(shuffled_glyph_name)

    if shuffled_glyph_names:
        font.setGlyphOrder(glyph_order)
        font["glyf"].glyphOrder = glyph_order

    for subtable in font["cmap"].tables:
        if not subtable.isUnicode() or not hasattr(subtable, "cmap"):
            continue
        for source_codepoint, shuffled_codepoints in mapping.items():
            for shuffled_codepoint in shuffled_codepoints:
                glyph_name = shuffled_glyph_names.get((source_codepoint, shuffled_codepoint))
                if glyph_name is None:
                    continue
                subtable.cmap[shuffled_codepoint] = glyph_name

    if "post" in font:
        font["post"].formatType = 3.0

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


def build_noroboto_builds(required_codepoints_by_family: dict[str, set[int]]) -> dict[str, NorobotoBuild]:
    family_mappings = {
        family_key: _family_mapping_for_variants(
            [variant for variant in NOROBOTO_VARIANTS.values() if variant.family_key == family_key],
            required_codepoints_by_family.get(family_key, set()),
        )
        for family_key in {variant.family_key for variant in NOROBOTO_VARIANTS.values()}
    }
    return {
        key: build_noroboto_font(variant, family_mappings[variant.family_key])
        for key, variant in NOROBOTO_VARIANTS.items()
    }


def _target_text_part_names(payloads: dict[str, bytes]) -> list[str]:
    header_parts = sorted(
        part_name
        for part_name in payloads
        if part_name.startswith("word/header") and part_name.endswith(".xml")
    )
    footer_parts = sorted(
        part_name
        for part_name in payloads
        if part_name.startswith("word/footer") and part_name.endswith(".xml")
    )
    note_parts = [
        part_name
        for part_name in (DOCX_FOOTNOTES_PART, DOCX_ENDNOTES_PART)
        if part_name in payloads
    ]
    return [DOCX_DOCUMENT_PART, *header_parts, *footer_parts, *note_parts]


def _merge_required_codepoints_by_family(
    part_xml_payloads: list[bytes],
    text_xpath: str,
) -> dict[str, set[int]]:
    required_codepoints = {
        family_key: set()
        for family_key in {variant.family_key for variant in NOROBOTO_VARIANTS.values()}
    }
    for part_xml in part_xml_payloads:
        part_required_codepoints = _required_codepoints_by_family(part_xml, text_xpath)
        for family_key, codepoints in part_required_codepoints.items():
            required_codepoints[family_key].update(codepoints)
    return required_codepoints


def _require_target_text_elements(
    root: etree._Element,
    text_xpath: str,
    *,
    require_targets: bool = True,
) -> list[tuple[etree._Element, etree._Element]]:
    targets = root.xpath(text_xpath, namespaces=_xpath_namespaces(root))
    if not targets and require_targets:
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


def replace_text_with_pua_text(
    document_xml: bytes,
    text_xpath: str,
    builds: dict[str, NorobotoBuild],
    *,
    require_targets: bool = True,
) -> tuple[bytes, int, str]:
    root = _parse_xml(document_xml)
    replacement_count = 0
    selected_family_names: set[str] = set()
    for run, target in _require_target_text_elements(root, text_xpath, require_targets=require_targets):
        build = _select_build_for_run(run, builds)
        text_value = target.text or ""
        _ensure_run_uses_font(run, build.family_name)
        remapped_characters: list[str] = []
        for character in text_value:
            codepoint = ord(character)
            shuffled_codepoints = build.mapping.get(codepoint)
            if shuffled_codepoints is None and _should_preserve_codepoint(codepoint):
                remapped_characters.append(character)
                continue
            if shuffled_codepoints is None:
                raise ValueError(
                    f"Character {character!r} (U+{codepoint:04X}) is not available in the {build.display_name} mapping"
                )
            remapped_characters.append(chr(random.choice(shuffled_codepoints)))

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
    builds: dict[str, NorobotoBuild] | None = None,
) -> tuple[bytes, int, str]:
    input_buffer = BytesIO(docx_bytes)
    output_buffer = BytesIO()
    replacement_count = 0
    document_part_found = False
    selected_family_name = ""

    with zipfile.ZipFile(input_buffer, mode="r") as source_archive:
        original_infos = {info.filename: copy(info) for info in source_archive.infolist()}
        payloads = {info.filename: source_archive.read(info.filename) for info in source_archive.infolist()}
        target_part_names = _target_text_part_names(payloads)

        document_xml = payloads.get(DOCX_DOCUMENT_PART)
        if document_xml is None:
            raise KeyError(f"DOCX part not found: {DOCX_DOCUMENT_PART}")

        if builds is None:
            builds = build_noroboto_builds(
                _merge_required_codepoints_by_family(
                    [payloads[part_name] for part_name in target_part_names],
                    text_xpath,
                )
            )

        selected_family_names: set[str] = set()
        for part_name in target_part_names:
            payloads[part_name], part_replacement_count, part_family_name = replace_text_with_pua_text(
                payloads[part_name],
                text_xpath,
                builds,
                require_targets=part_name == DOCX_DOCUMENT_PART,
            )
            replacement_count += part_replacement_count
            if part_family_name:
                selected_family_names.update(part_family_name.split(", "))

        payloads[DOCX_DOCUMENT_PART] = _insert_root_disclosure_paragraph(
            payloads[DOCX_DOCUMENT_PART],
            builds[DISCLOSURE_PARAGRAPH_BUILD_KEY].family_name,
        )
        selected_family_name = ", ".join(sorted(selected_family_names))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Noroboto to a .docx file.")
    parser.add_argument("input_path", help="Path to the input .docx file")
    parser.add_argument(
        "output_path",
        nargs="?",
        default="noroboto.docx",
        help="Path to write the Noroboto output .docx file",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    updated_docx, replacement_count, selected_font_name = replace_text_element_with_pua_text(
        input_path.read_bytes(),
        DEFAULT_TEXT_XPATH,
    )
    written_path = _write_output_docx(updated_docx, output_path)
    print(
        f"Built {len(NOROBOTO_VARIANTS)} randomized Noroboto embedded fonts in memory; "
        f"used {selected_font_name} for substitution, replaced {replacement_count} characters, "
        f"and wrote {written_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
