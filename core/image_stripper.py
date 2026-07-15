from __future__ import annotations

import os

from PIL import Image
from PIL.ExifTags import TAGS


class ImageMetadataError(Exception):
    pass


SENSITIVE_TAGS = {
    "GPSInfo", "Make", "Model", "Software", "Artist", "Copyright",
    "XPAuthor", "HostComputer", "GPSLatitude", "GPSLongitude",
}


def _open_image(filepath: str) -> Image.Image:
    if not os.path.isfile(filepath):
        raise ImageMetadataError(f"File not found: {filepath}")
    try:
        return Image.open(filepath)
    except Exception as exc:
        raise ImageMetadataError(
            f"Could not open '{filepath}' as an image. It may be corrupted or not a supported format."
        ) from exc


def read_metadata(filepath: str) -> dict:
    img = _open_image(filepath)
    data = {"format": img.format, "mode": img.mode, "size": f"{img.width}x{img.height}"}
    exif = img._getexif()
    sensitive = {}
    if exif:
        for tag_id, value in exif.items():
            name = TAGS.get(tag_id, str(tag_id))
            if name in SENSITIVE_TAGS:
                sensitive[name] = str(value)
    data["sensitive_exif"] = sensitive
    return data


def strip_metadata(filepath: str, output_path: str) -> dict:
    before = read_metadata(filepath)
    img = _open_image(filepath)
    cleaned = Image.new(img.mode, img.size)
    cleaned.putdata(list(img.getdata()))
    cleaned.save(output_path, format=img.format or "PNG")
    return before
