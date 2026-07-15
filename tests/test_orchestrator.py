import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.orchestrator import detect_type, process_single, process_batch

SAMPLES = os.path.join(os.path.dirname(__file__), "sample_files")


def _s(name):
    p = os.path.join(SAMPLES, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not found")
    return p


def test_detect_type():
    assert detect_type("f.pdf") == "pdf"
    assert detect_type("f.docx") == "docx"
    assert detect_type("f.xlsx") == "xlsx"
    assert detect_type("f.jpg") == "image"
    assert detect_type("f.unknown") is None


def test_process_pdf(tmp_path):
    r = process_single(_s("plain_metadata.pdf"), str(tmp_path))
    assert r["success"]
    assert os.path.exists(r["output_path"])


def test_process_missing(tmp_path):
    r = process_single("/tmp/nonexistent.pdf", str(tmp_path))
    assert not r["success"]


def test_batch_mixed(tmp_path):
    results = process_batch([_s("plain_metadata.pdf"), _s("plain_metadata.xlsx")], str(tmp_path / "batch"))
    assert len(results) == 2
    assert all(r["success"] for r in results)


def test_batch_error_isolation(tmp_path):
    results = process_batch([_s("plain_metadata.pdf"), "/tmp/nonexistent.xyz"], str(tmp_path / "batch"))
    successes = [r for r in results if r["success"]]
    assert len(successes) >= 1
