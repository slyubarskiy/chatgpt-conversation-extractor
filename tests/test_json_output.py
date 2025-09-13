"""
Test suite for JSON output functionality.
Focuses on high-value coverage for the new JSON features.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chatgpt_extractor.extractor import ConversationExtractorV2


class TestJSONOutput:
    """Test JSON output functionality - critical new feature."""
    
    def test_json_dir_output(self, tmp_path):
        """Test individual JSON file generation."""
        conversations = [{
            "id": "test-json-1",
            "title": "JSON Test",
            "create_time": 1234567890,
            "update_time": 1234567900,
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Test message"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        # Test JSON directory output
        extractor = ConversationExtractorV2(
            str(input_file), 
            str(tmp_path),
            output_format='json',
            json_format='multiple'
        )
        extractor.extract_all()
        
        # Check JSON file was created
        json_file = tmp_path / "json" / "JSON Test.json"
        assert json_file.exists()
        
        # Verify JSON structure
        with open(json_file) as f:
            data = json.load(f)
        
        assert data['id'] == 'test-json-1'
        assert data['title'] == 'JSON Test'
        assert len(data['messages']) == 1
        assert data['messages'][0]['role'] == 'user'
        assert data['messages'][0]['content'] == 'Test message'
    
    def test_json_single_file_output(self, tmp_path):
        """Test consolidated JSON file generation."""
        conversations = [
            {
                "id": f"conv-{i}",
                "title": f"Conversation {i}",
                "mapping": {
                    "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                    "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": [f"Message {i}"]}
                    }}
                },
                "current_node": "n2"
            }
            for i in range(3)
        ]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        # Test single JSON file output
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            output_format='json',
            json_format='single'
        )
        extractor.extract_all()
        
        # Find the consolidated JSON file
        json_files = list(tmp_path.glob("conversations_export_*.json"))
        assert len(json_files) == 1
        
        # Verify structure
        with open(json_files[0]) as f:
            data = json.load(f)
        
        assert 'export_metadata' in data
        assert data['export_metadata']['total_conversations'] == 3
        assert len(data['conversations']) == 3
        
    def test_both_formats_output(self, tmp_path):
        """Test generating both markdown and JSON."""
        conversations = [{
            "id": "both-test",
            "title": "Both Formats",
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Test"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            output_format='both',
            json_format='multiple'
        )
        extractor.extract_all()
        
        # Check both files exist
        assert (tmp_path / "md" / "Both Formats.md").exists()
        assert (tmp_path / "json" / "Both Formats.json").exists()
    
    def test_json_with_project_structure(self, tmp_path):
        """Test JSON output preserves project folder structure."""
        conversations = [{
            "id": "proj-json",
            "title": "Project JSON",
            "conversation_template_id": "g-p-myproject",
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Project test"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            output_format='json',
            json_format='multiple'
        )
        extractor.extract_all()
        
        # Check project structure in JSON output
        json_file = tmp_path / "json" / "g-p-myproject" / "Project JSON.json"
        assert json_file.exists()
        
        with open(json_file) as f:
            data = json.load(f)
        assert data['project_id'] == 'g-p-myproject'
    
    def test_json_metadata_completeness(self, tmp_path):
        """Test all metadata fields are included in JSON."""
        conversations = [{
            "id": "metadata-test",
            "title": "Metadata Test",
            "create_time": 1234567890,
            "update_time": 1234567900,
            "default_model_slug": "gpt-4",
            "is_starred": True,
            "is_archived": False,
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2", "n3"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "system"},
                    "content": {"content_type": "user_editable_context"},
                    "metadata": {
                        "is_user_system_message": True,
                        "user_context_message_data": {
                            "about_user_message": "User is a developer",
                            "about_model_message": "Be helpful and concise"
                        }
                    }
                }},
                "n3": {"id": "n3", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Test message"]}
                }}
            },
            "current_node": "n3"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            output_format='json',
            json_format='multiple'
        )
        extractor.extract_all()
        
        json_file = tmp_path / "json" / "Metadata Test.json"
        with open(json_file) as f:
            data = json.load(f)
        
        # Verify all metadata fields
        assert data['starred'] == True
        assert data['archived'] == False
        assert data['model'] == 'gpt-4'
        # Custom instructions should be extracted from user_context_message_data
        assert 'custom_instructions' in data
        assert data['custom_instructions']['about_user_message'] == "User is a developer"
        assert data['custom_instructions']['about_model_message'] == "Be helpful and concise"


class TestDirectoryStructure:
    """Test directory creation logic for new structure."""
    
    def test_default_directory_structure(self, tmp_path):
        """Test default md/ and json/ subdirectory creation."""
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps([]))
        
        # Test markdown only (default)
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path / "output1")
        )
        assert (tmp_path / "output1" / "md").exists()
        assert not (tmp_path / "output1" / "json").exists()
        
        # Test JSON only
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path / "output2"),
            output_format='json'
        )
        assert not (tmp_path / "output2" / "md").exists()
        assert (tmp_path / "output2" / "json").exists()
        
        # Test both
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path / "output3"),
            output_format='both'
        )
        assert (tmp_path / "output3" / "md").exists()
        assert (tmp_path / "output3" / "json").exists()
    
    def test_override_directories(self, tmp_path):
        """Test directory override options bypass subdirectory creation."""
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps([]))
        
        # Test markdown override
        custom_md = tmp_path / "custom_markdown"
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path / "output"),
            markdown_dir=str(custom_md)
        )
        assert custom_md.exists()
        assert not (tmp_path / "output" / "md").exists()
        
        # Test JSON override
        custom_json = tmp_path / "custom_json"
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path / "output2"),
            output_format='json',
            json_dir=str(custom_json)
        )
        assert custom_json.exists()
        assert not (tmp_path / "output2" / "json").exists()
    
    def test_permission_error_handling(self, tmp_path):
        """Test handling of permission errors during directory creation."""
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps([]))
        
        # Mock permission error
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("No permission")):
            with pytest.raises(PermissionError):
                extractor = ConversationExtractorV2(
                    str(input_file),
                    str(tmp_path / "output")
                )


class TestTimestampSynchronization:
    """Test file timestamp synchronization functionality."""
    
    def test_timestamp_parsing(self, tmp_path):
        """Test ISO timestamp parsing."""
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps([]))
        
        extractor = ConversationExtractorV2(str(input_file), str(tmp_path))
        
        # Valid timestamps
        ts = extractor.parse_iso_timestamp("2024-01-01T12:00:00Z")
        assert ts is not None
        assert ts > 0
        
        # Invalid timestamps
        assert extractor.parse_iso_timestamp("invalid") is None
        assert extractor.parse_iso_timestamp("") is None
        assert extractor.parse_iso_timestamp(None) is None
        
        # Pre-1970 timestamp (should return None)
        assert extractor.parse_iso_timestamp("1969-12-31T23:59:59Z") is None
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_timestamp_sync(self, tmp_path):
        """Test Windows-specific timestamp synchronization."""
        conversations = [{
            "id": "ts-test",
            "title": "Timestamp Test",
            "create_time": 1704067200,  # 2024-01-01 00:00:00
            "update_time": 1704153600,  # 2024-01-02 00:00:00
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Test"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            preserve_timestamps=True
        )
        extractor.extract_all()
        
        # Check file was created
        md_file = tmp_path / "md" / "Timestamp Test.md"
        assert md_file.exists()
        
        # Verify modification time was set (creation time requires special permissions)
        import os
        stat_info = os.stat(md_file)
        # Should be close to the update_time
        assert abs(stat_info.st_mtime - 1704153600) < 10
    
    def test_timestamp_sync_disabled(self, tmp_path):
        """Test that timestamp sync can be disabled."""
        conversations = [{
            "id": "no-ts",
            "title": "No Timestamp",
            "create_time": 1234567890,
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Test"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        
        extractor = ConversationExtractorV2(
            str(input_file),
            str(tmp_path),
            preserve_timestamps=False
        )
        extractor.extract_all()
        
        md_file = tmp_path / "md" / "No Timestamp.md"
        assert md_file.exists()
        
        # File should have current timestamp, not the old one
        import os
        import time
        stat_info = os.stat(md_file)
        current_time = time.time()
        assert abs(stat_info.st_mtime - current_time) < 60  # Within last minute