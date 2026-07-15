"""
docx_stripper.py — DOCX metadata reader/stripper.

Part of the Document Metadata Anonymizer project. This module reads and
strips hidden metadata from Microsoft Word (.docx) files:

  * Standard document properties (docProps/core.xml)      -> T07 / T08
  * Comment author identities (word/comments.xml)          -> T09
  * Tracked-change (w:ins / w:del / *Change) authors        -> T09
  * Attached-template file paths (word/settings.xml)        -> T09

Design notes
------------
A .docx file is a ZIP package of XML parts (OPC / OOXML). `python-docx`
gives convenient access to `core_properties`, but it has no API at all
for comments, tracked changes, or template attachments — those live in
XML that python-docx never parses. To reach them we open the .docx as a
plain zip archive and edit the raw XML with `lxml.etree`, then splice the
modified parts back into the archive byte-for-byte, leaving every other
part (document.xml's *content*, media, styles, fonts, etc.) untouched.

This keeps the visible content/layout/formatting intact while removing
every field capable of leaking a real person's name, workstation ID, or
internal file-path.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from typing import Any, Dict, List, Optional

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml import etree

# --------------------------------------------------------------------------
# Namespaces / constants
# --------------------------------------------------------------------------

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Elements (besides w:ins / w:del) that also carry a w:author attribute
# when Word records a formatting or paragraph-property change.
TRACKED_CHANGE_TAGS = (
    "ins", "del", "rPrChange", "pPrChange", "tblPrChange",
    "tcPrChange", "trPrChange", "sectPrChange", "numberingChange",
)

# core_properties fields we read/clear. Mirrors python-docx's CoreProperties
# attribute names 1:1 so read_metadata()/strip_metadata() stay in sync with
# whatever python-docx exposes.
STRING_CORE_FIELDS = [
    "author", "category", "comments", "content_status", "identifier",
    "keywords", "language", "last_modified_by", "subject", "title",
    "version",
]
DATE_CORE_FIELDS = ["created", "modified", "last_printed"]
INT_CORE_FIELDS = ["revision"]

COMMENTS_PART = "word/comments.xml"
DOCUMENT_PART = "word/document.xml"
SETTINGS_PART = "word/settings.xml"
SETTINGS_RELS_PART = "word/_rels/settings.xml.rels"
APP_PROPS_PART = "docProps/app.xml"

EXTENDED_PROPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"

# "company" lives in docProps/app.xml (Extended Properties), not
# docProps/core.xml, so python-docx's core_properties never sees it even
# though it's one of the most identity-revealing fields in the file.
# "manager" lives alongside it and leaks the same way.
APP_XML_FIELDS = {"company": "Company", "manager": "Manager"}


class DocxMetadataError(Exception):
    """Raised for any .docx that cannot be safely read, parsed, or written.

    Covers files that are missing, not a valid ZIP/OPC package (including
    password-protected files, which are not plain OOXML zips and fail the
    same way), or that are otherwise corrupted.
    """


def _q(tag: str) -> str:
    """Expand an unprefixed tag name (e.g. 'author') to a Clark-notation
    qualified name in the WordprocessingML namespace (e.g. '{...}author')."""
    return f"{{{NS['w']}}}{tag}"


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------

def _load_zip_part(zf: zipfile.ZipFile, name: str) -> Optional[etree._Element]:
    """Return the parsed XML root of a part, or None if it doesn't exist."""
    if name not in zf.namelist():
        return None
    return etree.fromstring(zf.read(name))


