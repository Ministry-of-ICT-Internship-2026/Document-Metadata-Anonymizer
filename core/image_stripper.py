from __future__ import annotations

import os

from PIL import Image
from PIL.ExifTags import TAGS as EXIF_TAGS
from PIL.PngImagePlugin import PngInfo

PNG_TEXT_KEYS = {
    "Title", "Author", "Description", "Copyright", "Creation Time",
    "Software", "Disclaimer", "Warning", "Source", "Comment",
}

IPTC_HEADER_NAMES = {
    "2#025": "Model", "2#080": "Byline", "2#110": "Credit",
    "2#116": "Copyright", "2#120": "Caption", "2#122": "CaptionWriter",
}

JPEG_COM_PREFIX = "jc.Comment"
ICC_PROFILE_KEY = "icc_profile"

SENSITIVE_EXIF_TAGS = {
    "GPSInfo", "Make", "Model", "Software", "Artist", "Copyright",
    "XPAuthor", "HostComputer", "GPSLatitude", "GPSLongitude",
}

ANIMATED_FORMATS = ("GIF",)


class ImageMetadataError(Exception):
    pass


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _open_image(filepath: str) -> Image.Image:
    if not os.path.isfile(filepath):
        raise ImageMetadataError(f"File not found: {filepath}")
    try:
        return Image.open(filepath)
    except Exception as exc:
        raise ImageMetadataError(
            f"Could not open '{filepath}' as an image. It may be "
            "corrupted or not a supported format."
        ) from exc


def _stringify(value) -> str:
    if value is None:
        return ""
    return str(value)


# --------------------------------------------------------------------------
# Reader
# --------------------------------------------------------------------------

def read_metadata(filepath: str) -> dict:
    img = _open_image(filepath)
    data: dict = {
        "format": img.format,
        "mode": img.mode,
        "size": f"{img.width}x{img.height}",
    }

    # EXIF
    sensitive: dict = {}
    exif = img._getexif()
    if exif:
        for tag_id, value in exif.items():
            name = EXIF_TAGS.get(tag_id, str(tag_id))
            if name in SENSITIVE_EXIF_TAGS:
                sensitive[name] = str(value)
    data["sensitive_exif"] = sensitive

    # PNG text chunks (tEXt/zTXt/iTXt)
    png_text: dict = {}
    for key, val in img.info.items():
        if key in PNG_TEXT_KEYS:
            png_text[key] = str(val)
    data["png_text_chunks"] = png_text

    # ICC profile
    icc = img.info.get(ICC_PROFILE_KEY)
    if icc is not None:
        data["icc_profile"] = f"present ({len(icc)} bytes)"
    else:
        data["icc_profile"] = None

    # IPTC data
    iptc_data = img.info.get("iptc")
    iptc_found: dict = {}
    if iptc_data is not None:
        if hasattr(iptc_data, "items"):
            for key, val in iptc_data.items():
                label = IPTC_HEADER_NAMES.get(str(key), str(key))
                iptc_found[label] = _stringify(val)
    data["iptc"] = iptc_found if iptc_found else None

    # JPEG comments
    jfif_comment = img.info.get("comment")
    if jfif_comment is not None:
        data["jpeg_comment"] = str(jfif_comment)
    else:
        data["jpeg_comment"] = None

    # Animation
    frames = 0
    if img.format in ANIMATED_FORMATS:
        try:
            while True:
                frames += 1
                img.seek(img.tell() + 1)
        except EOFError:
            img.seek(0)
    data["frames"] = frames if frames > 1 else 1

    return data


# --------------------------------------------------------------------------
# Stripper
# --------------------------------------------------------------------------

def strip_metadata(filepath: str, output_path: str, filters: dict | None = None) -> dict:
    if filters is None:
        filters = {"author": True, "dates": True, "geo": True, "software": True}
    before = read_metadata(filepath)
    img = _open_image(filepath)
    fmt = img.format
    is_animated = before.get("frames", 1) > 1

    should_strip = any(filters.get(k) for k in ("author", "dates", "geo", "software"))

    if not should_strip:
        img.save(output_path, format=fmt or "PNG")
        return before

    if fmt == "GIF" and is_animated:
        _strip_gif_animated(img, output_path)
    elif fmt in ("JPEG", "MPO"):
        img.save(output_path, format="JPEG", exif=b"", quality="keep")
    elif fmt == "PNG":
        png_info = PngInfo()
        img.save(output_path, format="PNG", pnginfo=png_info)
    elif fmt == "TIFF" or fmt == "TIF":
        cleaned = Image.new(img.mode, img.size)
        cleaned.putdata(list(img.getdata()))
        cleaned.save(output_path, format="TIFF")
    else:
        cleaned = Image.new(img.mode, img.size)
        if img.mode == "P":
            palette = img.getpalette()
            if palette:
                cleaned.putpalette(palette)
        cleaned.putdata(list(img.getdata()))
        cleaned.save(output_path, format=fmt or "PNG")

    return before


def _strip_gif_animated(img: Image.Image, output_path: str) -> None:
    frames_durations: list = []
    frames_disposal: list = []
    frames: list[Image.Image] = []

    try:
        while True:
            duration = img.info.get("duration", 100)
            disposal = img.info.get("disposal", 2)
            frame = img.copy()
            if frame.mode != "P":
                frame = frame.convert("P")
            frames.append(frame)
            frames_durations.append(duration)
            frames_disposal.append(disposal)
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    if not frames:
        img.seek(0)
        img.save(output_path, format="GIF")
        return

    first_palette = frames[0].getpalette()
    cleaned_frames: list[Image.Image] = []
    for frame in frames:
        c = Image.new("P", frame.size)
        if first_palette:
            c.putpalette(first_palette)
        c.putdata(list(frame.getdata()))
        cleaned_frames.append(c)

    duration = frames_durations[0] if len(set(frames_durations)) == 1 else frames_durations
    disposal = frames_disposal[0] if len(set(frames_disposal)) == 1 else frames_disposal

    cleaned_frames[0].save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=cleaned_frames[1:],
        duration=duration,
        disposal=disposal,
        loop=0,
    )
