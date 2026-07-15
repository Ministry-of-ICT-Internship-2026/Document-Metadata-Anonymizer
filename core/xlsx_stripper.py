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
EXTENDED_PROPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
CONNECTIONS_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
EXTERNAL_LINK_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
THREADED_COMMENT_NS = "http://schemas.microsoft.com/office/2019/10/wordprocessingml"
PEOPLE_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CUSTOM_XML_PREFIX = "customXML/"

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
            f"Could not open '{filepath}' as an .xlsx file. It may be "
            "corrupted, password-protected, or not a valid Excel file."
        ) from exc


def _load_xml_part(zf: zipfile.ZipFile, name: str):
    if name not in zf.namelist():
        return None
    return etree.fromstring(zf.read(name))


def _serialize(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _get_text(el: etree._Element | None, default: str = "") -> str:
    if el is not None and el.text:
        return el.text
    return default


# --------------------------------------------------------------------------
# Readers
# --------------------------------------------------------------------------

def _read_threaded_comments(zf: zipfile.ZipFile) -> dict:
    result: dict = {"threaded_comment_authors": []}
    names = zf.namelist()
    threaded_parts = [n for n in names if n.startswith("xl/threadedComments/") and n.endswith(".xml")]
    for tp in threaded_parts:
        root = _load_xml_part(zf, tp)
        if root is None:
            continue
        for tc in root:
            author = tc.get(f"{{{MAIN_NS}}}author", "")
            if author:
                result["threaded_comment_authors"].append(author)
    result["threaded_comment_authors"] = sorted(set(result["threaded_comment_authors"]))
    return result


def _read_external_links(zf: zipfile.ZipFile) -> dict:
    result: dict = {"external_link_paths": []}
    names = zf.namelist()
    ext_parts = [n for n in names if n.startswith("xl/externalLinks/") and n.endswith(".xml")]
    for ep in ext_parts:
        root = _load_xml_part(zf, ep)
        if root is None:
            continue
        for ext in root.findall(f"{{{EXTERNAL_LINK_NS}}}externalBook"):
            for sheet_ds in ext.iter():
                if sheet_ds.tag == f"{{{EXTERNAL_LINK_NS}}}sheetDataSet":
                    continue
            for rel_file in ext.findall(f"file"):
                pass
        # external links store paths in r:id relationships
        rels_path = f"xl/externalLinks/_rels/{os.path.basename(ep)}.rels"
        rels_root = _load_xml_part(zf, rels_path)
        if rels_root is not None:
            for rel in rels_root:
                target = rel.get("Target", "")
                if target:
                    result["external_link_paths"].append(target)
    return result


def _read_connections(zf: zipfile.ZipFile) -> dict:
    result: dict = {"connections": []}
    root = _load_xml_part(zf, "xl/connections.xml")
    if root is None:
        return result
    for conn in root.findall(f"{{{CONNECTIONS_NS}}}connection"):
        name = conn.get("name", "")
        desc = conn.get("description", "")
        conn_str = ""
        db_pr = conn.find(f"{{{CONNECTIONS_NS}}}dbPr")
        if db_pr is not None:
            conn_str = db_pr.get("connection", "")
        info = {}
        if name:
            info["name"] = name
        if desc:
            info["description"] = desc
        if conn_str:
            info["connection"] = conn_str
        if info:
            result["connections"].append(info)
    return result


def _read_defined_names(zf: zipfile.ZipFile) -> list:
    result: list = []
    root = _load_xml_part(zf, "xl/workbook.xml")
    if root is None:
        return result
    for dn in root.iter(f"{{{MAIN_NS}}}definedName"):
        name = dn.get("name", "")
        text = dn.text or ""
        if name:
            result.append({"name": name, "value": text.strip()})
    return result


def _read_pivot_tables(zf: zipfile.ZipFile) -> dict:
    result: dict = {"pivot_source_names": [], "pivot_cache_definition_sources": []}
    names = zf.namelist()
    cache_defs = [n for n in names if n.startswith("xl/pivotCache/") and n.endswith(".xml")]
    for cd in cache_defs:
        root = _load_xml_part(zf, cd)
        if root is None:
            continue
        cache_source = root.find(f"{{{MAIN_NS}}}cacheSource")
        if cache_source is not None:
            ws_source = cache_source.find(f"{{{MAIN_NS}}}worksheetSource")
            if ws_source is not None:
                ref = ws_source.get("ref", "")
                sheet = ws_source.get("sheet", "")
                name = ws_source.get("name", "")
                src = f"{sheet}!{ref}" if sheet and ref else (f"{sheet}!{name}" if sheet and name else "")
                if src:
                    result["pivot_cache_definition_sources"].append(src)
    return result


def _read_people_part(zf: zipfile.ZipFile) -> dict:
    result: dict = {"person_names": []}
    root = _load_xml_part(zf, "xl/people.xml")
    if root is None:
        return result
    for person in root:
        name = person.get(f"{{{MAIN_NS}}}name", "")
        if name:
            result["person_names"].append(name)
    return result


def _read_custom_xml_parts(zf: zipfile.ZipFile) -> list:
    return sorted(n for n in zf.namelist() if n.startswith(CUSTOM_XML_PREFIX))


def read_metadata(filepath: str) -> dict:
    wb = _open_workbook(filepath)
    props = wb.properties
    data: dict = {}
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

    with zipfile.ZipFile(filepath, "r") as zf:
        data.update(_read_threaded_comments(zf))
        data.update(_read_external_links(zf))
        data.update(_read_connections(zf))
        data["defined_names"] = _read_defined_names(zf)
        data.update(_read_pivot_tables(zf))
        data.update(_read_people_part(zf))
        data["custom_xml_parts"] = _read_custom_xml_parts(zf)

    return data


# --------------------------------------------------------------------------
# Strippers
# --------------------------------------------------------------------------

def _strip_core_properties(wb: openpyxl.Workbook) -> dict:
    props = wb.properties
    before: dict = {}
    for field in STRING_CORE_FIELDS:
        before[field] = str(getattr(props, field, None) or "")
        setattr(props, field, "")
    for field in INT_CORE_FIELDS:
        before[field] = getattr(props, field, None)
        setattr(props, field, 1)
    for field in DATE_CORE_FIELDS:
        val = getattr(props, field, None)
        before[field] = val.isoformat() if hasattr(val, "isoformat") else str(val) if val else None
    before["custom_properties"] = {p.name: str(p.value) for p in wb.custom_doc_props}
    for p in list(wb.custom_doc_props):
        try:
            del wb.custom_doc_props[p.name]
        except Exception:
            pass
    before["hidden_sheets"] = [ws.title for ws in wb.worksheets if ws.sheet_state != "visible"]
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            ws.sheet_state = "visible"
    return before


def _strip_date_xml(core_xml_bytes: bytes) -> bytes:
    root = etree.fromstring(core_xml_bytes)
    for tag in DATE_TAGS.values():
        for el in root.findall(tag):
            parent = el.getparent() if hasattr(el, 'getparent') else None
            if parent is not None:
                parent.remove(el)
            else:
                try:
                    root.remove(el)
                except ValueError:
                    pass
    for el in root.findall(f"{{{CORE_XML_NS}}}revision"):
        el.text = "1"
    return _serialize(root)


def _strip_threaded_comments_xml(xml_bytes: bytes, part_name: str) -> bytes:
    root = etree.fromstring(xml_bytes)
    for tc in root:
        tc.set(f"{{{MAIN_NS}}}author", "")
        if "provisionId" in tc.attrib:
            tc.attrib.pop("provisionId", None)
    return _serialize(root)


def _strip_connections_xml(xml_bytes: bytes) -> bytes:
    root = etree.fromstring(xml_bytes)
    for conn in root.findall(f"{{{CONNECTIONS_NS}}}connection"):
        if "name" in conn.attrib:
            conn.attrib.pop("name")
        if "description" in conn.attrib:
            conn.attrib.pop("description")
        db_pr = conn.find(f"{{{CONNECTIONS_NS}}}dbPr")
        if db_pr is not None:
            if "connection" in db_pr.attrib:
                db_pr.attrib.pop("connection")
    return _serialize(root)


def _strip_external_links_rels(zf: zipfile.ZipFile, names: set) -> dict:
    replacements: dict = {}
    ext_parts = [n for n in names if n.startswith("xl/externalLinks/") and n.endswith(".xml")]
    for ep in ext_parts:
        rels_path = f"xl/externalLinks/_rels/{os.path.basename(ep)}.rels"
        if rels_path not in names:
            continue
        rels_root = etree.fromstring(zf.read(rels_path))
        for rel in rels_root:
            if "Target" in rel.attrib:
                rel.attrib.pop("Target")
        replacements[rels_path] = _serialize(rels_root)
    return replacements


def _strip_defined_names(xml_bytes: bytes) -> bytes:
    root = etree.fromstring(xml_bytes)
    for dn in root.iter(f"{{{MAIN_NS}}}definedName"):
        parent = dn.getparent()
        if parent is not None:
            parent.remove(dn)
    return _serialize(root)


def _strip_workbook_xml(zf: zipfile.ZipFile) -> bytes:
    xml_bytes = zf.read("xl/workbook.xml")
    return _strip_defined_names(xml_bytes)


def _strip_people_xml(xml_bytes: bytes) -> bytes:
    root = etree.fromstring(xml_bytes)
    for person in root:
        person.set(f"{{{MAIN_NS}}}name", "")
        person.set(f"{{{PEOPLE_NS}}}id", "")
        person.text = ""
    return _serialize(root)


def _strip_custom_xml_parts(zf: zipfile.ZipFile) -> dict:
    replacements: dict = {}
    for name in zf.namelist():
        if name.startswith(CUSTOM_XML_PREFIX) and name.endswith(".xml"):
            root = etree.fromstring(zf.read(name))
            for child in list(root):
                root.remove(child)
            replacements[name] = _serialize(root)
    return replacements


def strip_metadata(filepath: str, output_path: str, filters: dict | None = None) -> dict:
    if filters is None:
        filters = {"author": True, "dates": True, "geo": True, "software": True}
    before = read_metadata(filepath)
    wb = _open_workbook(filepath)
    core_before = _strip_core_properties(wb) if (filters.get("author") or filters.get("dates") or filters.get("software")) else {"custom_properties": {}, "hidden_sheets": []}

    tmp = tempfile.mktemp(suffix=".xlsx")
    try:
        wb.save(tmp)
        wb.close()

        with zipfile.ZipFile(tmp, "r") as zin, \
                zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            names = set(zin.namelist())

            for item in zin.infolist():
                fname = item.filename
                data = zin.read(fname)

                if fname == "docProps/core.xml" and (filters.get("dates") or filters.get("software")):
                    data = _strip_date_xml(data)

                elif fname == "xl/connections.xml" and filters.get("software"):
                    data = _strip_connections_xml(data)

                elif fname == "xl/workbook.xml" and filters.get("software"):
                    data = _strip_defined_names(data)

                elif fname.startswith("xl/threadedComments/") and fname.endswith(".xml") and filters.get("author"):
                    data = _strip_threaded_comments_xml(data, fname)

                elif fname == "xl/people.xml" and filters.get("author"):
                    data = _strip_people_xml(data)

                elif fname.startswith(CUSTOM_XML_PREFIX) and fname.endswith(".xml") and filters.get("author"):
                    root = etree.fromstring(data)
                    for child in list(root):
                        root.remove(child)
                    data = _serialize(root)

                elif fname.startswith("xl/externalLinks/"):
                    if fname.endswith(".xml.rels") and filters.get("software"):
                        rels_root = etree.fromstring(data)
                        for rel in rels_root:
                            if "Target" in rel.attrib:
                                rel.attrib.pop("Target")
                        data = _serialize(rels_root)

                zout.writestr(item, data)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    result = dict(before)
    result["custom_properties_cleared"] = list(core_before.get("custom_properties", {}).keys())
    return result
