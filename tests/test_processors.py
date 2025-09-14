"""
Tests for the MessageProcessor class.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor.processors import MessageProcessor
from chatgpt_extractor.trackers import SchemaEvolutionTracker


class TestMessageProcessor:
    """Test suite for MessageProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a MessageProcessor instance."""
        tracker = SchemaEvolutionTracker()
        return MessageProcessor(tracker)

    def test_should_filter_message_visually_hidden(self, processor):
        """Test filtering of visually hidden messages."""
        msg = {
            "metadata": {"is_visually_hidden_from_conversation": True},
            "author": {"role": "assistant"},
            "content": {"content_type": "text"},
        }
        assert processor.should_filter_message(msg) is True

    def test_should_filter_message_system_non_user(self, processor):
        """Test filtering of non-user system messages."""
        msg = {
            "author": {"role": "system"},
            "content": {"content_type": "text"},
            "metadata": {},
        }
        assert processor.should_filter_message(msg) is True

    def test_should_not_filter_user_system_message(self, processor):
        """Test preservation of user system messages."""
        msg = {
            "author": {"role": "system"},
            "content": {"content_type": "text"},
            "metadata": {"is_user_system_message": True},
        }
        assert processor.should_filter_message(msg) is False

    def test_should_filter_tool_without_dalle(self, processor):
        """Test filtering of tool messages without DALL-E content."""
        msg = {
            "author": {"role": "tool"},
            "content": {"content_type": "text", "parts": ["Some output"]},
            "metadata": {},
        }
        assert processor.should_filter_message(msg) is True

    def test_should_not_filter_tool_with_dalle(self, processor):
        """Test preservation of tool messages with DALL-E content."""
        msg = {
            "author": {"role": "tool"},
            "content": {
                "content_type": "multimodal_text",
                "parts": [
                    {
                        "content_type": "image_asset_pointer",
                        "metadata": {"dalle": {"prompt": "A cat"}},
                    }
                ],
            },
            "metadata": {},
        }
        assert processor.should_filter_message(msg) is False

    def test_extract_message_content_text(self, processor):
        """Test extraction of simple text content."""
        msg = {"content": {"content_type": "text", "parts": ["Hello, world!"]}}
        result = processor.extract_message_content(msg, "test-id")
        assert result == "Hello, world!"

    def test_extract_message_content_code(self, processor):
        """Test extraction of code content."""
        msg = {
            "content": {
                "content_type": "code",
                "text": 'print("Hello")',
                "language": "python",
            }
        }
        result = processor.extract_message_content(msg, "test-id")
        assert result == '```python\nprint("Hello")\n```'

    def test_extract_message_content_execution_output(self, processor):
        """Test extraction of code execution output."""
        msg = {"content": {"content_type": "execution_output", "text": "Hello"}}
        result = processor.extract_message_content(msg, "test-id")
        assert result == "```output\nHello\n```"

    def test_extract_message_content_multimodal(self, processor):
        """Test extraction of multimodal content."""
        msg = {
            "content": {
                "content_type": "multimodal_text",
                "parts": [
                    "Text part",
                    {
                        "content_type": "image_asset_pointer",
                        "metadata": {"dalle": {"prompt": "A sunset"}},
                    },
                ],
            }
        }
        result = processor.extract_message_content(msg, "test-id")
        assert "Text part" in result
        assert "[DALL-E Image: A sunset]" in result

    def test_extract_from_parts_with_none(self, processor):
        """Test handling of None values in parts array."""
        parts = ["Hello", None, "World"]
        result = processor.extract_from_parts(parts, "test-id")
        assert result == "Hello\nWorld"

    def test_extract_citations(self, processor):
        """Test citation extraction."""
        msg = {
            "metadata": {
                "citations": [
                    {
                        "metadata": {
                            "title": "Example Article",
                            "url": "https://example.com",
                            "type": "webpage",
                        },
                        "quote": "Some quoted text",
                    }
                ]
            }
        }
        citations = processor.extract_citations(msg)
        assert len(citations) == 1
        assert citations[0]["title"] == "Example Article"
        assert citations[0]["url"] == "https://example.com"
        assert citations[0]["quote"] == "Some quoted text"

    def test_extract_web_urls_from_citations(self, processor):
        """Test URL extraction from citations."""
        msg = {
            "metadata": {
                "citations": [
                    {"metadata": {"url": "https://example.com"}},
                    {"metadata": {"url": "https://test.com"}},
                ]
            },
            "content": {"content_type": "text"},
        }
        urls = processor.extract_web_urls(msg)
        assert "https://example.com" in urls
        assert "https://test.com" in urls

    def test_extract_web_urls_from_content(self, processor):
        """Test URL extraction from content fields."""
        msg = {
            "content": {
                "content_type": "tether_quote",
                "url": "https://quoted.com",
                "domain": "example.org",
            },
            "metadata": {},
        }
        urls = processor.extract_web_urls(msg)
        assert "https://quoted.com" in urls
        assert "https://example.org" in urls

    def test_extract_web_urls_from_text(self, processor):
        """Test URL extraction from text using regex."""
        msg = {
            "content": {
                "content_type": "text",
                "parts": ["Check out https://example.com and https://test.org"],
            },
            "metadata": {},
        }
        urls = processor.extract_web_urls(msg)
        assert "https://example.com" in urls
        assert "https://test.org" in urls

    def test_extract_file_names_from_attachments(self, processor):
        """Test file name extraction from attachments."""
        msg = {
            "metadata": {
                "attachments": [{"name": "document.pdf"}, {"name": "image.png"}]
            },
            "content": {},
        }
        files = processor.extract_file_names(msg)
        assert "document.pdf" in files
        assert "image.png" in files

    def test_contains_dalle_image_none_metadata(self, processor):
        """Test DALL-E detection with None metadata (regression test)."""
        content = {
            "content_type": "multimodal_text",
            "parts": [
                {
                    "content_type": "image_asset_pointer",
                    "metadata": None,  # This caused the NoneType error
                }
            ],
        }
        # Should not raise TypeError
        result = processor._contains_dalle_image(content)
        assert result is False

    def test_user_editable_context_extraction(self, processor):
        """Test extraction of custom instructions."""
        msg = {
            "content": {
                "content_type": "user_editable_context",
                "text": "The user provided the following information about themselves:\nI am a developer.\nThe user provided the additional info about how they would like you to respond:\nBe concise.",
            }
        }
        result = processor.extract_message_content(msg, "test-id")
        assert "I am a developer" in result
        assert "Be concise" in result
        assert (
            "The user provided" not in result
            or len(result) < len(msg["content"]["text"]) * 0.9
        )
