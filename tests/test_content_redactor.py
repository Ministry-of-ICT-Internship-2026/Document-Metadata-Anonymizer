import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.content_redactor import (
    REDACTED_LABEL,
    _find_matches,
    _merge_counts,
    luhn_check,
    redact_content,
    redact_text,
    shannon_entropy,
)

SAMPLES = os.path.join(os.path.dirname(__file__), "sample_files")


def _s(name):
    p = os.path.join(SAMPLES, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not found")
    return p


class TestShannonEntropy:
    def test_empty(self):
        assert shannon_entropy("") == 0.0
        assert shannon_entropy("   ") == 0.0

    def test_low_entropy(self):
        assert shannon_entropy("aaaaa") < 1.0

    def test_high_entropy(self):
        e = shannon_entropy("aB3$xK9#mP2!qR7")
        assert e > 3.0


class TestLuhnCheck:
    def test_valid_visa(self):
        assert luhn_check("4111111111111111") is True

    def test_valid_mastercard(self):
        assert luhn_check("5555555555554444") is True

    def test_invalid(self):
        assert luhn_check("1234567890123456") is False

    def test_too_short(self):
        assert luhn_check("1234") is False

    def test_too_long(self):
        assert luhn_check("1" * 20) is False


class TestRedactText:
    def test_email(self):
        result, counts = redact_text(
            "Contact john.doe@example.com for info",
            {"email"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("email") == 1

    def test_phone(self):
        result, counts = redact_text(
            "Call +256-712-345-678 today",
            {"phone"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("phone") == 1

    def test_nin(self):
        result, counts = redact_text(
            "NIN: 12-345678-901234-56",
            {"nin"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("nin") == 1

    def test_credit_card_valid(self):
        result, counts = redact_text(
            "Card: 4111 1111 1111 1111 expires soon",
            {"credit_card"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("credit_card") == 1

    def test_credit_card_invalid(self):
        result, counts = redact_text(
            "Number 1234 5678 9012 3456 is not real",
            {"credit_card"},
        )
        assert counts.get("credit_card", 0) == 0

    def test_ipv4(self):
        result, counts = redact_text(
            "Server at 192.168.1.1 is down",
            {"ip"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("ip") == 1

    def test_multiple_patterns(self):
        result, counts = redact_text(
            "Email: a@b.com, Phone: +1-555-123-4567",
            {"email", "phone"},
        )
        assert counts.get("email") == 1
        assert counts.get("phone") == 1
        assert result.count(REDACTED_LABEL) == 2

    def test_no_match(self):
        result, counts = redact_text("Just plain text here", {"email"})
        assert result == "Just plain text here"
        assert counts == {}

    def test_confidential_keyword(self):
        result, counts = redact_text(
            "This is a confidential document about our strategy.",
            {"confidential"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("confidential") == 1

    def test_custom_keywords(self):
        result, counts = redact_text(
            "The project-x budget is secret.",
            {"confidential"},
            custom_keywords=["project-x", "budget"],
        )
        assert REDACTED_LABEL in result
        assert counts.get("confidential") == 1

    def test_jwt(self):
        result, counts = redact_text(
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dkWmelU7fQwGqRJ_iLc8zQ",
            {"jwt"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("jwt") == 1

    def test_api_key(self):
        result, counts = redact_text(
            "OpenAI key: sk-abc123def456ghi789jkl",
            {"api_key"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("api_key") == 1

    def test_high_entropy(self):
        result, counts = redact_text(
            "Token: aB3x$K9mP2!qR7xYzLmNpQsR",
            {"high_entropy"},
        )
        assert REDACTED_LABEL in result
        assert counts.get("high_entropy") == 1

    def test_empty_text(self):
        result, counts = redact_text("", {"email"})
        assert result == ""
        assert counts == {}

    def test_no_rules(self):
        result, counts = redact_text("a@b.com", set())
        assert result == "a@b.com"
        assert counts == {}


class TestMergeCounts:
    def test_merge_empty(self):
        assert _merge_counts({}, {"a": 1}) == {"a": 1}

    def test_merge_additive(self):
        assert _merge_counts({"a": 2}, {"a": 3, "b": 1}) == {"a": 5, "b": 1}


class TestRedactContent:
    def test_docx_with_content(self, tmp_path):
        src = _s("plain_metadata.docx")
        out = str(tmp_path / "cleaned.docx")
        filters = {"redact_email": True, "redact_phone": True, "redact_ip": True}
        result = redact_content(src, out, filters=filters)
        assert result is not None
        assert result.get("total", 0) >= 0
        assert os.path.exists(out)

    def test_xlsx_with_content(self, tmp_path):
        src = _s("plain_metadata.xlsx")
        out = str(tmp_path / "cleaned.xlsx")
        filters = {"redact_email": True, "redact_phone": True}
        result = redact_content(src, out, filters=filters)
        assert result is not None
        assert result.get("total", 0) >= 0
        assert os.path.exists(out)

    def test_pdf_with_content(self, tmp_path):
        src = _s("plain_metadata.pdf")
        out = str(tmp_path / "cleaned.pdf")
        filters = {"redact_email": True, "redact_phone": True}
        result = redact_content(src, out, filters=filters)
        assert result is not None
        assert result.get("total", 0) >= 0
        assert os.path.exists(out)

    def test_no_rules_returns_none(self, tmp_path):
        src = _s("plain_metadata.docx")
        out = str(tmp_path / "cleaned.docx")
        result = redact_content(src, out, filters={})
        assert result is None

    def test_filters_none_returns_none(self, tmp_path):
        src = _s("plain_metadata.docx")
        out = str(tmp_path / "cleaned.docx")
        result = redact_content(src, out, filters=None)
        assert result is None

    def test_image_returns_none(self, tmp_path):
        src = _s("plain_metadata.pdf")
        os.rename(src, src)
        png_path = str(tmp_path / "test.png")
        with open(png_path, "wb") as f:
            f.write(b"not a real png")
        result = redact_content(png_path, str(tmp_path / "out.png"), filters={"redact_email": True})
        assert result is None
