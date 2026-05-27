from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Iterable, Literal
from uuid import uuid4

import pdfplumber
import pikepdf
from pikepdf import Array, Dictionary, Name, Stream

PUA_START = 0xE000
PUA_END = 0xF8FF
DISCLOSURE_TEXT = (
    "This document contains mitigations against review by automated systems. "
    "Recipients should ensure that they have read the contents on screen or in print. "
    "Recipients with bona fide vision impairments may be entitled to unmitigated documents upon request."
)
DISCLOSURE_LINE_LIMIT = 92
DEFAULT_PAGE_WIDTH = 612.0
DEFAULT_PAGE_HEIGHT = 792.0
BODY_FONT_RESOURCE_NAME = "F1"
DISCLOSURE_FONT_RESOURCE_NAME = "F2"
BODY_FONT_FAMILY = "Helvetica"
DISCLOSURE_FONT_FAMILY = "Helvetica-Oblique"
WINANSI_PRINTABLE_RANGE = range(0x20, 0x7F)
CUSTOM_ENCODING_BYTE_CODES = tuple(
    [code for code in range(0x01, 0x20) if code not in (0x09, 0x0A, 0x0D)]
    + list(range(0x80, 0xFF))
)
ObfuscationMode = Literal["total", "partial"]

_PUNCTUATION_GLYPH_NAMES = {
    "!": "exclam",
    '"': "quotedbl",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "quoteright",
    "(": "parenleft",
    ")": "parenright",
    "*": "asterisk",
    "+": "plus",
    ",": "comma",
    "-": "hyphen",
    ".": "period",
    "/": "slash",
    ":": "colon",
    ";": "semicolon",
    "<": "less",
    "=": "equal",
    ">": "greater",
    "?": "question",
    "@": "at",
    "[": "bracketleft",
    "\\": "backslash",
    "]": "bracketright",
    "^": "asciicircum",
    "_": "underscore",
    "`": "grave",
    "{": "braceleft",
    "|": "bar",
    "}": "braceright",
    "~": "asciitilde",
}
_DIGIT_GLYPH_NAMES = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}
_LATIN_SUPPLEMENT_GLYPH_NAMES = {
    " ": "space",
    "¡": "exclamdown",
    "¢": "cent",
    "£": "sterling",
    "¥": "yen",
    "§": "section",
    "¨": "dieresis",
    "©": "copyright",
    "«": "guillemotleft",
    "¬": "logicalnot",
    "®": "registered",
    "¯": "macron",
    "°": "degree",
    "±": "plusminus",
    "´": "acute",
    "µ": "mu",
    "¶": "paragraph",
    "·": "periodcentered",
    "¸": "cedilla",
    "»": "guillemotright",
    "¼": "onequarter",
    "½": "onehalf",
    "¾": "threequarters",
    "¿": "questiondown",
    "À": "Agrave",
    "Á": "Aacute",
    "Â": "Acircumflex",
    "Ã": "Atilde",
    "Ä": "Adieresis",
    "Å": "Aring",
    "Æ": "AE",
    "Ç": "Ccedilla",
    "È": "Egrave",
    "É": "Eacute",
    "Ê": "Ecircumflex",
    "Ë": "Edieresis",
    "Ì": "Igrave",
    "Í": "Iacute",
    "Î": "Icircumflex",
    "Ï": "Idieresis",
    "Ñ": "Ntilde",
    "Ò": "Ograve",
    "Ó": "Oacute",
    "Ô": "Ocircumflex",
    "Õ": "Otilde",
    "Ö": "Odieresis",
    "×": "multiply",
    "Ø": "Oslash",
    "Ù": "Ugrave",
    "Ú": "Uacute",
    "Û": "Ucircumflex",
    "Ü": "Udieresis",
    "Ý": "Yacute",
    "ß": "germandbls",
    "à": "agrave",
    "á": "aacute",
    "â": "acircumflex",
    "ã": "atilde",
    "ä": "adieresis",
    "å": "aring",
    "æ": "ae",
    "ç": "ccedilla",
    "è": "egrave",
    "é": "eacute",
    "ê": "ecircumflex",
    "ë": "edieresis",
    "ì": "igrave",
    "í": "iacute",
    "î": "icircumflex",
    "ï": "idieresis",
    "ñ": "ntilde",
    "ò": "ograve",
    "ó": "oacute",
    "ô": "ocircumflex",
    "õ": "otilde",
    "ö": "odieresis",
    "÷": "divide",
    "ø": "oslash",
    "ù": "ugrave",
    "ú": "uacute",
    "û": "ucircumflex",
    "ü": "udieresis",
    "ý": "yacute",
    "ÿ": "ydieresis",
}
_TYPOGRAPHIC_GLYPH_NAMES = {
    "–": "endash",
    "—": "emdash",
    "‘": "quoteleft",
    "’": "quoteright",
    "“": "quotedblleft",
    "”": "quotedblright",
    "•": "bullet",
    "…": "ellipsis",
    "€": "Euro",
    "¤": "currency",
    "¦": "brokenbar",
    "ª": "ordfeminine",
    "²": "twosuperior",
    "³": "threesuperior",
    "¹": "onesuperior",
    "º": "ordmasculine",
    "™": "trademark",
    "†": "dagger",
    "‡": "daggerdbl",
    "‰": "perthousand",
    "Ð": "Eth",
    "Þ": "Thorn",
    "ð": "eth",
    "þ": "thorn",
}


