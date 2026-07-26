"""
Tests for the main convert function and type mapping.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import convert, SECURE_NOTE_TYPE, LOGIN_TYPE, CARD_TYPE


class TestConvert:
    """Tests for convert function."""

    def test_convert_login(self):
        rows = [
            {
                "Display_Name": "Test Login",
                "Notes": "A login",
                "Login_Username": "user",
                "Login_Password": "pass",
                "Login_URLs": "https://example.com",
                "Favorite": "true",
                "Others": "{}"
            }
        ]
        items, skipped = convert(rows)
        assert len(items) == 1
        assert items[0]["type"] == LOGIN_TYPE
        assert len(skipped) == 0

    def test_convert_card(self):
        rows = [
            {
                "Display_Name": "My Card",
                "Notes": "",
                "Login_Username": "",
                "Login_Password": "",
                "Login_URLs": "",
                "Favorite": "false",
                "Others": '{"Type": "card", "Card_Number": "1234"}'
            }
        ]
        items, _skipped = convert(rows)
        assert len(items) == 1
        assert items[0]["type"] == CARD_TYPE

    def test_convert_secure_note(self):
        rows = [
            {
                "Display_Name": "My Note",
                "Notes": "",
                "Login_Username": "",
                "Login_Password": "",
                "Login_URLs": "",
                "Favorite": "false",
                "Others": '{"Type": "secure", "Secure_Note": "Secret"}'
            }
        ]
        items, _skipped = convert(rows)
        assert len(items) == 1
        assert items[0]["type"] == SECURE_NOTE_TYPE

    def test_convert_new_types(self):
        """Test that ID, Bank, Driver, Router are converted to secure notes."""
        test_cases = [
            ('{"Type": "id", "Secure_Note": "123"}', "ID"),
            ('{"Type": "bank", "Secure_Note": "456"}', "Bank"),
            ('{"Type": "driver", "Secure_Note": "789"}', "Driver"),
            ('{"Type": "router", "Secure_Note": "000"}', "Router"),
        ]

        for others_json, display_name in test_cases:
            rows = [{
                "Display_Name": display_name,
                "Notes": "",
                "Login_Username": "",
                "Login_Password": "",
                "Login_URLs": "",
                "Favorite": "false",
                "Others": others_json
            }]
            items, skipped = convert(rows)
            assert len(items) == 1, f"Failed for {display_name}"
            assert items[0]["type"] == SECURE_NOTE_TYPE, f"Wrong type for {display_name}"
            assert len(skipped) == 0

    def test_convert_unsupported_type(self):
        """Test that unsupported types are skipped."""
        rows = [{
            "Display_Name": "Unknown Type",
            "Notes": "",
            "Login_Username": "",
            "Login_Password": "",
            "Login_URLs": "",
            "Favorite": "false",
            "Others": '{"Type": "unknown_type"}'
        }]
        items, skipped = convert(rows)
        assert len(items) == 0
        assert len(skipped) == 1
        assert "unsupported type" in skipped[0][1]

    def test_convert_no_login_info(self):
        """Test that entries with no login info and no type are skipped."""
        rows = [{
            "Display_Name": "Empty Entry",
            "Notes": "",
            "Login_Username": "",
            "Login_Password": "",
            "Login_URLs": "",
            "Favorite": "false",
            "Others": "{}"
        }]
        items, skipped = convert(rows)
        assert len(items) == 0
        assert len(skipped) == 1

    def test_convert_mixed_types(self):
        """Test conversion with multiple types in one file."""
        rows = [
            {
                "Display_Name": "Login",
                "Login_Username": "user",
                "Login_Password": "pass",
                "Others": "{}"
            },
            {
                "Display_Name": "Card",
                "Others": '{"Type": "card", "Card_Number": "1234"}'
            },
            {
                "Display_Name": "ID",
                "Others": '{"Type": "id", "Secure_Note": "123"}'
            },
        ]
        items, _skipped = convert(rows)
        assert len(items) == 3
        types = {item["type"] for item in items}
        assert LOGIN_TYPE in types
        assert CARD_TYPE in types
        assert SECURE_NOTE_TYPE in types

    def test_convert_preserves_favorite(self):
        """Test that favorite flag is preserved."""
        rows = [{
            "Display_Name": "Favorite",
            "Login_Username": "user",
            "Login_Password": "pass",
            "Favorite": "true",
            "Others": "{}"
        }]
        items, _skipped = convert(rows)
        assert items[0]["favorite"] is True

    def test_convert_handles_malformed_row(self):
        """Test that malformed rows are skipped gracefully."""
        rows = [
            {"Display_Name": "Good", "Login_Username": "user"},
            {"malformed": "data"},  # Missing required fields
        ]
        items, skipped = convert(rows)
        assert len(items) == 1  # Only the good row
        assert len(skipped) == 1  # The malformed one

    def test_convert_empty_rows(self):
        """Test with empty input."""
        items, skipped = convert([])
        assert len(items) == 0
        assert len(skipped) == 0

    def test_convert_login_with_custom_fields(self):
        others = (
            '{"Custom": ['
            '{"Type": "AutofillWeb", "AutofillWeb_Title": "Email", "AutofillWeb_Type": "text",'
            ' "AutofillWeb": "me@example.com", "AutofillWeb_Selector": "#email"},'
            '{"Type": "Password", "Password_Title": "API", "Password": "key123"}'
            ']}'
        )
        rows = [
            {
                "Display_Name": "themoviedb",
                "Login_Username": "user",
                "Login_Password": "pass",
                "Login_URLs": "https://www.themoviedb.org",
                "Others": others,
            }
        ]
        items, skipped = convert(rows)
        assert len(items) == 1
        assert items[0]["type"] == LOGIN_TYPE
        assert [(f["name"], f["value"], f["type"]) for f in items[0]["fields"]] == [
            ("Email", "me@example.com", 0),
            ("API", "key123", 1),
        ]
        assert len(skipped) == 0

    def test_convert_custom_fields_only_still_imported(self):
        """A row with no login info but custom fields should not be skipped."""
        rows = [
            {
                "Display_Name": "Only Custom",
                "Others": '{"Custom": [{"Type": "Password", "Password_Title": "API", "Password": "k"}]}',
            }
        ]
        items, skipped = convert(rows)
        assert len(items) == 1
        assert items[0]["fields"][0]["name"] == "API"
        assert len(skipped) == 0

    def test_convert_card_keeps_custom_fields(self):
        rows = [
            {
                "Display_Name": "My Card",
                "Others": '{"Type": "Card", "Card_Number": "4111111111111111",'
                          ' "Custom": [{"Type": "Text", "Text_Title": "Bank Line", "Text": "info"}]}',
            }
        ]
        items, _skipped = convert(rows)
        assert items[0]["type"] == CARD_TYPE
        assert items[0]["fields"][-1] == {"name": "Bank Line", "value": "info", "type": 0}

    def test_convert_unsupported_type_with_custom_fields_is_still_skipped(self):
        """Custom fields must not turn an unsupported category into a half empty login."""
        rows = [
            {
                "Display_Name": "My Wifi",
                "Others": '{"Type": "Wifi", "Wifi_SSID": "home", "Wifi_Password": "secret",'
                          ' "Custom": [{"Type": "Text", "Text_Title": "Note", "Text": "keep"}]}',
            }
        ]
        items, skipped = convert(rows)
        assert items == []
        assert skipped == [("My Wifi", "unsupported type 'Wifi'")]
