"""
Comprehensive tests to achieve 80%+ code coverage.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import time

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chatgpt_extractor.extractor import ConversationExtractorV2
from chatgpt_extractor.processors import MessageProcessor
from chatgpt_extractor.trackers import SchemaEvolutionTracker, ProgressTracker


class TestExtractorComprehensive:
    """Comprehensive tests for ConversationExtractorV2."""
    
    def test_extract_all_with_various_scenarios(self, tmp_path):
        """Test extract_all with different conversation scenarios."""
        conversations = [
            # Normal conversation
            {
                "id": "conv-1",
                "title": "Normal Chat",
                "create_time": 1234567890,
                "update_time": 1234567900,
                "mapping": {
                    "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                    "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Hello"]}
                    }}
                },
                "current_node": "n2"
            },
            # Conversation with missing current_node
            {
                "id": "conv-2",
                "title": "Missing Current",
                "mapping": {
                    "n1": {"id": "n1", "parent": None, "children": ["n2"]},
                    "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Test"]}
                    }}
                }
            },
            # Empty mapping
            {
                "id": "conv-3",
                "title": "Empty Mapping",
                "mapping": {},
                "current_node": "n1"
            }
        ]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"
        
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        extractor.extract_all()
        
        # Check files created
        assert output_dir.exists()
        assert (output_dir / "Normal Chat.md").exists()
        
    def test_process_conversation_with_errors(self, tmp_path):
        """Test process_conversation error handling."""
        extractor = ConversationExtractorV2("dummy.json", str(tmp_path))
        
        # Test with None conversation
        extractor.process_conversation(None)
        
        # Test with conversation missing id
        conv_no_id = {"title": "No ID", "mapping": {}}
        extractor.process_conversation(conv_no_id)
        
        # Test with conversation missing mapping
        conv_no_mapping = {"id": "test", "title": "No Mapping"}
        extractor.process_conversation(conv_no_mapping)
        
    def test_extract_metadata_comprehensive(self):
        """Test metadata extraction with all fields."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        conv = {
            "id": "test-123",
            "title": "Test Title",
            "create_time": 1234567890.123,
            "update_time": 1234567900.456,
            "conversation_template_id": "g-p-project-id",
            "gizmo_id": "g-p-gizmo-id",
            "default_model_slug": "gpt-4",
            "custom_instructions": {
                "about_user": "User info",
                "about_model": "Model info"
            }
        }
        
        metadata = extractor.extract_metadata(conv)
        assert metadata["id"] == "test-123"
        assert metadata["title"] == "Test Title"
        assert metadata["model"] == "gpt-4"
        assert metadata["project_id"] == "g-p-project-id"
        
    def test_backward_traverse_edge_cases(self):
        """Test backward traverse with edge cases."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        # Empty mapping
        messages = extractor.backward_traverse({}, None, "test-1")
        assert messages == []
        
        # Circular reference protection
        circular_mapping = {
            "n1": {"id": "n1", "parent": "n2", "message": {"content": "1"}},
            "n2": {"id": "n2", "parent": "n1", "message": {"content": "2"}}
        }
        messages = extractor.backward_traverse(circular_mapping, "n1", "test-2")
        assert len(messages) <= 2  # Should stop at cycle
        
    def test_process_messages_comprehensive(self):
        """Test message processing with various content types."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        messages = [
            # User message with text
            {
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["User text"]},
                "metadata": {}
            },
            # Assistant message with code
            {
                "author": {"role": "assistant"},
                "content": {
                    "content_type": "code",
                    "language": "python",
                    "text": "print('hello')"
                },
                "metadata": {}
            },
            # System message (should be filtered)
            {
                "author": {"role": "system"},
                "content": {"content_type": "text", "parts": ["System"]},
                "metadata": {}
            },
            # Tool message (should be filtered)
            {
                "author": {"role": "tool"},
                "content": {"content_type": "text", "parts": ["Tool output"]},
                "metadata": {}
            }
        ]
        
        # process_messages now needs conv_data parameter
        conv_data = {"id": "test-conv", "title": "Test Conversation"}
        processed = extractor.process_messages(messages, "test-conv", conv_data)
        assert len(processed) >= 2  # User and assistant messages
        
    def test_merge_continuations(self):
        """Test message continuation merging."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        messages = [
            {"role": "user", "content": "Question?"},
            {"role": "assistant", "content": "Part 1"},
            {"role": "assistant", "content": "Part 2"},
            {"role": "user", "content": "Another?"},
            {"role": "assistant", "content": "Answer"}
        ]
        
        # Add graph indices
        for i, msg in enumerate(messages):
            msg["_graph_index"] = i
        
        merged = extractor.merge_continuations(messages)
        # Should merge the two consecutive assistant messages
        assert len(merged) == 4
        
    def test_generate_markdown(self):
        """Test markdown generation."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        metadata = {
            "id": "test-123",
            "title": "Test Conversation",
            "create_time": "2024-01-01",
            "model": "gpt-4",
            "word_count": 100,
            "message_count": 2
        }
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        markdown = extractor.generate_markdown(metadata, messages)
        # YAML frontmatter uses --- not ```yaml
        assert "---" in markdown
        assert "id: test-123" in markdown
        assert "Test Conversation" in markdown
        assert "## User" in markdown
        assert "## Assistant" in markdown
        
    def test_save_to_file_with_project(self, tmp_path):
        """Test saving file with project organization."""
        extractor = ConversationExtractorV2("dummy.json", str(tmp_path))
        
        metadata = {
            "id": "test-123",
            "title": "Project File",
            "project_id": "g-p-myproject"
        }
        
        content = "# Test Content"
        extractor.save_to_file(metadata, content)
        
        # Check project directory created
        project_dir = tmp_path / "g-p-myproject"
        assert project_dir.exists()
        assert (project_dir / "Project File.md").exists()
        
    def test_sanitize_filename_various_inputs(self):
        """Test filename sanitization with various inputs."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        # Normal filename
        assert extractor.sanitize_filename("Normal") == "Normal"
        
        # With special characters
        sanitized = extractor.sanitize_filename("File/Name:Test*")
        assert "/" not in sanitized
        assert ":" not in sanitized
        
        # Very long filename
        long_name = "A" * 200
        sanitized = extractor.sanitize_filename(long_name)  # max_length parameter doesn't exist
        assert len(sanitized) <= 100  # Default max length is 100
        
        # Empty string
        assert extractor.sanitize_filename("") == "untitled"
        
        # Only special characters - becomes underscores
        assert extractor.sanitize_filename("///:::***") == "_________"
        
    def test_log_conversion_failure(self, tmp_path):
        """Test conversion failure logging."""
        extractor = ConversationExtractorV2("dummy.json", str(tmp_path))
        
        conv = {"id": "fail-1", "title": "Failed Conv"}
        error = Exception("Test error")
        extractor.log_conversion_failure(conv, "fail-1", "Failed Conv", error)
        
        assert len(extractor.conversion_failures) == 1
        assert extractor.conversion_failures[0]["error_message"] == "Test error"
        
    def test_save_conversion_log(self, tmp_path):
        """Test saving conversion log."""
        extractor = ConversationExtractorV2("dummy.json", str(tmp_path))
        
        # Add some failures with correct structure
        extractor.conversion_failures = [
            {"conversation_id": "f1", "title": "Fail 1", "error_message": "Error 1", "error_type": "TestError", "category": "Other", "structural_issues": []},
            {"conversation_id": "f2", "title": "Fail 2", "error_message": "Error 2", "error_type": "TestError", "category": "Other", "structural_issues": []}
        ]
        
        extractor.save_conversion_log()
        
        log_file = tmp_path / "conversion_log.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Total Failures: 2" in content
        
    def test_save_schema_report(self, tmp_path):
        """Test schema evolution report saving."""
        extractor = ConversationExtractorV2("dummy.json", str(tmp_path))
        
        # Track some schema elements
        extractor.schema_tracker.track_content_type("text", "conv-1")
        extractor.schema_tracker.track_content_type("unknown_type", "conv-2")
        
        extractor.save_schema_report()
        
        report_file = tmp_path / "schema_evolution.log"
        assert report_file.exists()


class TestMessageProcessorComprehensive:
    """Comprehensive tests for MessageProcessor."""
    
    def test_extract_message_content_all_types(self):
        """Test extraction of all content types."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # Text content - wrap in message structure
        text_msg = {"content": {"content_type": "text", "parts": ["Hello"]}}
        result = processor.extract_message_content(text_msg, "test-1")
        assert result == "Hello"
        
        # Code content - wrap in message structure
        code_msg = {"content": {
            "content_type": "code",
            "language": "python",
            "text": "print('test')"
        }}
        result = processor.extract_message_content(code_msg, "test-2")
        assert "```python" in result
        
        # Multimodal text - wrap in message structure
        multimodal_msg = {"content": {
            "content_type": "multimodal_text",
            "parts": ["Text", {"content_type": "code", "text": "code"}]
        }}
        result = processor.extract_message_content(multimodal_msg, "test-3")
        assert "Text" in result
        
        # Execution output - wrap in message structure
        exec_msg = {"content": {
            "content_type": "execution_output",
            "text": "Output text"
        }}
        result = processor.extract_message_content(exec_msg, "test-4")
        assert "Output text" in result
        
        # Unknown type - wrap in message structure
        unknown_msg = {"content": {"content_type": "unknown_type", "data": "something"}}
        result = processor.extract_message_content(unknown_msg, "test-5")
        assert result is None or result == ""
        
    def test_should_filter_message_various_cases(self):
        """Test message filtering logic."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # Hidden message
        hidden = {
            "author": {"role": "user"},
            "metadata": {"is_visually_hidden_from_conversation": True}
        }
        assert processor.should_filter_message(hidden) is True
        
        # User system message (should not filter)
        user_system = {
            "author": {"role": "system"},
            "metadata": {"is_user_system_message": True}
        }
        assert processor.should_filter_message(user_system) is False
        
        # Regular user message
        regular = {
            "author": {"role": "user"},
            "metadata": {}
        }
        assert processor.should_filter_message(regular) is False
        
    def test_extract_web_urls(self):
        """Test URL extraction from messages."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        message = {
            "content": {
                "content_type": "text",
                "parts": ["Visit https://example.com and http://test.org"]
            },
            "metadata": {
                "citations": [
                    {"url": "https://cite.com"}
                ]
            }
        }
        
        urls = processor.extract_web_urls(message)
        assert len(urls) >= 2
        assert "https://example.com" in urls
        
    def test_extract_file_names(self):
        """Test file name extraction."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        metadata = {
            "attachments": [
                {"name": "file1.pdf"},
                {"name": "file2.txt"}
            ]
        }
        
        # Pass full message structure with metadata field
        msg = {"metadata": metadata}
        files = processor.extract_file_names(msg)
        assert "file1.pdf" in files
        assert "file2.txt" in files


class TestTrackersComprehensive:
    """Comprehensive tests for tracker classes."""
    
    def test_schema_evolution_tracker(self):
        """Test SchemaEvolutionTracker functionality."""
        tracker = SchemaEvolutionTracker()
        
        # Track various elements
        tracker.track_content_type("text", "conv-1")
        tracker.track_content_type("code", "conv-2")
        tracker.track_content_type("unknown", "conv-3")
        
        tracker.track_author_role("user", "conv-1")
        tracker.track_author_role("assistant", "conv-2")
        tracker.track_author_role("unknown_role", "conv-3")
        
        tracker.track_metadata_keys({"key1": "val1"}, "conv-1")
        tracker.track_metadata_keys({"key2": "val2"}, "conv-2")
        
        tracker.track_part_type("text", "conv-1")  # Only takes 2 arguments
        tracker.track_part_type("image", "conv-2")
        
        # Generate report
        report = tracker.generate_report()
        assert "unknown" in report
        assert "unknown_role" in report
        
    def test_progress_tracker(self):
        """Test ProgressTracker functionality."""
        tracker = ProgressTracker(100)
        
        # Update progress
        tracker.update(success=True)
        assert tracker.processed == 1
        assert tracker.failed == 0  # No failures yet
        
        tracker.update(success=False)
        assert tracker.processed == 2
        assert tracker.failed == 1
        
        # Show progress
        with patch('builtins.print'):
            tracker.show_progress()
        
        # Final stats - using correct method name
        stats = tracker.final_stats()
        assert stats["total"] == 100
        assert stats["processed"] == 2
        assert stats["failed"] == 1
        assert stats["success_rate"] == 50.0


class TestIntegration:
    """Integration tests for full workflow."""
    
    def test_full_extraction_workflow(self, tmp_path):
        """Test complete extraction workflow."""
        # Create comprehensive test data
        conversations = [
            {
                "id": "conv-complete",
                "title": "Complete Test",
                "create_time": 1234567890,
                "update_time": 1234567900,
                "conversation_template_id": "g-p-test-project",
                "custom_instructions": {
                    "about_user": "Test user",
                    "about_model": "Test model"
                },
                "mapping": {
                    "root": {"id": "root", "parent": None, "children": ["msg1"]},
                    "msg1": {"id": "msg1", "parent": "root", "children": ["msg2"], 
                            "message": {
                                "author": {"role": "user"},
                                "content": {"content_type": "text", "parts": ["Hello AI"]},
                                "metadata": {}
                            }},
                    "msg2": {"id": "msg2", "parent": "msg1", "children": ["msg3"],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["Hello human!"]},
                                "metadata": {}
                            }},
                    "msg3": {"id": "msg3", "parent": "msg2", "children": [],
                            "message": {
                                "author": {"role": "user"},
                                "content": {
                                    "content_type": "code",
                                    "language": "python",
                                    "text": "def greet():\n    print('Hi')"
                                },
                                "metadata": {"attachments": [{"name": "script.py"}]}
                            }}
                },
                "current_node": "msg3"
            }
        ]
        
        input_file = tmp_path / "complete.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"
        
        # Run extraction
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        extractor.extract_all()
        
        # Verify results
        project_dir = output_dir / "g-p-test-project"
        assert project_dir.exists()
        
        md_file = project_dir / "Complete Test.md"
        assert md_file.exists()
        
        content = md_file.read_text()
        assert "Complete Test" in content
        assert "Hello AI" in content
        assert "Hello human!" in content
        assert "```python" in content
        assert "script.py" in content