def _glyph_name_for_character(character: str) -> str | None:
    if len(character) != 1:
        return None
    if character.isalpha() and ord(character) < 128:
        return character
    if character in _DIGIT_GLYPH_NAMES:
        return _DIGIT_GLYPH_NAMES[character]
    if character in _PUNCTUATION_GLYPH_NAMES:
        return _PUNCTUATION_GLYPH_NAMES[character]
    if character in _LATIN_SUPPLEMENT_GLYPH_NAMES:
        return _LATIN_SUPPLEMENT_GLYPH_NAMES[character]
    if character in _TYPOGRAPHIC_GLYPH_NAMES:
        return _TYPOGRAPHIC_GLYPH_NAMES[character]
    return None


def _winansi_byte_for_character(character: str) -> int | None:
    if len(character) != 1:
        return None
    codepoint = ord(character)
    if codepoint in WINANSI_PRINTABLE_RANGE:
        return codepoint
    return None


@dataclass(frozen=True)
class PdfCharacter:
    text: str
    x0: float
    y0: float
    width: float
    height: float
    font_size: float


@dataclass(frozen=True)
class PdfPage:
    width: float
    height: float
    characters: tuple[PdfCharacter, ...]


@dataclass
class _ByteCodePool:
    available: list[int] = field(default_factory=lambda: list(CUSTOM_ENCODING_BYTE_CODES))
    rng: random.Random | None = None

    def reserve(self, count: int) -> list[int]:
        if count > len(self.available):
            raise ValueError(
                f"Custom encoding requires {count} byte codes, but only {len(self.available)} remain free."
            )
        if self.rng is not None:
            self.rng.shuffle(self.available)
        reserved = self.available[:count]
        self.available = self.available[count:]
        return reserved


@dataclass
class _SubstitutionPlan:
    visible_text: str
    extracted_text: str
    byte_codes: tuple[int, ...]
    byte_code_to_glyph_name: dict[int, str]
    byte_code_to_unicode_target: dict[int, str]


@dataclass
class _ObfuscationRecipe:
    mode: ObfuscationMode
    body_byte_code_for_character: dict[str, int]
    byte_code_to_glyph_name: dict[int, str]
    byte_code_to_unicode_target: dict[int, str]
    substitutions: tuple[_SubstitutionPlan, ...] = ()


def _extract_pages(pdf_bytes: bytes) -> tuple[PdfPage, ...]:
    pages: list[PdfPage] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            characters: list[PdfCharacter] = []
            for character in page.chars:
                text = str(character.get("text", ""))
                if not text:
                    continue
                font_size = float(character.get("size") or character.get("height") or 11.0)
                if font_size <= 0:
                    font_size = 11.0
                characters.append(
                    PdfCharacter(
                        text=text,
                        x0=float(character.get("x0", 0.0)),
                        y0=float(character.get("y0", 0.0)),
                        width=float(character.get("width", 0.0)),
                        height=float(character.get("height", 0.0)),
                        font_size=font_size,
                    )
                )
            pages.append(
                PdfPage(
                    width=float(page.width) if page.width else DEFAULT_PAGE_WIDTH,
                    height=float(page.height) if page.height else DEFAULT_PAGE_HEIGHT,
                    characters=tuple(characters),
                )
            )
    return tuple(pages)


