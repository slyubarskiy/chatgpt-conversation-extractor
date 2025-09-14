"""
Test suite for CLI argument validation.
Focuses on the new validation logic for JSON output options.
"""

import json
import sys
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor.__main__ import validate_cli_arguments, main


class TestCLIValidation:
    """Test CLI argument validation logic."""

    def test_valid_markdown_only(self):
        """Test valid markdown-only configuration."""
        args = argparse.Namespace(
            output_format="markdown",
            json_format="multiple",  # Default value
            json_dir=None,
            json_file=None,
        )

        # Should not raise any exception
        with patch("chatgpt_extractor.__main__.get_logger"):
            validate_cli_arguments(args)

    def test_valid_json_dir(self):
        """Test valid JSON directory output configuration."""
        args = argparse.Namespace(
            output_format="json",
            json_format="multiple",
            json_dir="custom/json",
            json_file=None,
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            validate_cli_arguments(args)

    def test_valid_json_file(self):
        """Test valid single JSON file configuration."""
        args = argparse.Namespace(
            output_format="json",
            json_format="single",
            json_dir=None,
            json_file="output.json",
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            validate_cli_arguments(args)

    def test_invalid_both_json_options(self):
        """Test error when both json-dir and json-file are specified."""
        args = argparse.Namespace(
            output_format="json",
            json_format="multiple",
            json_dir="json_dir",
            json_file="output.json",
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            with pytest.raises(SystemExit) as exc_info:
                validate_cli_arguments(args)
            assert exc_info.value.code == 1

    def test_invalid_json_options_with_markdown_only(self):
        """Test error when JSON options used with markdown-only output."""
        args = argparse.Namespace(
            output_format="markdown",
            json_format="single",
            json_dir="json_output",
            json_file=None,
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            with pytest.raises(SystemExit) as exc_info:
                validate_cli_arguments(args)
            assert exc_info.value.code == 1

    def test_invalid_json_file_with_multiple_format(self):
        """Test error when json-file used with multiple format."""
        args = argparse.Namespace(
            output_format="json",
            json_format="multiple",  # Should be 'single' for json_file
            json_dir=None,
            json_file="output.json",
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            with pytest.raises(SystemExit) as exc_info:
                validate_cli_arguments(args)
            assert exc_info.value.code == 1

    def test_invalid_json_dir_with_single_format(self):
        """Test error when json-dir used with single format."""
        args = argparse.Namespace(
            output_format="json",
            json_format="single",  # Should be 'multiple' for json_dir
            json_dir="json_output",
            json_file=None,
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            with pytest.raises(SystemExit) as exc_info:
                validate_cli_arguments(args)
            assert exc_info.value.code == 1

    def test_both_format_with_json_options(self):
        """Test 'both' format accepts JSON options."""
        args = argparse.Namespace(
            output_format="both",
            json_format="multiple",
            json_dir="custom_json",
            json_file=None,
        )

        with patch("chatgpt_extractor.__main__.get_logger"):
            validate_cli_arguments(args)  # Should not raise


class TestCLIIntegration:
    """Test full CLI integration with new options."""

    def test_help_shows_json_options(self, capsys):
        """Test that help text includes new JSON options."""
        with patch("sys.argv", ["chatgpt_extractor", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "--output-format" in captured.out
        assert "--json-format" in captured.out
        assert "--json-dir" in captured.out
        assert "--json-file" in captured.out
        assert "--preserve-timestamps" in captured.out

    def test_json_extraction_via_cli(self, tmp_path):
        """Test JSON extraction through CLI interface."""
        conversations = [
            {
                "id": "cli-test",
                "title": "CLI Test",
                "mapping": {
                    "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                    "n2": {
                        "id": "n2",
                        "parent": "n1",
                        "children": [],
                        "message": {
                            "author": {"role": "user"},
                            "content": {"content_type": "text", "parts": ["Test"]},
                        },
                    },
                },
                "current_node": "n2",
            }
        ]

        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"

        test_args = [
            "chatgpt_extractor",
            str(input_file),
            str(output_dir),
            "--output-format",
            "json",
            "--json-format",
            "multiple",
        ]

        with patch("sys.argv", test_args):
            # Mock the exit to prevent test termination
            with patch("sys.exit"):
                main()

        # Verify JSON output was created
        json_file = output_dir / "json" / "CLI Test.json"
        assert json_file.exists()

    def test_both_format_via_cli(self, tmp_path):
        """Test both markdown and JSON output via CLI."""
        conversations = [
            {
                "id": "both-cli",
                "title": "Both CLI",
                "mapping": {
                    "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                    "n2": {
                        "id": "n2",
                        "parent": "n1",
                        "children": [],
                        "message": {
                            "author": {"role": "user"},
                            "content": {"content_type": "text", "parts": ["Test"]},
                        },
                    },
                },
                "current_node": "n2",
            }
        ]

        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"

        test_args = [
            "chatgpt_extractor",
            str(input_file),
            str(output_dir),
            "--output-format",
            "both",
        ]

        with patch("sys.argv", test_args):
            with patch("sys.exit"):
                main()

        # Verify both outputs created
        assert (output_dir / "md" / "Both CLI.md").exists()
        assert (output_dir / "json" / "Both CLI.json").exists()
