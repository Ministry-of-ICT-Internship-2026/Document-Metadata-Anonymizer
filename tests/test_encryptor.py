import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.document_encryptor import (
    ENC_PREFIX,
    _get_fernet,
    decrypt_document,
    decrypt_text,
    encrypt_document,
    encrypt_text,
    is_encrypted,
)

SAMPLES = os.path.join(os.path.dirname(__file__), "sample_files")

PASSWORD = "test-password-123!"


def _s(name):
    p = os.path.join(SAMPLES, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not found")
    return p


class TestEncryptDecryptText:
    def test_roundtrip(self):
        f = _get_fernet(PASSWORD)
        original = "Hello, this is sensitive data!"
        ct = encrypt_text(original, f)
        assert ct != original
        assert ct.startswith(ENC_PREFIX)
        pt = decrypt_text(ct, f)
        assert pt == original

    def test_empty_text(self):
        f = _get_fernet(PASSWORD)
        assert encrypt_text("", f) == ""
        assert decrypt_text("", f) == ""

    def test_whitespace_only(self):
        f = _get_fernet(PASSWORD)
        assert encrypt_text("   ", f) == "   "

    def test_already_encrypted(self):
        f = _get_fernet(PASSWORD)
        ct = encrypt_text("data", f)
        ct2 = encrypt_text(ct, f)
        assert ct2 == ct

    def test_wrong_password(self):
        good_f = _get_fernet(PASSWORD)
        bad_f = _get_fernet("wrong-password")
        original = "sensitive"
        ct = encrypt_text(original, good_f)
        pt = decrypt_text(ct, bad_f)
        assert pt != original

    def test_not_encrypted(self):
        f = _get_fernet(PASSWORD)
        assert decrypt_text("plain text", f) == "plain text"


class TestEncryptDecryptDocx:
    def test_roundtrip(self, tmp_path):
        src = _s("plain_metadata.docx")
        enc = str(tmp_path / "encrypted.docx")
        dec = str(tmp_path / "decrypted.docx")

        encrypt_document(src, enc, PASSWORD)
        assert os.path.exists(enc)
        assert is_encrypted(enc)

        decrypt_document(enc, dec, PASSWORD)
        assert os.path.exists(dec)
        assert not is_encrypted(dec)

    def test_encrypted_content_differs(self, tmp_path):
        src = _s("plain_metadata.docx")
        enc = str(tmp_path / "encrypted.docx")

        encrypt_document(src, enc, PASSWORD)

        import zipfile
        with zipfile.ZipFile(src, "r") as z:
            src_text = z.read("word/document.xml").decode("utf-8", errors="replace")
        with zipfile.ZipFile(enc, "r") as z:
            enc_text = z.read("word/document.xml").decode("utf-8", errors="replace")

        assert ENC_PREFIX in enc_text

    def test_wrong_password_leaves_encrypted(self, tmp_path):
        src = _s("plain_metadata.docx")
        enc = str(tmp_path / "encrypted.docx")
        dec = str(tmp_path / "dec.docx")

        encrypt_document(src, enc, PASSWORD)
        decrypt_document(enc, dec, "wrong-password")
        import zipfile
        with zipfile.ZipFile(dec, "r") as z:
            text = z.read("word/document.xml").decode("utf-8", errors="replace")
        assert ENC_PREFIX in text  # still encrypted

    def test_not_encrypted_raises(self, tmp_path):
        src = _s("plain_metadata.docx")
        out = str(tmp_path / "out.docx")
        assert not is_encrypted(src)
        with pytest.raises(ValueError, match="Not an encrypted document"):
            decrypt_document(src, out, PASSWORD)


class TestEncryptDecryptXlsx:
    def test_roundtrip(self, tmp_path):
        src = _s("plain_metadata.xlsx")
        enc = str(tmp_path / "encrypted.xlsx")
        dec = str(tmp_path / "decrypted.xlsx")

        encrypt_document(src, enc, PASSWORD)
        assert os.path.exists(enc)
        assert is_encrypted(enc)

        decrypt_document(enc, dec, PASSWORD)
        assert os.path.exists(dec)
        assert not is_encrypted(dec)


class TestIsEncrypted:
    def test_normal_file(self):
        assert not is_encrypted(_s("plain_metadata.docx"))

    def test_encrypted_file(self, tmp_path):
        src = _s("plain_metadata.docx")
        enc = str(tmp_path / "enc.docx")
        encrypt_document(src, enc, PASSWORD)
        assert is_encrypted(enc)

    def test_missing_file(self):
        assert not is_encrypted("/tmp/nonexistent.docx")

    def test_pdf_returns_false(self):
        assert not is_encrypted(_s("plain_metadata.pdf"))
