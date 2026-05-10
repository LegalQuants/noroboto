from io import BytesIO
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from noroboto import DOCX_DOCUMENT_PART, DocxPackage


def _build_minimal_docx() -> bytes:
    document_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello backend</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
'''
    content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'''
    rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'''

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr(DOCX_DOCUMENT_PART, document_xml)
    return buffer.getvalue()


class DocxPackageTests(unittest.TestCase):
    def test_docx_package_reads_and_updates_document_xml(self) -> None:
        package = DocxPackage.from_bytes(_build_minimal_docx())

        self.assertTrue(package.has_part(DOCX_DOCUMENT_PART))
        self.assertEqual(list(package.iter_document_text()), ["Hello backend"])

        replacements = package.replace_document_text("backend", "service")

        self.assertEqual(replacements, 1)

        updated_package = DocxPackage.from_bytes(package.to_bytes())
        self.assertEqual(list(updated_package.iter_document_text()), ["Hello service"])


if __name__ == "__main__":
    unittest.main()