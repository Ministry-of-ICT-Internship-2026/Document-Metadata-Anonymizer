from __future__ import annotations

import os
from typing import Any

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.constants import PageAttributes as PA
from PyPDF2.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NullObject,
    TextStringObject,
    create_string_object,
)


class PdfMetadataError(Exception):
    pass


INFO_FIELDS = [
    "/Author", "/Title", "/Subject", "/Creator", "/Producer", "/Keywords",
]
DATE_FIELDS = ["/CreationDate", "/ModDate"]

EMPTY_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'
    "</x:xmpmeta>"
    '<?xpacket end="w"?>'
)


def _stringify(value: Any) -> Any:
    if value is None:
        return None
    return str(value)


def _open_pdf(filepath: str) -> PdfReader:
    if not os.path.isfile(filepath):
        raise PdfMetadataError(f"File not found: {filepath}")
    try:
        return PdfReader(filepath)
    except Exception as exc:
        raise PdfMetadataError(
            f"Could not open '{filepath}' as a PDF. It may be corrupted, "
            "password-protected, or not a valid PDF."
        ) from exc


def _resolve(obj: Any) -> Any:
    if isinstance(obj, IndirectObject):
        return obj.get_object()
    return obj


def _get_obj(dictionary: Any, key: str, default: Any = None) -> Any:
    d = _resolve(dictionary)
    if d is None:
        return default
    if isinstance(d, dict):
        return d.get(key, default)
    try:
        return d.get(key, default)
    except Exception:
        return default


# --------------------------------------------------------------------------
# Metadata readers
# --------------------------------------------------------------------------

def read_metadata(filepath: str) -> dict:
    reader = _open_pdf(filepath)
    info = reader.metadata
    data: dict = {}
    for field in INFO_FIELDS + DATE_FIELDS:
        val = _stringify(_get_obj(info, field)) if info else None
        data[field.lstrip("/")] = val

    root = _resolve(_get_obj(reader.trailer, "/Root"))
    data["has_xmp"] = "/Metadata" in root if isinstance(root, dict) else False

    annot_authors: list[str] = []
    for page in reader.pages:
        annots = _get_obj(page, PA.ANNOTS)
        if annots is None:
            continue
        for a in annots:
            ao = _resolve(a)
            if isinstance(ao, dict) and "/T" in ao:
                annot_authors.append(str(ao["/T"]))

    data["annotation_authors"] = sorted(set(annot_authors))
    data["acroform"] = "/AcroForm" in root if isinstance(root, dict) else False

    names_dict = _get_obj(root, "/Names")
    ef = _get_obj(_get_obj(names_dict, "/EmbeddedFiles"), "/Names") if isinstance(names_dict, dict) else None
    data["has_embedded_files"] = ef is not None

    return data


# --------------------------------------------------------------------------
# Stripping helpers
# --------------------------------------------------------------------------

def _strip_catalog_xmp(catalog: DictionaryObject) -> bool:
    removed = "/Metadata" in catalog
    if removed:
        catalog[NameObject("/Metadata")] = NullObject()
    return removed


def _strip_annotations(writer: PdfWriter) -> dict:
    removed: dict[str, list[str]] = {"annotation_authors": []}
    for page in writer.pages:
        annots_arr = _get_obj(page, PA.ANNOTS)
        if annots_arr is None:
            continue
        if not isinstance(annots_arr, ArrayObject):
            continue
        for annot_ref in annots_arr:
            annot = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
            if not isinstance(annot, DictionaryObject):
                continue
            if "/T" in annot:
                removed["annotation_authors"].append(str(annot["/T"]))
                annot[NameObject("/T")] = TextStringObject("")
            if "/Subj" in annot:
                annot[NameObject("/Subj")] = TextStringObject("")
            if "/CA" in annot:
                annot[NameObject("/CA")] = TextStringObject("")
            if "/RC" in annot:
                annot[NameObject("/RC")] = TextStringObject("")
    return removed