def _build_total_recipe(
    pages: tuple[PdfPage, ...], *, rng: random.Random
) -> _ObfuscationRecipe:
    unique_characters = sorted(
        {
            character.text
            for page in pages
            for character in page.characters
            if not character.text.isspace() and _glyph_name_for_character(character.text) is not None
        }
    )
    pool = _ByteCodePool(rng=rng)
    available_pua_codepoints = list(range(PUA_START, PUA_END + 1))
    rng.shuffle(available_pua_codepoints)
    reserved_byte_codes = pool.reserve(len(unique_characters))

    body_byte_code_for_character: dict[str, int] = {}
    byte_code_to_glyph_name: dict[int, str] = {}
    byte_code_to_unicode_target: dict[int, str] = {}
    for index, character in enumerate(unique_characters):
        glyph_name = _glyph_name_for_character(character)
        if glyph_name is None:
            continue
        byte_code = reserved_byte_codes[index]
        body_byte_code_for_character[character] = byte_code
        byte_code_to_glyph_name[byte_code] = glyph_name
        byte_code_to_unicode_target[byte_code] = chr(available_pua_codepoints[index])

    return _ObfuscationRecipe(
        mode="total",
        body_byte_code_for_character=body_byte_code_for_character,
        byte_code_to_glyph_name=byte_code_to_glyph_name,
        byte_code_to_unicode_target=byte_code_to_unicode_target,
    )


def _build_partial_recipe(
    substitutions: Iterable[tuple[str, str]],
    *,
    rng: random.Random,
) -> _ObfuscationRecipe:
    pool = _ByteCodePool(rng=rng)
    substitution_plans: list[_SubstitutionPlan] = []
    aggregate_byte_code_to_glyph_name: dict[int, str] = {}
    aggregate_byte_code_to_unicode_target: dict[int, str] = {}

    for visible_text, extracted_text in substitutions:
        if not visible_text:
            raise ValueError("Partial substitution requires a non-empty visible string")
        visible_glyph_names: list[str] = []
        for character in visible_text:
            glyph_name = _glyph_name_for_character(character)
            if glyph_name is None:
                raise ValueError(
                    f"Visible character {character!r} (U+{ord(character):04X}) is outside the Helvetica encoding set"
                )
            visible_glyph_names.append(glyph_name)

        reserved_byte_codes = pool.reserve(len(visible_text))
        plan_byte_code_to_glyph_name: dict[int, str] = {}
        plan_byte_code_to_unicode_target: dict[int, str] = {}
        for position, byte_code in enumerate(reserved_byte_codes):
            plan_byte_code_to_glyph_name[byte_code] = visible_glyph_names[position]
            if position < len(extracted_text):
                plan_byte_code_to_unicode_target[byte_code] = extracted_text[position]
            else:
                plan_byte_code_to_unicode_target[byte_code] = "﻿"
        if len(extracted_text) > len(visible_text) and reserved_byte_codes:
            trailing_extracted = extracted_text[len(visible_text) :]
            last_byte_code = reserved_byte_codes[-1]
            plan_byte_code_to_unicode_target[last_byte_code] = (
                plan_byte_code_to_unicode_target[last_byte_code] + trailing_extracted
            )

        substitution_plans.append(
            _SubstitutionPlan(
                visible_text=visible_text,
                extracted_text=extracted_text,
                byte_codes=tuple(reserved_byte_codes),
                byte_code_to_glyph_name=plan_byte_code_to_glyph_name,
                byte_code_to_unicode_target=plan_byte_code_to_unicode_target,
            )
        )
        aggregate_byte_code_to_glyph_name.update(plan_byte_code_to_glyph_name)
        aggregate_byte_code_to_unicode_target.update(plan_byte_code_to_unicode_target)

    return _ObfuscationRecipe(
        mode="partial",
        body_byte_code_for_character={},
        byte_code_to_glyph_name=aggregate_byte_code_to_glyph_name,
        byte_code_to_unicode_target=aggregate_byte_code_to_unicode_target,
        substitutions=tuple(substitution_plans),
    )


