"""
Performance tests to ensure extraction speed meets requirements.
"""

import json
import time
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor.extractor import ConversationExtractorV2


class TestPerformance:
    """Performance test suite."""

    def generate_conversations(self, count: int) -> list:
        """Generate sample conversations for performance testing."""
        conversations = []
        for i in range(count):
            conv = {
                "id": f"perf-test-{i:04d}",
                "title": f"Performance Test Conversation {i}",
                "create_time": 1704067200 + i,
                "update_time": 1704067200 + i + 3600,
                "mapping": {
                    "node-1": {
                        "id": "node-1",
                        "parent": None,
                        "children": ["node-2"],
                        "message": None,
                    },
                    "node-2": {
                        "id": "node-2",
                        "parent": "node-1",
                        "children": ["node-3"],
                        "message": {
                            "author": {"role": "user"},
                            "content": {
                                "content_type": "text",
                                "parts": [f"Question {i}: How do I learn Python?"],
                            },
                        },
                    },
                    "node-3": {
                        "id": "node-3",
                        "parent": "node-2",
                        "children": [],
                        "message": {
                            "author": {"role": "assistant"},
                            "content": {
                                "content_type": "text",
                                "parts": [
                                    f"Answer {i}: Here are some tips for learning Python..."
                                ],
                            },
                        },
                    },
                },
                "current_node": "node-3",
                "default_model_slug": "gpt-4",
            }
            conversations.append(conv)
        return conversations

    @pytest.mark.performance
    def test_extraction_speed_small(self):
        """Test extraction speed for small dataset (100 conversations)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "perf_test.json"
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Generate 100 conversations
            conversations = self.generate_conversations(100)

            with open(input_file, "w") as f:
                json.dump(conversations, f)

            # Measure extraction time
            start_time = time.time()

            extractor = ConversationExtractorV2(str(input_file), str(output_dir))
            extractor.extract_all()

            elapsed_time = time.time() - start_time
            rate = len(conversations) / elapsed_time

            print(
                f"\nProcessed {len(conversations)} conversations in {elapsed_time:.2f}s"
            )
            print(f"Rate: {rate:.1f} conversations/second")

            # Assert minimum performance (at least 30 conv/s for small datasets)
            assert (
                rate >= 30
            ), f"Performance too slow: {rate:.1f} conv/s (expected >= 30)"

    @pytest.mark.performance
    @pytest.mark.slow
    def test_extraction_speed_large(self):
        """Test extraction speed for larger dataset (1000 conversations)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "perf_test_large.json"
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Generate 1000 conversations
            conversations = self.generate_conversations(1000)

            with open(input_file, "w") as f:
                json.dump(conversations, f)

            # Measure extraction time
            start_time = time.time()

            extractor = ConversationExtractorV2(str(input_file), str(output_dir))
            # Suppress output for performance test
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                extractor.extract_all()
            finally:
                sys.stdout = old_stdout

            elapsed_time = time.time() - start_time
            rate = len(conversations) / elapsed_time

            print(
                f"\nProcessed {len(conversations)} conversations in {elapsed_time:.2f}s"
            )
            print(f"Rate: {rate:.1f} conversations/second")

            # Assert minimum performance (at least 50 conv/s for simple conversations)
            assert (
                rate >= 50
            ), f"Performance too slow: {rate:.1f} conv/s (expected >= 50)"

            # Check all files were created in md/ subdirectory
            md_dir = output_dir / "md"
            md_files = list(md_dir.glob("*.md")) if md_dir.exists() else []
            assert len(md_files) == len(conversations)

    def test_memory_usage(self):
        """Test that memory usage stays reasonable."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "memory_test.json"
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Generate a moderate dataset
            conversations = self.generate_conversations(500)

            with open(input_file, "w") as f:
                json.dump(conversations, f)

            extractor = ConversationExtractorV2(str(input_file), str(output_dir))

            # Suppress output
            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                extractor.extract_all()
            finally:
                sys.stdout = old_stdout

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            print(f"\nMemory usage increased by {memory_increase:.1f} MB")

            # Assert memory usage is reasonable (less than 500MB increase for 500 conversations)
            assert (
                memory_increase < 500
            ), f"Memory usage too high: {memory_increase:.1f} MB"
