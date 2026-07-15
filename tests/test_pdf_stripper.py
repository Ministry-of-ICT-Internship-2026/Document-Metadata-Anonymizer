import os
import sys

import pytest
from PyPDF2 import PdfReader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.pdf_stripper import PdfMetadataError, read_metadata, strip_metadata

SAMPLES = os.path.join(os.path.dirname(__file__), "sample_files")


def _s(name):
    p = os.path.join(SAMPLES, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not found")
    return p


def test_read_metadata():
    m = read_metadata(_s("plain_metadata.pdf"))
    assert m["Author"] == "John Doe"
    assert m["Creator"] == "Microsoft Word"


def test_strip_clears_all(tmp_path):
    src = _s("plain_metadata.pdf")
    out = str(tmp_path / "stripped.pdf")
    before = strip_metadata(src, out)
    assert before["Author"] == "John Doe"
    after = read_metadata(out)
    for k in ("Author", "Title", "Subject", "Keywords"):
        assert after[k] is None or after[k] == ""


def test_content_preserved(tmp_path):
    src = _s("plain_metadata.pdf")
    out = str(tmp_path / "stripped.pdf")
    r1 = PdfReader(src)
    t1 = " ".join(p.extract_text() or "" for p in r1.pages)
    strip_metadata(src, out)
    r2 = PdfReader(out)
    t2 = " ".join(p.extract_text() or "" for p in r2.pages)
    assert t1 == t2


def test_no_metadata(tmp_path):
    m = read_metadata(_s("no_metadata.pdf"))
    assert m["Author"] is None
    r = strip_metadata(_s("no_metadata.pdf"), str(tmp_path / "out.pdf"))
    assert os.path.exists(str(tmp_path / "out.pdf"))


def test_missing_file_raises():
    with pytest.raises(PdfMetadataError):
        read_metadata("/tmp/nonexistent.pdf")


def test_bad_file_raises(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(PdfMetadataError):
        read_metadata(str(p))
