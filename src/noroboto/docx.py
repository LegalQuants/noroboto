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

ET.register_namespace("w", WORDPROCESSINGML_NS)


def _normalize_part_name(part_name: str) -> str:
    return part_name.lstrip("/")


def _serialize_xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _iter_text_elements(root: ET.Element) -> Iterator[ET.Element]:
    yield from root.iterfind(".//w:t", XML_NAMESPACES)


def replace_text(root: ET.Element, find: str, replace_with: str) -> int:
    if not find:
        raise ValueError("find must be a non-empty string")

    replacements = 0
    for text_node in _iter_text_elements(root):
        text_value = text_node.text or ""
        if find in text_value:
            text_node.text = text_value.replace(find, replace_with)
            replacements += text_value.count(find)
    return replacements


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

    def has_part(self, part_name: str) -> bool:
        return _normalize_part_name(part_name) in self.parts

    def read_bytes(self, part_name: str) -> bytes:
        normalized_name = _normalize_part_name(part_name)
        try:
            return self.parts[normalized_name]
        except KeyError as error:
            raise KeyError(f"DOCX part not found: {normalized_name}") from error

    def write_bytes(self, part_name: str, payload: bytes) -> None:
        self.parts[_normalize_part_name(part_name)] = payload

    def delete_part(self, part_name: str) -> None:
        self.parts.pop(_normalize_part_name(part_name), None)

    def read_xml(self, part_name: str) -> ET.Element:
        return ET.fromstring(self.read_bytes(part_name))

    def write_xml(self, part_name: str, root: ET.Element) -> None:
        self.write_bytes(part_name, _serialize_xml(root))

    def document_root(self) -> ET.Element:
        return self.read_xml(DOCX_DOCUMENT_PART)

    def iter_document_text(self) -> Iterator[str]:
        for text_node in _iter_text_elements(self.document_root()):
            if text_node.text:
                yield text_node.text

    def replace_document_text(self, find: str, replace_with: str) -> int:
        document_root = self.document_root()
        replacements = replace_text(document_root, find, replace_with)
        if replacements:
            self.write_xml(DOCX_DOCUMENT_PART, document_root)
        return replacements

    def to_bytes(self) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for part_name in sorted(self.parts):
                archive.writestr(part_name, self.parts[part_name])
        return buffer.getvalue()

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())
