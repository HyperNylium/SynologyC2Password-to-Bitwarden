"""
Tests for utility functions.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import (
    is_value_present, field, build_uris, custom_field,
    parse_others, parse_expiry, normalize_brand,
    TEXT_FIELD, HIDDEN_FIELD
)


class TestIsValuePresent:
    """Tests for is_value_present function."""

    def test_none(self):
        assert is_value_present(None) is False

    def test_empty_string(self):
        assert is_value_present("") is False

    def test_whitespace(self):
        assert is_value_present("   ") is False

    def test_nan(self):
        assert is_value_present("nan") is False
        assert is_value_present("NaN") is False

    def test_none_string(self):
        assert is_value_present("none") is False
        assert is_value_present("None") is False

    def test_null(self):
        assert is_value_present("null") is False

    def test_valid_string(self):
        assert is_value_present("test") is True
        assert is_value_present("  test  ") is True


class TestField:
    """Tests for field function."""

    def test_none(self):
        assert field(None) == ""

    def test_empty(self):
        assert field("") == ""

    def test_whitespace(self):
        assert field("   ") == ""

    def test_valid(self):
        assert field("test") == "test"


class TestBuildUris:
    """Tests for build_uris function."""

    def test_none(self):
        assert build_uris(None) == []

    def test_empty(self):
        assert build_uris("") == []

    def test_single_url(self):
        result = build_uris("https://example.com")
        assert len(result) == 1
        assert result[0]["uri"] == "https://example.com"

    def test_multiple_urls(self):
        urls = "https://example.com\nhttps://test.com"
        result = build_uris(urls)
        assert len(result) == 2

    def test_urls_with_spaces(self):
        urls = "https://example.com \n https://test.com"
        result = build_uris(urls)
        assert len(result) == 2
        assert result[0]["uri"] == "https://example.com"
        assert result[1]["uri"] == "https://test.com"


class TestCustomField:
    """Tests for custom_field function."""

    def test_text_field(self):
        result = custom_field("test", "value", TEXT_FIELD)
        assert result["name"] == "test"
        assert result["value"] == "value"
        assert result["type"] == TEXT_FIELD

    def test_hidden_field(self):
        result = custom_field("password", "secret", HIDDEN_FIELD)
        assert result["type"] == HIDDEN_FIELD

    def test_empty_value(self):
        result = custom_field("test", "", TEXT_FIELD)
        assert result["value"] == ""


class TestParseOthers:
    """Tests for parse_others function."""

    def test_none(self):
        assert parse_others(None) is None

    def test_empty(self):
        assert parse_others("") is None

    def test_invalid_json(self):
        assert parse_others("{invalid}") is None

    def test_valid_json(self):
        result = parse_others('{"Type": "card", "Card_Number": "1234"}')
        assert result is not None
        assert result["Type"] == "card"
        assert result["Card_Number"] == "1234"

    def test_non_dict_json(self):
        assert parse_others('["array"]') is None


class TestParseExpiry:
    """Tests for parse_expiry function."""

    def test_none(self):
        assert parse_expiry(None) == ("", "", "")

    def test_empty(self):
        assert parse_expiry("") == ("", "", "")

    def test_mm_yy(self):
        month, year, raw = parse_expiry("01/25")
        assert month == "1"
        assert year == "2025"
        assert raw == ""

    def test_mm_yyyy(self):
        month, year, raw = parse_expiry("12/2025")
        assert month == "12"
        assert year == "2025"

    def test_invalid(self):
        month, year, raw = parse_expiry("invalid")
        assert month == ""
        assert year == ""
        assert raw == "invalid"

    def test_mm_only(self):
        month, year, raw = parse_expiry("13/25")  # Invalid month
        assert month == ""
        assert year == ""

    def test_yy_mm_format(self):
        # Should not work (wrong format)
        month, year, raw = parse_expiry("25/01")
        assert month == ""
        assert year == ""

    def test_with_spaces(self):
        month, year, raw = parse_expiry(" 01 / 25 ")
        assert month == "1"
        assert year == "2025"


class TestNormalizeBrand:
    """Tests for normalize_brand function."""

    def test_visa(self):
        assert normalize_brand("visa") == "Visa"
        assert normalize_brand("VISA") == "Visa"

    def test_mastercard(self):
        assert normalize_brand("mastercard") == "Mastercard"
        assert normalize_brand("MasterCard") == "Mastercard"

    def test_amex(self):
        assert normalize_brand("amex") == "Amex"
        assert normalize_brand("american express") == "Amex"

    def test_unknown(self):
        assert normalize_brand("unknown") == "Other"
        assert normalize_brand("") == ""

    def test_diners_club(self):
        assert normalize_brand("diners club") == "Diners Club"

    def test_jcb(self):
        assert normalize_brand("jcb") == "JCB"