def _strip_acroform_metadata(catalog: DictionaryObject) -> dict:
    removed: dict[str, bool] = {"acroform_needs": False}
    acro = _get_obj(catalog, "/AcroForm")
    if acro is None:
        return removed
    removed["acroform_needs"] = True
    if "/NeedAppearances" in acro:
        del acro["/NeedAppearances"]
    fields = _get_obj(acro, "/Fields")
    if fields and isinstance(fields, ArrayObject):
        for f_ref in fields:
            field = f_ref.get_object() if hasattr(f_ref, "get_object") else f_ref
            if not isinstance(field, DictionaryObject):
                continue
            if "/TU" in field:
                field[NameObject("/TU")] = TextStringObject("")
            if "/TM" in field:
                field[NameObject("/TM")] = TextStringObject("")
    return removed


def _strip_embedded_files(catalog: DictionaryObject) -> dict:
    removed: dict[str, list[str]] = {"embedded_file_descriptions": []}
    names = _get_obj(catalog, "/Names")
    if names is None:
        return removed
    ef = _get_obj(names, "/EmbeddedFiles")
    if ef is None:
        return removed
    ef_tree = _get_obj(ef, "/Names")
    if ef_tree is None or not isinstance(ef_tree, ArrayObject):
        return removed
    for i in range(1, len(ef_tree), 2):
        fs = ef_tree[i]
        fs_obj = fs.get_object() if hasattr(fs, "get_object") else fs
        if not isinstance(fs_obj, DictionaryObject):
            continue
        ef_params = _get_obj(fs_obj, "/Params")
        if ef_params and isinstance(ef_params, DictionaryObject):
            if "/ModDate" in ef_params:
                ef_params[NameObject("/ModDate")] = TextStringObject("")
            if "/CreationDate" in ef_params:
                ef_params[NameObject("/CreationDate")] = TextStringObject("")
    desc = _get_obj(ef, "/Descriptions")
    if desc and isinstance(desc, dict):
        for k in desc:
            desc_entry = desc[k]
            if isinstance(desc_entry, dict) and "/Description" in desc_entry:
                removed["embedded_file_descriptions"].append(str(desc_entry["/Description"]))
                desc_entry["/Description"] = TextStringObject("")
    return removed


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def strip_metadata(filepath: str, output_path: str, filters: dict | None = None) -> dict:
    if filters is None:
        filters = {"author": True, "dates": True, "geo": True, "software": True}
    before = read_metadata(filepath)
    reader = _open_pdf(filepath)

    catalog = _resolve(_get_obj(reader.trailer, "/Root"))
    if not isinstance(catalog, DictionaryObject):
        catalog = DictionaryObject()

    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    info_clear = {}
    if filters.get("author"):
        info_clear["/Author"] = ""
    if filters.get("dates"):
        for f in DATE_FIELDS:
            info_clear[f] = ""
    if filters.get("software"):
        for f in ["/Title", "/Subject", "/Creator", "/Producer", "/Keywords"]:
            info_clear[f] = ""
    if info_clear:
        writer.add_metadata(info_clear)

    removed_xmp = False
    if filters.get("software"):
        removed_xmp = _strip_catalog_xmp(catalog)

    removed_annots: dict = {"annotation_authors": []}
    if filters.get("author"):
        removed_annots = _strip_annotations(writer)

    removed_acro: dict = {"acroform_needs": False}
    if filters.get("author") or filters.get("software"):
        removed_acro = _strip_acroform_metadata(catalog)

    removed_ef: dict = {"embedded_file_descriptions": []}
    if filters.get("dates"):
        removed_ef = _strip_embedded_files(catalog)

    writer._root_object = catalog

    with open(output_path, "wb") as f:
        writer.write(f)

    result = dict(before)
    result["xmp_stripped"] = removed_xmp
    result["annotation_authors"] = removed_annots.get("annotation_authors", [])
    result["acroform_stripped"] = removed_acro.get("acroform_needs", False)
    result["embedded_file_descriptions"] = removed_ef.get("embedded_file_descriptions", [])
    return result
