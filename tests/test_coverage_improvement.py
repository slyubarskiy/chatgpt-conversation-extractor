"""
Integration tests for edge cases in conversation graph traversal and content extraction.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chatgpt_extractor.extractor import ConversationExtractorV2
from chatgpt_extractor.processors import MessageProcessor
from chatgpt_extractor.trackers import SchemaEvolutionTracker, ProgressTracker


class TestCoverageImprovement:
    """Edge case validation for graph traversal, content filtering, and schema evolution.
    
    These tests target specific code paths identified through coverage analysis,
    particularly around None handling, branched conversations, and content type variations.
    """
    
    def test_extractor_full_workflow(self, tmp_path):
        """End-to-end extraction with nested nodes and code content type validation."""
        conversations = [{
            "id": "test-123",
            "title": "Test Conversation",
            "create_time": 1234567890,
            "update_time": 1234567900,
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"], "message": None},
                "n2": {"id": "n2", "parent": "n1", "children": ["n3"], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Hello"]}
                }},
                "n3": {"id": "n3", "parent": "n2", "children": ["n4"], "message": {
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["Hi there!"]}
                }},
                "n4": {"id": "n4", "parent": "n3", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "code", "language": "python", "text": "print('test')"}
                }}
            },
            "current_node": "n4"
        }]
        
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"
        
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        extractor.extract_all()
        
        assert (output_dir / "Test Conversation.md").exists()
        
    def test_extractor_with_project_conversation(self, tmp_path):
        """Project folder creation and gizmo_id-based conversation grouping."""
        conversations = [{
            "id": "proj-456",
            "title": "Project Chat",
            "conversation_template_id": "g-p-myproject",
            "gizmo_id": "g-p-myproject",
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"], "message": None},
                "n2": {"id": "n2", "parent": "n1", "children": [], "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Project test"]}
                }}
            },
            "current_node": "n2"
        }]
        
        input_file = tmp_path / "proj.json"
        input_file.write_text(json.dumps(conversations))
        output_dir = tmp_path / "output"
        
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        extractor.extract_all()
        
        assert (output_dir / "g-p-myproject" / "Project Chat.md").exists()
    
    def test_message_processor_content_types(self):
        """Content type handler coverage for text, code, and execution_output."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # Text content
        text_msg = {"content": {"content_type": "text", "parts": ["Hello world"]}}
        result = processor.extract_message_content(text_msg, "test-1")
        assert result == "Hello world"
        
        # Code content  
        code_msg = {"content": {
            "content_type": "code",
            "language": "python",
            "text": "def hello():\n    print('world')"
        }}
        result = processor.extract_message_content(code_msg, "test-2")
        assert "```python" in result
        assert "def hello():" in result
        
        # Execution output
        exec_msg = {"content": {
            "content_type": "execution_output",
            "text": "Output: 42"
        }}
        result = processor.extract_message_content(exec_msg, "test-3")
        assert "```output" in result
        assert "Output: 42" in result
    
    def test_message_filtering(self):
        """Message visibility filtering based on metadata flags and role combinations."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # Should filter: visually hidden
        msg1 = {
            "author": {"role": "user"},
            "metadata": {"is_visually_hidden_from_conversation": True}
        }
        assert processor.should_filter_message(msg1) is True
        
        # Should not filter: regular user message
        msg2 = {
            "author": {"role": "user"},
            "metadata": {}
        }
        assert processor.should_filter_message(msg2) is False
        
        # Should not filter: user system message
        msg3 = {
            "author": {"role": "system"},
            "metadata": {"is_user_system_message": True}
        }
        assert processor.should_filter_message(msg3) is False
    
    def test_schema_evolution_tracker(self):
        """Schema discovery tracking with 10-sample limit enforcement."""
        tracker = SchemaEvolutionTracker()
        
        # Track content types
        tracker.track_content_type("text", "conv-1")
        tracker.track_content_type("code", "conv-2")
        tracker.track_content_type("unknown_type", "conv-3")
        
        # Track author roles
        tracker.track_author_role("user", "conv-1")
        tracker.track_author_role("assistant", "conv-2")
        tracker.track_author_role("new_role", "conv-3")
        
        # Track metadata keys
        tracker.track_metadata_keys({"key1": "val1", "key2": "val2"}, "conv-1")
        
        # Generate report
        report = tracker.generate_report()
        assert "unknown_type" in report
        assert "new_role" in report
    
    def test_progress_tracker_operations(self):
        """Progress metrics calculation and failure rate tracking."""
        tracker = ProgressTracker(100)
        
        # Update progress
        tracker.update(success=True)
        assert tracker.processed == 1
        assert tracker.failed == 0  # No failures yet
        
        tracker.update(success=False)
        assert tracker.processed == 2
        assert tracker.failed == 1
        
        # Final stats - using the actual method name
        stats = tracker.final_stats()
        assert stats["total"] == 100
        assert stats["processed"] == 2
        assert stats["failed"] == 1
        assert stats["success_rate"] > 0
    
    def test_filename_sanitization(self):
        """Cross-platform filename sanitization with 100-char truncation."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        # Normal title
        assert extractor.sanitize_filename("Normal Title") == "Normal Title"
        
        # Title with special chars
        sanitized = extractor.sanitize_filename("File/Name:With*Special?")
        assert "/" not in sanitized
        assert ":" not in sanitized
        assert "*" not in sanitized
        assert "?" not in sanitized
        
        # Very long title (over 100 chars)
        long_title = "A" * 150
        sanitized = extractor.sanitize_filename(long_title, max_length=100)
        assert len(sanitized) == 100
    
    def test_web_url_extraction(self):
        """URL pattern matching from message parts and metadata citations."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        message = {
            "content": {
                "content_type": "text",
                "parts": ["Visit https://example.com and http://test.org"]
            },
            "metadata": {}
        }
        
        # extract_web_urls now takes optional conv_data parameter
        urls = processor.extract_web_urls(message, None)
        assert "https://example.com" in urls
        assert "http://test.org" in urls
    
    def test_backward_traverse_complex(self):
        """Branch isolation in forked conversation DAG structures."""
        extractor = ConversationExtractorV2("dummy.json", "output")
        
        # Create a graph with branches
        mapping = {
            "root": {"id": "root", "parent": None, "children": ["a1", "b1"]},
            "a1": {"id": "a1", "parent": "root", "children": ["a2"], 
                   "message": {"content": "Branch A1"}},
            "a2": {"id": "a2", "parent": "a1", "children": [], 
                   "message": {"content": "Branch A2"}},
            "b1": {"id": "b1", "parent": "root", "children": ["b2"], 
                   "message": {"content": "Branch B1"}},
            "b2": {"id": "b2", "parent": "b1", "children": [], 
                   "message": {"content": "Branch B2"}}
        }
        
        # Traverse from branch A
        messages_a = extractor.backward_traverse(mapping, "a2", "test-conv")
        assert len(messages_a) == 2
        assert messages_a[0]["content"] == "Branch A1"
        assert messages_a[1]["content"] == "Branch A2"
        
        # Traverse from branch B
        messages_b = extractor.backward_traverse(mapping, "b2", "test-conv")
        assert len(messages_b) == 2
        assert messages_b[0]["content"] == "Branch B1"
        assert messages_b[1]["content"] == "Branch B2"
    
    def test_citation_extraction(self):
        """Citation metadata extraction from nested dictionary structures."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # No citations
        assert processor.extract_citations({}) == []
        
        # With citations in metadata - proper structure with metadata field
        msg = {
            "metadata": {
                "citations": [
                    {"metadata": {"title": "Source 1", "url": "https://source1.com"}},
                    {"metadata": {"title": "Source 2", "url": "https://source2.com"}}
                ]
            }
        }
        citations = processor.extract_citations(msg)
        assert len(citations) == 2  # Should extract both citations
    
    def test_file_attachment_extraction(self):
        """Attachment metadata parsing for uploaded file references."""
        tracker = SchemaEvolutionTracker()
        processor = MessageProcessor(tracker)
        
        # No attachments
        assert processor.extract_file_names({}) == []
        
        # With attachments - needs to be in metadata field of message
        msg = {
            "metadata": {
                "attachments": [
                    {"name": "file1.pdf"},
                    {"name": "file2.txt"}
                ]
            }
        }
        files = processor.extract_file_names(msg)
        assert "file1.pdf" in files
        assert "file2.txt" in files