def _differences_array(byte_code_to_glyph_name: dict[int, str]) -> Array:
    entries: list = []
    sorted_codes = sorted(byte_code_to_glyph_name)
    previous_code: int | None = None
    for byte_code in sorted_codes:
        if previous_code is None or byte_code != previous_code + 1:
            entries.append(byte_code)
        entries.append(Name(f"/{byte_code_to_glyph_name[byte_code]}"))
        previous_code = byte_code
    return Array(entries)


_TOUNICODE_HEADER = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo
<< /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
"""
_TOUNICODE_FOOTER = b"""endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


def _utf16be_hex(text: str) -> str:
    return text.encode("utf-16-be").hex().upper()


def _build_tounicode_cmap(
    byte_code_to_unicode_target: dict[int, str], *, include_winansi_identity: bool
) -> bytes:
    mapping: dict[int, str] = dict(byte_code_to_unicode_target)
    if include_winansi_identity:
        for codepoint in WINANSI_PRINTABLE_RANGE:
            mapping.setdefault(codepoint, chr(codepoint))
    body = io.BytesIO()
    body.write(_TOUNICODE_HEADER)
    items = sorted(mapping.items())
    if items:
        for chunk_start in range(0, len(items), 100):
            chunk = items[chunk_start : chunk_start + 100]
            body.write(f"{len(chunk)} beginbfchar\n".encode("ascii"))
            for byte_code, target_text in chunk:
                body.write(
                    f"<{byte_code:02X}> <{_utf16be_hex(target_text)}>\n".encode("ascii")
                )
            body.write(b"endbfchar\n")
    body.write(_TOUNICODE_FOOTER)
    return body.getvalue()


def _encode_total_character(character: str, recipe: _ObfuscationRecipe) -> int | None:
    if character.isspace():
        return 0x20
    byte_code = recipe.body_byte_code_for_character.get(character)
    if byte_code is not None:
        return byte_code
    return recipe.body_byte_code_for_character.get("?")


def _find_substitution_runs(
    characters: tuple[PdfCharacter, ...], substitutions: tuple[_SubstitutionPlan, ...]
) -> dict[int, tuple[int, int]]:
    """Map each substitution-covered character index to (substitution_index, position_within_substitution)."""
    coverage: dict[int, tuple[int, int]] = {}
    rendered_text = "".join(character.text for character in characters)
    occupied: set[int] = set()
    for substitution_index, plan in enumerate(substitutions):
        search_start = 0
        while True:
            position = rendered_text.find(plan.visible_text, search_start)
            if position == -1:
                break
            indexes = range(position, position + len(plan.visible_text))
            if any(index in occupied for index in indexes):
                search_start = position + 1
                continue
            for offset, index in enumerate(indexes):
                coverage[index] = (substitution_index, offset)
                occupied.add(index)
            search_start = position + len(plan.visible_text)
    return coverage


def _encode_partial_character(
    character: PdfCharacter,
    character_index: int,
    coverage: dict[int, tuple[int, int]],
    recipe: _ObfuscationRecipe,
) -> int | None:
    coverage_entry = coverage.get(character_index)
    if coverage_entry is not None:
        substitution_index, position = coverage_entry
        plan = recipe.substitutions[substitution_index]
        return plan.byte_codes[position]
    return _winansi_byte_for_character(character.text)


def _disclosure_lines(text: str, line_character_limit: int) -> list[str]:
    if line_character_limit <= 0:
        return [text]
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current_line = ""
    for word in words:
        if not current_line:
            current_line = word
            continue
        candidate_line = f"{current_line} {word}"
        if len(candidate_line) > line_character_limit:
            lines.append(current_line)
            current_line = word
        else:
            current_line = candidate_line
    if current_line:
        lines.append(current_line)
    return lines


def _format_pdf_number(value: float) -> str:
    rounded_value = round(value, 3)
    if rounded_value == int(rounded_value):
        return str(int(rounded_value))
    return f"{rounded_value:.3f}".rstrip("0").rstrip(".")


def _build_text_command(
    *,
    font_resource_name: str,
    font_size: float,
    x_position: float,
    y_position: float,
    body_bytes: bytes,
) -> bytes:
    return (
        b"BT\n"
        + f"/{font_resource_name} {_format_pdf_number(font_size)} Tf\n".encode("ascii")
        + f"1 0 0 1 {_format_pdf_number(x_position)} {_format_pdf_number(y_position)} Tm\n".encode("ascii")
        + b"<"
        + body_bytes.hex().upper().encode("ascii")
        + b"> Tj\n"
        + b"ET\n"
    )


