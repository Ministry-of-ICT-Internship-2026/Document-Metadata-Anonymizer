from __future__ import annotations

import os
import zipfile

from core.docx_stripper import (
    DocxMetadataError,
    read_metadata as read_docx_metadata,
    strip_metadata as strip_docx_metadata,
)
from core.pdf_stripper import (
    PdfMetadataError,
    read_metadata as read_pdf_metadata,
    strip_metadata as strip_pdf_metadata,
)
from core.xlsx_stripper import (
    XlsxMetadataError,
    read_metadata as read_xlsx_metadata,
    strip_metadata as strip_xlsx_metadata,
)
from core.image_stripper import (
    ImageMetadataError,
    read_metadata as read_image_metadata,
    strip_metadata as strip_image_metadata,
)


SUPPORTED = {
    ".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx",
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".tiff": "image", ".tif": "image", ".bmp": "image",
}


def detect_type(filepath: str) -> str | None:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in SUPPORTED:
        return SUPPORTED[ext]
    try:
        with open(filepath, "rb") as f:
            h = f.read(4)
    except OSError:
        return None
    if h.startswith(b"%PDF"):
        return "pdf"
    if h.startswith(b"PK\x03\x04"):
        return {"docx": "docx", "xlsx": "xlsx"}.get(ext, "docx")
    return None


def read_metadata(filepath: str) -> dict:
    t = detect_type(filepath)
    if t is None:
        raise ValueError(f"Unsupported file: {filepath}")
    return {
        "pdf": read_pdf_metadata,
        "docx": read_docx_metadata,
        "xlsx": read_xlsx_metadata,
        "image": read_image_metadata,
    }[t](filepath)


def strip_metadata(filepath: str, output_path: str) -> dict:
    t = detect_type(filepath)
    if t is None:
        raise ValueError(f"Unsupported file: {filepath}")
    return {
        "pdf": strip_pdf_metadata,
        "docx": strip_docx_metadata,
        "xlsx": strip_xlsx_metadata,
        "image": strip_image_metadata,
    }[t](filepath, output_path)


def process_single(filepath: str, output_dir: str) -> dict:
    name, ext = os.path.splitext(os.path.basename(filepath))
    out = os.path.join(output_dir, f"{name}_cleaned{ext}")
    try:
        before = read_metadata(filepath)
        removed = strip_metadata(filepath, out)
        after = read_metadata(out)
        return {"file": os.path.basename(filepath), "success": True, "output_path": out, "before": before, "removed": removed, "after": after}
    except (DocxMetadataError, PdfMetadataError, XlsxMetadataError, ImageMetadataError, ValueError) as e:
        return {"file": os.path.basename(filepath), "success": False, "error": str(e)}


def process_batch(filepaths: list[str], output_dir: str) -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)
    return [process_single(fp, output_dir) for fp in filepaths]


def create_batch_zip(output_dir: str, zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(output_dir):
            if "_cleaned." in fname:
                zf.write(os.path.join(output_dir, fname), arcname=fname)
    return zip_path
