"""
Tests for the CLI main module.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chatgpt_extractor.__main__ import main, run_failure_analysis
from tests.test_helpers import capture_logs, assert_in_logs


class TestCLI:
    """Test suite for CLI functionality."""
    
    def test_version_argument(self, capsys):
        """Test --version argument."""
        with patch('sys.argv', ['chatgpt_extractor', '--version']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        
        captured = capsys.readouterr()
        assert 'v2.0' in captured.out
    
    def test_help_argument(self, capsys):
        """Test --help argument."""
        with patch('sys.argv', ['chatgpt_extractor', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        
        captured = capsys.readouterr()
        assert 'Extract ChatGPT conversations' in captured.out
    
    def test_missing_input_file(self, capsys):
        """Test behavior with missing input file."""
        with patch('sys.argv', ['chatgpt_extractor', 'nonexistent.json']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert 'not found' in captured.out
    
    @patch('chatgpt_extractor.__main__.ConversationExtractorV2')
    def test_successful_extraction(self, mock_extractor):
        """Test successful extraction flow."""
        # Create mock input file
        mock_extractor_instance = MagicMock()
        mock_extractor.return_value = mock_extractor_instance
        
        with patch('sys.argv', ['chatgpt_extractor', 'tests/fixtures/sample_conversation.json']):
            with patch('pathlib.Path.exists', return_value=True):
                main()
        
        # Verify extractor was called
        mock_extractor.assert_called_once()
        mock_extractor_instance.extract_all.assert_called_once()
    
    def test_run_failure_analysis_no_log(self, capsys):
        """Test failure analysis when no log exists."""
        with capture_logs('chatgpt_extractor.chatgpt_extractor.__main__') as log_capture:
            run_failure_analysis('input.json', 'output_dir')
            assert_in_logs(log_capture, 'No failures to analyze')
    
    def test_run_failure_analysis_no_failures(self, tmp_path, capsys):
        """Test failure analysis when log shows no failures."""
        log_file = tmp_path / 'conversion_log.log'
        log_file.write_text('Processing complete.\nFailed conversations: 0')
        
        with capture_logs('chatgpt_extractor.chatgpt_extractor.__main__') as log_capture:
            run_failure_analysis('input.json', str(tmp_path))
            assert_in_logs(log_capture, 'No failures to analyze')