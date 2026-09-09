from __future__ import annotations

import logging
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from media_cron.metadata.models import BookMetadata

logger = logging.getLogger(__name__)

OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class EPUBMetadataInjector:
    """Injects and normalizes metadata inside standard EPUB containers with atomic writing."""

    def inject(self, epub_path: Path, metadata: BookMetadata) -> None:
        if not epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

        # Validate that this is a valid zip container
        try:
            with zipfile.ZipFile(epub_path, "r") as zf:
                namelist = zf.namelist()
                if "META-INF/container.xml" not in namelist:
                    raise ValueError(f"Missing META-INF/container.xml in EPUB: {epub_path}")
                container_data = zf.read("META-INF/container.xml")
        except Exception as e:
            raise ValueError(f"Corrupt or invalid EPUB container {epub_path}: {e}") from e

        c_root = ET.fromstring(container_data)
        opf_path: str | None = None
        for elem in c_root.iter():
            if elem.tag.endswith("rootfile"):
                opf_path = elem.attrib.get("full-path")
                break

        if not opf_path:
            raise ValueError(f"No rootfile OPF path defined in container.xml: {epub_path}")

        with zipfile.ZipFile(epub_path, "r") as zf:
            if opf_path not in zf.namelist():
                raise ValueError(f"OPF path '{opf_path}' not present in EPUB archive")
            opf_data = zf.read(opf_path)

        updated_opf = self._update_opf_xml(opf_data, metadata)

        # Atomic replacement: write to temp file then os.replace
        temp_dir = epub_path.parent
        fd, temp_file_path = tempfile.mkstemp(suffix=".epub.tmp", dir=temp_dir)
        os.close(fd)
        temp_path = Path(temp_file_path)

        try:
            with zipfile.ZipFile(epub_path, "r") as src_zf:
                with zipfile.ZipFile(temp_path, "w") as dst_zf:
                    # 1. mimetype MUST be the first file and uncompressed
                    dst_zf.writestr(
                        "mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED
                    )

                    # 2. Copy all other files, substituting the OPF
                    for item in src_zf.infolist():
                        if item.filename == "mimetype":
                            continue
                        if item.filename == opf_path:
                            dst_zf.writestr(
                                item.filename, updated_opf, compress_type=zipfile.ZIP_DEFLATED
                            )
                        else:
                            content = src_zf.read(item.filename)
                            dst_zf.writestr(item, content)

            os.replace(temp_path, epub_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _update_opf_xml(self, opf_bytes: bytes, metadata: BookMetadata) -> bytes:
        ET.register_namespace("", "http://www.idpf.org/2007/opf")
        ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")

        root = ET.fromstring(opf_bytes)
        meta_elem = None
        for elem in root:
            if elem.tag.endswith("metadata"):
                meta_elem = elem
                break

        if meta_elem is None:
            meta_elem = ET.SubElement(root, "{http://www.idpf.org/2007/opf}metadata")

        # Update or set title
        title_elem = meta_elem.find("{http://purl.org/dc/elements/1.1/}title")
        if title_elem is None:
            title_elem = ET.SubElement(meta_elem, "{http://purl.org/dc/elements/1.1/}title")
        title_elem.text = metadata.title

        # Update or set author / creator
        creator_elem = meta_elem.find("{http://purl.org/dc/elements/1.1/}creator")
        if creator_elem is None:
            creator_elem = ET.SubElement(meta_elem, "{http://purl.org/dc/elements/1.1/}creator")
        creator_elem.text = metadata.author

        # Update or set date
        if metadata.publication_year:
            date_elem = meta_elem.find("{http://purl.org/dc/elements/1.1/}date")
            if date_elem is None:
                date_elem = ET.SubElement(meta_elem, "{http://purl.org/dc/elements/1.1/}date")
            date_elem.text = str(metadata.publication_year)

        # Update or set publisher
        if metadata.publisher:
            pub_elem = meta_elem.find("{http://purl.org/dc/elements/1.1/}publisher")
            if pub_elem is None:
                pub_elem = ET.SubElement(meta_elem, "{http://purl.org/dc/elements/1.1/}publisher")
            pub_elem.text = metadata.publisher

        # Update or set identifier (ISBN)
        if metadata.isbn:
            isbn_found = False
            for ident in meta_elem.findall("{http://purl.org/dc/elements/1.1/}identifier"):
                if (
                    ident.attrib.get("id") == "isbn"
                    or "isbn" in ident.attrib.get("scheme", "").lower()
                ):
                    ident.text = f"urn:isbn:{metadata.isbn}"
                    isbn_found = True
                    break
            if not isbn_found:
                new_ident = ET.SubElement(
                    meta_elem,
                    "{http://purl.org/dc/elements/1.1/}identifier",
                    {"id": "isbn", "scheme": "ISBN"},
                )
                new_ident.text = f"urn:isbn:{metadata.isbn}"

        # Subjects
        existing_subjects = [
            elem.text
            for elem in meta_elem.findall("{http://purl.org/dc/elements/1.1/}subject")
            if elem.text
        ]
        target_subjects = list(metadata.subjects)
        if metadata.udc_code:
            udc_tag = f"UDC: {metadata.udc_code}"
            if udc_tag not in target_subjects:
                target_subjects.append(udc_tag)

        for s in target_subjects:
            if s not in existing_subjects:
                sub_elem = ET.SubElement(meta_elem, "{http://purl.org/dc/elements/1.1/}subject")
                sub_elem.text = s

        # Series meta
        if metadata.series_name:
            series_meta = None
            for m in meta_elem.findall("{http://www.idpf.org/2007/opf}meta"):
                if m.attrib.get("name") == "calibre:series":
                    series_meta = m
                    break
            if series_meta is None:
                series_meta = ET.SubElement(
                    meta_elem, "{http://www.idpf.org/2007/opf}meta", {"name": "calibre:series"}
                )
            series_meta.attrib["content"] = metadata.series_name

        if metadata.volume_number:
            vol_meta = None
            for m in meta_elem.findall("{http://www.idpf.org/2007/opf}meta"):
                if m.attrib.get("name") == "calibre:series_index":
                    vol_meta = m
                    break
            if vol_meta is None:
                vol_meta = ET.SubElement(
                    meta_elem,
                    "{http://www.idpf.org/2007/opf}meta",
                    {"name": "calibre:series_index"},
                )
            vol_meta.attrib["content"] = str(metadata.volume_number)

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
