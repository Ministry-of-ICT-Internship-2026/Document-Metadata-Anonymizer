from __future__ import annotations

import os
from typing import Any

from PyPDF2 import PdfReader, PdfWriter


class PdfMetadataError(Exception):
    pass


PDF_FIELDS = [
    "/Author", "/Title", "/Subject", "/Creator", "/Producer", "/Keywords",
]
DATE_FIELDS = ["/CreationDate", "/ModDate"]


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
            f"Could not open '{filepath}' as a PDF. It may be corrupted, password-protected, or not a valid PDF."
        ) from exc


def read_metadata(filepath: str) -> dict:
    reader = _open_pdf(filepath)
    info = reader.metadata
    if info is None:
        return {field.lstrip("/"): None for field in PDF_FIELDS + DATE_FIELDS}
    data = {}
    for field in PDF_FIELDS + DATE_FIELDS:
        data[field.lstrip("/")] = _stringify(info.get(field, None))
    return data


def strip_metadata(filepath: str, output_path: str) -> dict:
    before = read_metadata(filepath)
    reader = _open_pdf(filepath)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({k: "" for k in PDF_FIELDS + DATE_FIELDS})
    with open(output_path, "wb") as f:
        writer.write(f)
    return before
