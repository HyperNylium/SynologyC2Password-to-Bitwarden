"""
Tests for CSV parsing functions.
"""
import os
import pytest
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import read_csv, validate_input_file, clean_path


class TestCleanPath:
    """Tests for clean_path function."""

    def test_none_input(self):
        assert clean_path(None) is None

    def test_empty_string(self):
        assert clean_path("") is None

    def test_strip_quotes(self):
        assert clean_path('"/path/to/file"') == "/path/to/file"
        assert clean_path("'/path/to/file'") == "/path/to/file"

    def test_replace_separators(self):
        assert clean_path("C:\\Users\\test") == "C:/Users/test"
        assert clean_path("C:/Users/test") == "C:/Users/test"


class TestValidateInputFile:
    """Tests for validate_input_file function."""

    def test_nonexistent_file(self, tmp_path):
        assert validate_input_file(str(tmp_path / "nonexistent.csv")) is False

    def test_directory_not_file(self, tmp_path):
        assert validate_input_file(str(tmp_path)) is False

    def test_valid_file(self, tmp_path):
        test_file = tmp_path / "test.csv"
        test_file.write_text("test")
        assert validate_input_file(str(test_file)) is True


class TestReadCSV:
    """Tests for read_csv function."""

    def test_read_valid_csv(self):
        rows, columns = read_csv("tests/fixtures/login.csv")
        assert len(rows) == 3
        assert "Display_Name" in columns
        assert "Login_Username" in columns

    def test_read_card_csv(self):
        rows, columns = read_csv("tests/fixtures/card.csv")
        assert len(rows) == 2
        assert rows[0]["Display_Name"] == "My Card"

    def test_read_secure_note_csv(self):
        rows, columns = read_csv("tests/fixtures/secure_note.csv")
        assert len(rows) == 2

    def test_read_new_types_csv(self):
        rows, columns = read_csv("tests/fixtures/new_types.csv")
        assert len(rows) == 5
        assert all("Display_Name" in row for row in rows)

    def test_encoding_detection(self, tmp_path):
        # Create UTF-16 file
        utf16_file = tmp_path / "utf16.csv"
        utf16_file.write_bytes("Display_Name\nTest\n".encode("utf-16"))
        rows, columns = read_csv(str(utf16_file))
        assert len(rows) == 1

    def test_empty_csv(self, tmp_path):
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")
        with pytest.raises(ValueError, match="empty"):
            read_csv(str(empty_file))
