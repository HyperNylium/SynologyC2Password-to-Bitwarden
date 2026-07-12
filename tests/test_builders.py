"""
Tests for Bitwarden item builders.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import (
    build_login, build_card, build_secure_note,
    LOGIN_TYPE, SECURE_NOTE_TYPE, CARD_TYPE,
    TEXT_FIELD, HIDDEN_FIELD
)


class TestBuildLogin:
    """Tests for build_login function."""

    def test_basic_login(self):
        row = {
            "Display_Name": "Test Login",
            "Notes": "My note",
            "Login_Username": "user1",
            "Login_Password": "pass1",
            "Login_URLs": "https://example.com",
            "Favorite": "true"
        }
        item = build_login(row, "Test Login", "My note", True)

        assert item["type"] == LOGIN_TYPE
        assert item["name"] == "Test Login"
        assert item["notes"] == "My note"
        assert item["favorite"] is True
        assert item["login"]["username"] == "user1"
        assert item["login"]["password"] == "pass1"
        assert len(item["login"]["uris"]) == 1
        assert item["login"]["uris"][0]["uri"] == "https://example.com"

    def test_login_no_urls(self):
        row = {
            "Display_Name": "Test",
            "Notes": "",
            "Login_Username": "user",
            "Login_Password": "pass",
            "Login_URLs": "",
            "Favorite": "false"
        }
        item = build_login(row, "Test", "", False)

        assert item["type"] == LOGIN_TYPE
        assert item["login"]["uris"] == []

    def test_login_with_totp(self):
        row = {
            "Display_Name": "Test",
            "Login_Username": "user",
            "Login_Password": "pass",
            "Login_TOTP": "123456",
        }
        item = build_login(row, "Test", "", False)

        assert item["login"]["totp"] == "123456"

    def test_login_no_credentials(self):
        row = {
            "Display_Name": "Test",
            "Notes": "Just notes",
            "Login_Username": "",
            "Login_Password": "",
            "Login_URLs": "",
        }
        item = build_login(row, "Test", "Just notes", False)

        assert item["type"] == LOGIN_TYPE
        assert item["login"]["username"] is None
        assert item["login"]["password"] is None


class TestBuildCard:
    """Tests for build_card function."""

    def test_basic_card(self):
        row = {
            "Display_Name": "My Card",
            "Notes": "Bank card",
        }
        others = {
            "Card_Type": "visa",
            "Card_Number": "1234 5678 9012 3456",
            "Card_Name": "John Doe",
            "Card_Expiry": "12/25",
            "Card_CVV": "123",
            "Card_PIN": "4567",
            "Card_Phone": "+1234567890",
            "Card_URL": "https://bank.com"
        }
        item = build_card(row, others, "My Card", "Bank card", False)

        assert item["type"] == CARD_TYPE
        assert item["name"] == "My Card"
        assert item["card"]["brand"] == "Visa"
        assert item["card"]["number"] == "1234567890123456"  # Spaces removed
        assert item["card"]["expMonth"] == "12"
        assert item["card"]["expYear"] == "2025"
        assert item["card"]["code"] == "123"

        # Check custom fields
        field_names = [f["name"] for f in item["fields"]]
        assert "Card_PIN" in field_names
        assert "Card_Phone" in field_names
        assert "Card_URL" in field_names

    def test_card_unknown_brand(self):
        row = {"Display_Name": "Test"}
        others = {
            "Card_Type": "unknown",
            "Card_Number": "1234",
        }
        item = build_card(row, others, "Test", "", False)
        assert item["card"]["brand"] == "Other"

    def test_card_no_expiry(self):
        row = {"Display_Name": "Test"}
        others = {
            "Card_Type": "visa",
            "Card_Number": "1234",
        }
        item = build_card(row, others, "Test", "", False)
        assert item["card"]["expMonth"] is None
        assert item["card"]["expYear"] is None

    def test_card_bad_expiry_format(self):
        row = {"Display_Name": "Test"}
        others = {
            "Card_Type": "visa",
            "Card_Number": "1234",
            "Card_Expiry": "invalid",
        }
        item = build_card(row, others, "Test", "", False)
        # Bad expiry should be in custom fields
        field_names = [f["name"] for f in item["fields"]]
        assert "Card_Expiry" in field_names

    def test_card_with_two_digit_year(self):
        row = {"Display_Name": "Test"}
        others = {
            "Card_Type": "visa",
            "Card_Number": "1234",
            "Card_Expiry": "05/28",
        }
        item = build_card(row, others, "Test", "", False)
        assert item["card"]["expYear"] == "2028"


class TestBuildSecureNote:
    """Tests for build_secure_note function."""

    def test_secure_note_only(self):
        others = {"Secure_Note": "This is a secret note"}
        item = build_secure_note(others, "My Note", "", False)

        assert item["type"] == SECURE_NOTE_TYPE
        assert item["name"] == "My Note"
        assert item["secureNote"]["type"] == 0
        assert "This is a secret note" in item["notes"]

    def test_secure_note_with_notes(self):
        others = {"Secure_Note": "Secret"}
        item = build_secure_note(others, "My Note", "Additional notes", False)

        assert "Additional notes" in item["notes"]
        assert "Secret" in item["notes"]

    def test_secure_note_no_content(self):
        others = {}
        item = build_secure_note(others, "My Note", "", False)

        assert item["type"] == SECURE_NOTE_TYPE
        assert item["notes"] is None

    def test_secure_note_empty_secure_note(self):
        others = {"Secure_Note": ""}
        item = build_secure_note(others, "My Note", "Existing notes", False)

        assert item["notes"] == "Existing notes"

    def test_secure_note_multiline(self):
        others = {"Secure_Note": "Line 1\nLine 2\nLine 3"}
        item = build_secure_note(others, "My Note", "", False)

        assert "Line 1" in item["notes"]
        assert "Line 2" in item["notes"]
        assert "Line 3" in item["notes"]
