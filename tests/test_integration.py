"""
Integration tests for the full conversion pipeline.
"""
import json
import os
import sys
import tempfile
import contextlib
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syno2bw import main, convert, save


class TestIntegration:
    """End-to-end tests for the conversion process."""

    def test_full_conversion_login(self, capsys):
        """Test full conversion of a login CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input CSV
            input_csv = os.path.join(tmpdir, "C2Password_Export_test.csv")
            with open(input_csv, "w") as f:
                f.write("Display_Name,Notes,Login_Username,Login_Password,Login_URLs,Login_TOTP,Favorite,Others\n")
                f.write('"Test Login","My note","user","pass","https://example.com",,"true",{}\n')

            # Change to tmpdir and run main
            original_dir = os.getcwd()
            original_argv = sys.argv
            sys.argv = ["syno2bw.py", input_csv]
            os.chdir(tmpdir)

            try:
                with contextlib.redirect_stdout(io.StringIO()) as cap_out:
                    try:
                        main()
                    except SystemExit:
                        pass

                # Check output file exists
                output_file = os.path.join(tmpdir, "bitwarden_file.json")
                assert os.path.exists(output_file), "Output file not created"

                # Verify content
                with open(output_file, "r") as f:
                    data = json.load(f)
                    assert "items" in data
                    assert len(data["items"]) == 1
                    assert data["items"][0]["type"] == 1  # LOGIN_TYPE
                    assert data["items"][0]["login"]["username"] == "user"
                    assert data["items"][0]["login"]["password"] == "pass"
            finally:
                sys.argv = original_argv
                os.chdir(original_dir)

    def test_full_conversion_all_types(self, capsys):
        """Test full conversion with all supported types."""
        import csv as csv_module
        with tempfile.TemporaryDirectory() as tmpdir:
            input_csv = os.path.join(tmpdir, "C2Password_Export_all.csv")
            with open(input_csv, "w", newline="") as f:
                writer = csv_module.writer(f)
                writer.writerow(["Display_Name", "Notes", "Login_Username", "Login_Password", "Login_URLs", "Login_TOTP", "Favorite", "Others"])
                writer.writerow(["Login", "", "user", "pass", "https://example.com", "", "false", "{}"])
                writer.writerow(["Card", "", "", "", "", "{}", "false", json.dumps({"Type": "card", "Card_Number": "1234"})])
                writer.writerow(["Secure", "", "", "", "", "{}", "false", json.dumps({"Type": "secure", "Secure_Note": "note"})])
                writer.writerow(["ID", "", "", "", "", "{}", "false", json.dumps({"Type": "id", "Secure_Note": "123"})])
                writer.writerow(["Bank", "", "", "", "", "{}", "false", json.dumps({"Type": "bank", "Secure_Note": "456"})])
            original_dir = os.getcwd()
            original_argv = sys.argv
            sys.argv = ["syno2bw.py", input_csv]
            os.chdir(tmpdir)

            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        main()
                    except SystemExit:
                        pass

                output_file = os.path.join(tmpdir, "bitwarden_file.json")
                with open(output_file, "r") as f:
                    data = json.load(f)
                    assert len(data["items"]) == 5
                    types = {item["type"] for item in data["items"]}
                    assert 1 in types  # Login
                    assert 3 in types  # Card
                    assert 2 in types  # Secure Note (for secure, id, bank)
            finally:
                sys.argv = original_argv
                os.chdir(original_dir)

    def test_full_conversion_preserves_structure(self, capsys):
        """Test that the Bitwarden JSON structure is correct."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_csv = os.path.join(tmpdir, "C2Password_Export.csv")
            with open(input_csv, "w") as f:
                f.write("Display_Name,Notes,Login_Username,Login_Password,Login_URLs,Login_TOTP,Favorite,Others\n")
                f.write('"Test","Note","user","pass","https://test.com",,"true",{}\n')

            original_dir = os.getcwd()
            original_argv = sys.argv
            sys.argv = ["syno2bw.py", input_csv]
            os.chdir(tmpdir)

            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        main()
                    except SystemExit:
                        pass

                output_file = os.path.join(tmpdir, "bitwarden_file.json")
                with open(output_file, "r") as f:
                    data = json.load(f)

                    # Check top-level structure
                    assert "folders" in data
                    assert "items" in data
                    assert data["folders"] == []

                    # Check item structure
                    item = data["items"][0]
                    assert "id" in item
                    assert "type" in item
                    assert "name" in item
                    assert "notes" in item
                    assert "favorite" in item
                    assert "reprompt" in item
            finally:
                sys.argv = original_argv
                os.chdir(original_dir)

    def test_convert_and_save_manually(self):
        """Test the convert + save pipeline without main()."""
        rows = [
            {
                "Display_Name": "Test Item",
                "Notes": "A test",
                "Login_Username": "user",
                "Login_Password": "pass",
                "Login_URLs": "https://example.com",
                "Favorite": "true",
                "Others": "{}"
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            items, skipped = convert(rows)
            assert len(items) == 1
            assert len(skipped) == 0

            output_path = os.path.join(tmpdir, "test_output.json")
            saved_path = save(items, output_path)

            assert os.path.exists(saved_path)
            with open(saved_path, "r") as f:
                data = json.load(f)
                assert "items" in data
                assert len(data["items"]) == 1

    def test_new_types_conversion(self):
        """Test that new types (ID, Bank, Driver, Router) are converted to secure notes."""
        test_cases = [
            ("id", "My ID", "National ID: 123"),
            ("bank", "My Bank", "IBAN: FR76..."),
            ("driver", "My Driver", "License: ABC123"),
            ("router", "My Router", "IP: 192.168.1.1"),
        ]

        for type_name, name, secure_note in test_cases:
            rows = [{
                "Display_Name": name,
                "Notes": "",
                "Login_Username": "",
                "Login_Password": "",
                "Login_URLs": "",
                "Favorite": "false",
                "Others": json.dumps({"Type": type_name, "Secure_Note": secure_note})
            }]

            items, skipped = convert(rows)
            assert len(items) == 1
            assert items[0]["type"] == 2  # SECURE_NOTE_TYPE
            assert items[0]["name"] == name
            assert secure_note in items[0]["notes"]
            assert "secureNote" in items[0]
