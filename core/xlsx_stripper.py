from __future__ import annotations

import os
import tempfile
import zipfile

import openpyxl
from lxml import etree


class XlsxMetadataError(Exception):
    pass


STRING_CORE_FIELDS = [
    "creator", "lastModifiedBy", "category", "contentStatus",
    "description", "identifier", "keywords", "language",
    "subject", "title", "version",
]
INT_CORE_FIELDS = ["revision"]
DATE_CORE_FIELDS = ["created", "modified", "lastPrinted"]

CORE_XML_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DCTERMS_NS = "http://purl.org/dc/terms/"

DATE_TAGS = {
    "created": f"{{{DCTERMS_NS}}}created",
    "modified": f"{{{DCTERMS_NS}}}modified",
    "lastPrinted": f"{{{CORE_XML_NS}}}lastPrinted",
}


def _open_workbook(filepath: str) -> openpyxl.Workbook:
    if not os.path.isfile(filepath):
        raise XlsxMetadataError(f"File not found: {filepath}")
    try:
        return openpyxl.load_workbook(filepath)
    except Exception as exc:
        raise XlsxMetadataError(
            f"Could not open '{filepath}' as an .xlsx file. It may be corrupted, password-protected, or not a valid Excel file."
        ) from exc


def read_metadata(filepath: str) -> dict:
    wb = _open_workbook(filepath)
    props = wb.properties
    data = {}
    for field in STRING_CORE_FIELDS:
        data[field] = str(getattr(props, field, None) or "")
    for field in INT_CORE_FIELDS:
        data[field] = getattr(props, field, None)
    for field in DATE_CORE_FIELDS:
        val = getattr(props, field, None)
        data[field] = val.isoformat() if hasattr(val, "isoformat") else str(val) if val else None
    data["custom_properties"] = {p.name: str(p.value) for p in wb.custom_doc_props}
    data["hidden_sheets"] = [ws.title for ws in wb.worksheets if ws.sheet_state != "visible"]
    wb.close()
    return data


def strip_metadata(filepath: str, output_path: str) -> dict:
    before = read_metadata(filepath)
    wb = _open_workbook(filepath)
    props = wb.properties
    for field in STRING_CORE_FIELDS:
        setattr(props, field, "")
    for field in INT_CORE_FIELDS:
        setattr(props, field, 1)
    for p in list(wb.custom_doc_props):
        try:
            del wb.custom_doc_props[p.name]
        except Exception:
            pass
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            ws.sheet_state = "visible"
    tmp = tempfile.mktemp(suffix=".xlsx")
    try:
        wb.save(tmp)
        wb.close()
        with zipfile.ZipFile(tmp, "r") as zin, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "docProps/core.xml":
                    root = etree.fromstring(data)
                    for tag in DATE_TAGS.values():
                        for el in root.findall(tag):
                            (el.getparent() or root).remove(el)
                    for el in root.findall(f"{{{CORE_XML_NS}}}revision"):
                        el.text = "1"
                    data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                zout.writestr(item, data)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return before