def _build_disclosure_block(
    *,
    page_width: float,
    page_height: float,
    disclosure_font_size: float,
    disclosure_line_leading: float,
    margin: float,
) -> tuple[bytes, float]:
    lines = _disclosure_lines(DISCLOSURE_TEXT, DISCLOSURE_LINE_LIMIT)
    top_y = page_height - margin
    block_height = len(lines) * disclosure_font_size * disclosure_line_leading
    content = bytearray()
    for line_index, line_text in enumerate(lines):
        line_y = top_y - (line_index + 1) * disclosure_font_size * disclosure_line_leading
        content.extend(
            _build_text_command(
                font_resource_name=DISCLOSURE_FONT_RESOURCE_NAME,
                font_size=disclosure_font_size,
                x_position=margin,
                y_position=line_y,
                body_bytes=line_text.encode("latin-1", errors="replace"),
            )
        )
    return bytes(content), block_height


def _build_page_content(
    *,
    page: PdfPage,
    recipe: _ObfuscationRecipe,
    is_first_page: bool,
    disclosure_font_size: float,
    disclosure_line_leading: float,
    margin: float,
    disclosure_gap: float,
) -> bytes:
    content = bytearray()
    body_y_offset = 0.0
    if is_first_page:
        disclosure_block_bytes, disclosure_block_height = _build_disclosure_block(
            page_width=page.width,
            page_height=page.height,
            disclosure_font_size=disclosure_font_size,
            disclosure_line_leading=disclosure_line_leading,
            margin=margin,
        )
        content.extend(disclosure_block_bytes)
        body_y_offset = disclosure_block_height + disclosure_gap

    coverage: dict[int, tuple[int, int]] = {}
    if recipe.mode == "partial":
        coverage = _find_substitution_runs(page.characters, recipe.substitutions)

    for character_index, character in enumerate(page.characters):
        if character.text.isspace():
            continue
        if recipe.mode == "total":
            byte_code = _encode_total_character(character.text, recipe)
        else:
            byte_code = _encode_partial_character(character, character_index, coverage, recipe)
        if byte_code is None:
            continue
        content.extend(
            _build_text_command(
                font_resource_name=BODY_FONT_RESOURCE_NAME,
                font_size=character.font_size,
                x_position=character.x0,
                y_position=character.y0 - body_y_offset,
                body_bytes=bytes((byte_code,)),
            )
        )
    return bytes(content)


def _build_body_font_dictionary(
    pdf: pikepdf.Pdf, recipe: _ObfuscationRecipe
) -> Dictionary:
    tounicode_stream = Stream(
        pdf,
        _build_tounicode_cmap(
            recipe.byte_code_to_unicode_target,
            include_winansi_identity=(recipe.mode == "partial"),
        ),
    )
    return pdf.make_indirect(
        Dictionary(
            Type=Name("/Font"),
            Subtype=Name("/Type1"),
            BaseFont=Name(f"/{BODY_FONT_FAMILY}"),
            Encoding=Dictionary(
                Type=Name("/Encoding"),
                BaseEncoding=Name("/WinAnsiEncoding"),
                Differences=_differences_array(recipe.byte_code_to_glyph_name),
            ),
            ToUnicode=tounicode_stream,
        )
    )


def _build_disclosure_font_dictionary(pdf: pikepdf.Pdf) -> Dictionary:
    return pdf.make_indirect(
        Dictionary(
            Type=Name("/Font"),
            Subtype=Name("/Type1"),
            BaseFont=Name(f"/{DISCLOSURE_FONT_FAMILY}"),
            Encoding=Name("/WinAnsiEncoding"),
        )
    )