def _serialize(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _open_document(filepath: str) -> Document:
    if not os.path.isfile(filepath):
        raise DocxMetadataError(f"File not found: {filepath}")
    try:
        return Document(filepath)
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise DocxMetadataError(
            f"Could not open '{filepath}' as a .docx file. It may be "
            f"corrupted, password-protected, or not a valid Word document."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface any other parse failure clearly
        raise DocxMetadataError(
            f"Unexpected error reading '{filepath}': {exc}"
        ) from exc


def _open_zip(filepath: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(filepath, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocxMetadataError(
            f"Could not open '{filepath}' as a .docx package: {exc}"
        ) from exc


def _stringify(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


# --------------------------------------------------------------------------
# Readers for each leak surface
# --------------------------------------------------------------------------

def _read_core_properties(document: Document) -> Dict[str, Any]:
    props = document.core_properties
    data: Dict[str, Any] = {}
    for field in STRING_CORE_FIELDS + DATE_CORE_FIELDS + INT_CORE_FIELDS:
        data[field] = _stringify(getattr(props, field, None))
    return data


def _read_comment_authors(zf: zipfile.ZipFile) -> List[str]:
    root = _load_zip_part(zf, COMMENTS_PART)
    if root is None:
        return []
    authors = []
    for comment in root.findall(_q("comment")):
        author = comment.get(_q("author"))
        if author:
            authors.append(author)
    return authors


def _read_tracked_change_authors(zf: zipfile.ZipFile) -> List[str]:
    root = _load_zip_part(zf, DOCUMENT_PART)
    if root is None:
        return []
    authors = set()
    for tag in TRACKED_CHANGE_TAGS:
        for el in root.iter(_q(tag)):
            author = el.get(_q("author"))
            if author:
                authors.add(author)
    return sorted(authors)


def _read_app_xml_fields(zf: zipfile.ZipFile) -> Dict[str, Optional[str]]:
    """Read Company/Manager out of docProps/app.xml (Extended Properties)."""
    result: Dict[str, Optional[str]] = {key: None for key in APP_XML_FIELDS}
    root = _load_zip_part(zf, APP_PROPS_PART)
    if root is None:
        return result
    for key, tag in APP_XML_FIELDS.items():
        el = root.find(f"{{{EXTENDED_PROPS_NS}}}{tag}")
        if el is not None and el.text:
            result[key] = el.text
    return result


def _read_template_path(zf: zipfile.ZipFile) -> Optional[str]:
    root = _load_zip_part(zf, SETTINGS_PART)
    if root is None:
        return None
    el = root.find(_q("attachedTemplate"))
    if el is None:
        return None
    rid = el.get(f"{{{NS['r']}}}id")
    if not rid:
        return None
    rels_root = _load_zip_part(zf, SETTINGS_RELS_PART)
    if rels_root is None:
        return None
    for rel in rels_root:
        if rel.get("Id") == rid:
            return rel.get("Target")
    return None


def read_metadata(filepath: str) -> dict:
    """Read every metadata field this module knows how to find in a .docx.

    Args:
        filepath: Path to the .docx file to inspect.

    Returns:
        A flat dict combining core document properties with
        ``comment_authors`` (list[str]), ``tracked_change_authors``
        (list[str]), and ``template_path`` (str | None).

    Raises:
        DocxMetadataError: if the file doesn't exist, isn't a valid .docx
            package, or is password-protected/corrupted.
    """
    document = _open_document(filepath)
    data = _read_core_properties(document)

    with _open_zip(filepath) as zf:
        data["comment_authors"] = _read_comment_authors(zf)
        data["tracked_change_authors"] = _read_tracked_change_authors(zf)
        data["template_path"] = _read_template_path(zf)
        data.update(_read_app_xml_fields(zf))

    return data


# --------------------------------------------------------------------------
# Stripping
# --------------------------------------------------------------------------

_DATE_FIELD_TO_XML_REMOVER = {
    "created": "_remove_created",
    "modified": "_remove_modified",
    "last_printed": "_remove_lastPrinted",
}


def _strip_core_properties(document: Document) -> Dict[str, Any]:
    """Clear core_properties in place; return what was present beforehand."""
    props = document.core_properties
    before: Dict[str, Any] = {}
    for field in STRING_CORE_FIELDS:
        value = getattr(props, field, None)
        before[field] = value
        if value:
            setattr(props, field, "")
    for field in DATE_CORE_FIELDS:
        value = getattr(props, field, None)
        before[field] = _stringify(value)
        if value is not None:
            # python-docx's date setters reject None (they require a real
            # datetime), so drop the underlying XML element instead of
            # trying to assign an empty value through the property API.
            getattr(props._element, _DATE_FIELD_TO_XML_REMOVER[field])()
    for field in INT_CORE_FIELDS:
        value = getattr(props, field, None)
        before[field] = value
        if value:
            # cp:revision is defined as xsd:positiveInteger in the OOXML
            # schema (and python-docx enforces this) - 0 is invalid, so
            # the closest thing to "cleared" is resetting to 1.
            setattr(props, field, 1)
    return before


def _strip_comments_xml(xml_bytes: bytes) -> tuple[bytes, List[str]]:
    root = etree.fromstring(xml_bytes)
    removed = []
    for comment in root.findall(_q("comment")):
        author = comment.get(_q("author"))
        if author:
            removed.append(author)
        comment.set(_q("author"), "")
        comment.set(_q("initials"), "")
        if _q("date") in comment.attrib:
            comment.set(_q("date"), "1970-01-01T00:00:00Z")
    return _serialize(root), removed


def _strip_tracked_changes_xml(xml_bytes: bytes) -> tuple[bytes, List[str]]:
    root = etree.fromstring(xml_bytes)
    removed = set()
    for tag in TRACKED_CHANGE_TAGS:
        for el in root.iter(_q(tag)):
            author = el.get(_q("author"))
            if author:
                removed.add(author)
            el.set(_q("author"), "")
            if _q("date") in el.attrib:
                el.set(_q("date"), "1970-01-01T00:00:00Z")
    return _serialize(root), sorted(removed)


def _strip_settings_xml(xml_bytes: bytes) -> tuple[bytes, Optional[etree._Element]]:
    """Remove <w:attachedTemplate>; return the modified XML and the removed
    element (so its r:id relationship can also be cleaned up)."""
    root = etree.fromstring(xml_bytes)
    el = root.find(_q("attachedTemplate"))
    if el is None:
        return xml_bytes, None
    root.remove(el)
    return _serialize(root), el


def _strip_settings_rels_xml(xml_bytes: bytes, removed_rid: Optional[str]) -> bytes:
    if not removed_rid:
        return xml_bytes
    root = etree.fromstring(xml_bytes)
    for rel in list(root):
        if rel.get("Id") == removed_rid:
            root.remove(rel)
    return _serialize(root)


def _strip_app_xml(xml_bytes: bytes) -> tuple[bytes, Dict[str, Optional[str]]]:
    root = etree.fromstring(xml_bytes)
    removed: Dict[str, Optional[str]] = {key: None for key in APP_XML_FIELDS}
    for key, tag in APP_XML_FIELDS.items():
        el = root.find(f"{{{EXTENDED_PROPS_NS}}}{tag}")
        if el is not None and el.text:
            removed[key] = el.text
            el.text = ""
    return _serialize(root), removed


def _rewrite_zip_with_replacements(
    src_path: str, dst_path: str, replacements: Dict[str, bytes]
) -> None:
    """Copy every entry from src_path's zip to dst_path, substituting the
    byte content of any entry named in `replacements`. All other entries
    (media, styles, fonts, etc.) are copied verbatim and untouched."""
    with zipfile.ZipFile(src_path, "r") as zin:
        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = replacements.get(item.filename, zin.read(item.filename))
                zout.writestr(item, data)


def strip_metadata(filepath: str, output_path: str) -> dict:
    """Write a metadata-scrubbed copy of a .docx file.

    Clears core document properties, comment author identities, tracked
    -change author identities, and any attached-template file path, while
    leaving visible content, formatting, images, and page layout unchanged.

    Args:
        filepath: Path to the source .docx file.
        output_path: Path the cleaned .docx should be written to.

    Returns:
        A dict describing exactly what was removed, in the same shape as
        ``read_metadata()`` (so callers can render a before/after diff).

    Raises:
        DocxMetadataError: if the source file doesn't exist, isn't a valid
            .docx package, or is password-protected/corrupted.
    """
    document = _open_document(filepath)
    removed = _strip_core_properties(document)

    # Save the core-properties-cleared document to a temp file first; this
    # is our base for the raw XML surgery below (python-docx repackages the
    # rest of the archive unmodified).
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(tmp_fd)
    try:
        document.save(tmp_path)

        with _open_zip(tmp_path) as zf:
            names = set(zf.namelist())
            comments_removed: List[str] = []
            tracked_removed: List[str] = []
            template_path: Optional[str] = None
            replacements: Dict[str, bytes] = {}

            if COMMENTS_PART in names:
                new_xml, comments_removed = _strip_comments_xml(zf.read(COMMENTS_PART))
                replacements[COMMENTS_PART] = new_xml

            if DOCUMENT_PART in names:
                new_xml, tracked_removed = _strip_tracked_changes_xml(zf.read(DOCUMENT_PART))
                replacements[DOCUMENT_PART] = new_xml

            removed_rid = None
            if SETTINGS_PART in names:
                template_path = _read_template_path(zf)
                new_settings_xml, removed_el = _strip_settings_xml(zf.read(SETTINGS_PART))
                replacements[SETTINGS_PART] = new_settings_xml
                if removed_el is not None:
                    removed_rid = removed_el.get(f"{{{NS['r']}}}id")

            if removed_rid and SETTINGS_RELS_PART in names:
                replacements[SETTINGS_RELS_PART] = _strip_settings_rels_xml(
                    zf.read(SETTINGS_RELS_PART), removed_rid
                )

            app_xml_removed: Dict[str, Optional[str]] = {key: None for key in APP_XML_FIELDS}
            if APP_PROPS_PART in names:
                new_app_xml, app_xml_removed = _strip_app_xml(zf.read(APP_PROPS_PART))
                replacements[APP_PROPS_PART] = new_app_xml

        _rewrite_zip_with_replacements(tmp_path, output_path, replacements)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    removed["comment_authors"] = comments_removed
    removed["tracked_change_authors"] = tracked_removed
    removed["template_path"] = template_path
    removed.update(app_xml_removed)
    return removed
