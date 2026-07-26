"""
Tests for utility functions.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import (
    is_value_present, field, build_uris, custom_field, build_custom_fields,
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
        month, year, _raw = parse_expiry("12/2025")
        assert month == "12"
        assert year == "2025"

    def test_invalid(self):
        month, year, raw = parse_expiry("invalid")
        assert month == ""
        assert year == ""
        assert raw == "invalid"

    def test_mm_only(self):
        month, year, _raw = parse_expiry("13/25")  # Invalid month
        assert month == ""
        assert year == ""

    def test_yy_mm_format(self):
        # Should not work (wrong format)
        month, year, _raw = parse_expiry("25/01")
        assert month == ""
        assert year == ""

    def test_with_spaces(self):
        month, year, _raw = parse_expiry(" 01 / 25 ")
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


class TestCustomFields:
    """Tests for build_custom_fields function."""

    def test_none_and_missing(self):
        assert build_custom_fields(None) == []
        assert build_custom_fields({}) == []
        assert build_custom_fields({"Custom": "not a list"}) == []

    def test_autofill_web_text_and_password(self):
        others = {
            "Custom": [
                {
                    "Type": "AutofillWeb",
                    "AutofillWeb_Title": "Email",
                    "AutofillWeb_Type": "text",
                    "AutofillWeb": "me@example.com",
                    "AutofillWeb_Selector": "#email",
                },
                {
                    "Type": "AutofillWeb",
                    "AutofillWeb_Title": "Password Confirm",
                    "AutofillWeb_Type": "password",
                    "AutofillWeb": "secret",
                    "AutofillWeb_Selector": "#password_confirm",
                },
            ]
        }
        fields = build_custom_fields(others)
        assert fields == [
            {"name": "Email", "value": "me@example.com", "type": TEXT_FIELD},
            {"name": "Password Confirm", "value": "secret", "type": HIDDEN_FIELD},
        ]

    def test_password_entry_is_hidden(self):
        others = {"Custom": [{"Type": "Password", "Password_Title": "API", "Password": "key123"}]}
        fields = build_custom_fields(others)
        assert fields == [{"name": "API", "value": "key123", "type": HIDDEN_FIELD}]

    def test_missing_title_falls_back_to_type(self):
        others = {"Custom": [{"Type": "Text", "Text": "hello"}]}
        assert build_custom_fields(others)[0]["name"] == "Text"

    def test_unknown_type_uses_first_value_key(self):
        others = {"Custom": [{"Type": "Mystery", "Mystery_Title": "Thing", "Value": "42"}]}
        assert build_custom_fields(others) == [{"name": "Thing", "value": "42", "type": TEXT_FIELD}]

    def test_skips_blank_and_non_dict_entries(self):
        others = {
            "Custom": [
                "junk",
                {"Type": "Password", "Password_Title": "Empty", "Password": ""},
                {"Type": "Password", "Password_Title": "Kept", "Password": "v"},
            ]
        }
        assert [f["name"] for f in build_custom_fields(others)] == ["Kept"]

    def test_blank_typed_value_keeps_searching(self):
        """A blank value under the type key should not stop the fallback search."""

        others = {
            "Custom": [
                {"Type": "Password", "Password_Title": "API", "Password": None, "Note": "real"}
            ]
        }
        assert build_custom_fields(others) == [
            {"name": "API", "value": "real", "type": HIDDEN_FIELD}
        ]

    def test_nested_value_is_kept_as_json(self):
        """Bitwarden fields are text, so a nested object must not become a python repr."""

        others = {
            "Custom": [
                {"Type": "Address", "Address_Title": "Home", "Address": {"City": "X", "Zip": "1"}}
            ]
        }
        assert build_custom_fields(others) == [
            {"name": "Home", "value": '{"City": "X", "Zip": "1"}', "type": TEXT_FIELD}
        ]

    def test_skips_empty_nested_values(self):
        others = {"Custom": [{"Type": "Address", "Address_Title": "Home", "Address": {}}]}
        assert build_custom_fields(others) == []

    def test_unnamed_entry_falls_back_to_position(self):
        others = {"Custom": [{"Value": "orphan"}]}
        assert build_custom_fields(others) == [
            {"name": "Custom_1", "value": "orphan", "type": TEXT_FIELD}
        ]