def _build_output_pdf(
    pages: tuple[PdfPage, ...],
    recipe: _ObfuscationRecipe,
    *,
    disclosure_font_size: float = 9.0,
    disclosure_line_leading: float = 1.25,
    margin: float = 36.0,
    disclosure_gap: float = 18.0,
    source_title: str | None = None,
) -> bytes:
    pdf = pikepdf.Pdf.new()
    with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
        metadata["dc:title"] = source_title or "Noroboto-processed document"
        metadata["pdf:Producer"] = "Noroboto"
    pdf.docinfo["/Producer"] = "Noroboto"
    pdf.docinfo["/Title"] = source_title or "Noroboto-processed document"

    body_font = _build_body_font_dictionary(pdf, recipe)
    disclosure_font = _build_disclosure_font_dictionary(pdf)

    for page_index, page in enumerate(pages):
        page_width = page.width or DEFAULT_PAGE_WIDTH
        page_height = page.height or DEFAULT_PAGE_HEIGHT
        content_bytes = _build_page_content(
            page=page,
            recipe=recipe,
            is_first_page=page_index == 0,
            disclosure_font_size=disclosure_font_size,
            disclosure_line_leading=disclosure_line_leading,
            margin=margin,
            disclosure_gap=disclosure_gap,
        )
        if not content_bytes:
            content_bytes = b"BT ET\n"
        content_stream = Stream(pdf, content_bytes)
        page_dictionary = Dictionary(
            Type=Name("/Page"),
            MediaBox=Array([0, 0, page_width, page_height]),
            Resources=Dictionary(
                Font=Dictionary(
                    F1=body_font,
                    F2=disclosure_font,
                ),
            ),
            Contents=content_stream,
        )
        pdf.pages.append(pikepdf.Page(pdf.make_indirect(page_dictionary)))

    output_buffer = BytesIO()
    pdf.save(output_buffer)
    return output_buffer.getvalue()


def replace_text_with_pua_text_pdf(
    pdf_bytes: bytes,
    *,
    mode: ObfuscationMode = "total",
    substitutions: Iterable[tuple[str, str]] | None = None,
    seed: int | None = None,
) -> tuple[bytes, int, str]:
    if mode not in ("total", "partial"):
        raise ValueError(f"Unsupported obfuscation mode: {mode!r}")
    rng = random.Random(seed if seed is not None else int(uuid4().int & 0xFFFFFFFF))
    pages = _extract_pages(pdf_bytes)
    if not pages:
        raise ValueError("Input PDF has no pages")

    if mode == "total":
        recipe = _build_total_recipe(pages, rng=rng)
        if "?" not in recipe.body_byte_code_for_character:
            extended_characters = sorted({*recipe.body_byte_code_for_character.keys(), "?"})
            pool = _ByteCodePool(rng=rng)
            pool.available = [
                code
                for code in CUSTOM_ENCODING_BYTE_CODES
                if code not in recipe.byte_code_to_glyph_name
            ]
            reserved = pool.reserve(1)
            byte_code = reserved[0]
            recipe.body_byte_code_for_character["?"] = byte_code
            recipe.byte_code_to_glyph_name[byte_code] = "question"
            recipe.byte_code_to_unicode_target[byte_code] = chr(PUA_END)
            del extended_characters
    else:
        if substitutions is None:
            raise ValueError("Partial obfuscation requires at least one substitution")
        substitutions_list = list(substitutions)
        if not substitutions_list:
            raise ValueError("Partial obfuscation requires at least one substitution")
        recipe = _build_partial_recipe(substitutions_list, rng=rng)

    output_bytes = _build_output_pdf(pages, recipe)

    if mode == "total":
        replacement_count = sum(
            1
            for page in pages
            for character in page.characters
            if not character.text.isspace() and character.text in recipe.body_byte_code_for_character
        )
    else:
        replacement_count = 0
        for page in pages:
            page_text = "".join(character.text for character in page.characters)
            for plan in recipe.substitutions:
                occurrence_count = page_text.count(plan.visible_text)
                replacement_count += occurrence_count * len(plan.visible_text)
    return output_bytes, replacement_count, BODY_FONT_FAMILY


def write_obfuscated_pdf(
    input_path: Path,
    output_path: Path,
    *,
    mode: ObfuscationMode = "total",
    substitutions: Iterable[tuple[str, str]] | None = None,
    seed: int | None = None,
) -> tuple[Path, int, str]:
    obfuscated_bytes, replacement_count, font_family = replace_text_with_pua_text_pdf(
        input_path.read_bytes(),
        mode=mode,
        substitutions=substitutions,
        seed=seed,
    )
    try:
        output_path.write_bytes(obfuscated_bytes)
        written_path = output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}-generated{output_path.suffix}")
        fallback_path.write_bytes(obfuscated_bytes)
        written_path = fallback_path
    return written_path, replacement_count, font_family
