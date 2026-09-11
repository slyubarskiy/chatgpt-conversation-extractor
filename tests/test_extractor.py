"""
Tests for the main ConversationExtractorV2 class.
"""

import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor.extractor import ConversationExtractorV2
from tests.test_helpers import capture_logs, assert_in_logs


class TestConversationExtractorV2:
    """Test suite for ConversationExtractorV2."""

    @pytest.fixture
    def sample_data(self):
        """Load sample conversation data."""
        fixture_path = Path(__file__).parent / "fixtures" / "sample_conversation.json"
        with open(fixture_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.json"
            output_dir = temp_path / "output"
            output_dir.mkdir()
            yield input_file, output_dir

    def test_initialization(self, temp_dirs):
        """Test extractor initialization."""
        input_file, output_dir = temp_dirs

        # Create empty JSON file
        with open(input_file, "w") as f:
            json.dump([], f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        assert extractor.input_file == input_file
        assert extractor.output_dir == output_dir
        assert output_dir.exists()

    def test_initialization_without_input_file(self, temp_dirs):
        """Construct without input_file — supports callers operating on dicts
        already in memory who do not need a file on disk."""
        _, output_dir = temp_dirs
        extractor = ConversationExtractorV2(output_dir=str(output_dir))
        assert extractor.input_file is None
        assert extractor.output_dir == output_dir

    def test_extract_all_without_input_file_raises(self, temp_dirs):
        """extract_all() must raise a clear ValueError if no input_file was
        supplied — clearer than the cryptic open(None) failure it would
        otherwise produce."""
        _, output_dir = temp_dirs
        extractor = ConversationExtractorV2(output_dir=str(output_dir))
        with pytest.raises(ValueError, match="input_file"):
            extractor.extract_all()

    def test_initialization_without_output_dir_raises(self):
        """output_dir is typed Optional only because Python forbids a non-default
        arg after a default one; it is runtime-required."""
        with pytest.raises(ValueError, match="output_dir"):
            ConversationExtractorV2()

    def test_extract_metadata(self, temp_dirs, sample_data):
        """Test metadata extraction from conversation."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        metadata = extractor.extract_metadata(sample_data[0])

        assert metadata["id"] == "test-conv-001"
        assert metadata["title"] == "Test Conversation"
        assert metadata["model"] == "gpt-4"
        assert "created" in metadata
        assert "updated" in metadata
        assert metadata["chat_url"] == "https://chatgpt.com/c/test-conv-001"

    @pytest.mark.parametrize(
        "tz_name", ["UTC", "Europe/London", "US/Pacific", "Asia/Kolkata"]
    )
    def test_extract_metadata_timestamps_are_true_utc(
        self, temp_dirs, sample_data, monkeypatch, tz_name
    ):
        """Frontmatter ``created`` / ``updated`` are true UTC regardless of
        host timezone. Regression guard against a prior bug that emitted
        ``datetime.fromtimestamp(t).isoformat() + "Z"`` — naive local
        wall time falsely labelled as UTC. Under BST the resulting value
        was +1h ahead of reality; under IST it was +5:30 ahead. This
        test drives four representative TZs (zero offset, +1h summer,
        negative offset, non-hour-aligned offset) and asserts the byte-
        level output is identical to what UTC would produce.
        """
        import time as _time_mod

        # tzset() is POSIX-only; skip cleanly on Windows CI runners.
        if not hasattr(_time_mod, "tzset"):
            pytest.skip(
                "time.tzset() not available (Windows) — TZ envvar has no effect"
            )
        monkeypatch.setenv("TZ", tz_name)
        _time_mod.tzset()

        input_file, output_dir = temp_dirs
        # Deterministic epochs the ChatGPT API uses (seconds since 1970):
        # 1704067200 = 2024-01-01T00:00:00Z, 1704153600 = 2024-01-02T00:00:00Z.
        conv = {
            "id": "tz-test",
            "title": "TZ Test",
            "create_time": 1704067200,
            "update_time": 1704153600,
            "mapping": {},
        }
        with open(input_file, "w") as f:
            json.dump([conv], f)
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))
        metadata = extractor.extract_metadata(conv)

        assert (
            metadata["created"] == "2024-01-01T00:00:00Z"
        ), f"created was {metadata['created']!r} under TZ={tz_name}"
        assert (
            metadata["updated"] == "2024-01-02T00:00:00Z"
        ), f"updated was {metadata['updated']!r} under TZ={tz_name}"

    def test_backward_traverse(self, temp_dirs, sample_data):
        """Test backward traversal of conversation graph."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        conv = sample_data[0]
        messages = extractor.backward_traverse(
            conv["mapping"], conv["current_node"], conv["id"]
        )

        # Should have 3 messages (system, user, assistant)
        assert len(messages) == 3

        # Check order (should be chronological after reversal)
        assert messages[0]["author"]["role"] == "system"
        assert messages[1]["author"]["role"] == "user"
        assert messages[2]["author"]["role"] == "assistant"

    def test_backward_traverse_missing_current_node(self, temp_dirs):
        """Test backward traversal with missing current_node."""
        input_file, output_dir = temp_dirs

        # Create conversation without current_node
        conv = {
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
                    "children": [],
                    "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Hello"]},
                        "weight": 1.0,
                        "update_time": 1704067200,
                    },
                },
            },
            "current_node": None,
        }

        with open(input_file, "w") as f:
            json.dump([conv], f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        # Should find highest-weight leaf
        messages = extractor.backward_traverse(conv["mapping"], None, "test-id")

        assert len(messages) == 1
        assert messages[0]["author"]["role"] == "user"

    def test_process_messages(self, temp_dirs, sample_data):
        """Test message processing and filtering."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        conv = sample_data[0]
        raw_messages = extractor.backward_traverse(
            conv["mapping"], conv["current_node"], conv["id"]
        )

        processed = extractor.process_messages(raw_messages, conv["id"], conv)

        # System message should be preserved (is_user_system_message=true)
        assert len(processed) == 3
        assert processed[0]["role"] == "system"
        assert processed[1]["role"] == "user"
        assert processed[2]["role"] == "assistant"

    def test_extract_metadata_survives_explicit_null_title(self, temp_dirs):
        """Regression guard for the null-title fix landed in PR #2.

        Some OpenAI exports contain conversations whose ``title`` field is
        present with an explicit ``null`` value (as opposed to omitted).
        ``dict.get("title", "Untitled")`` returns the default ONLY when the
        key is missing — an explicit ``None`` value passes through and later
        crashes ``re.sub`` in ``sanitize_filename`` and slicing in
        ``extract_all``'s failure logging. The fix uses
        ``conv.get("title") or "Untitled"`` in five call sites and widens
        ``sanitize_filename``'s signature to accept ``Optional[str]``.
        """
        input_file, output_dir = temp_dirs
        conv = {
            "id": "null-title-conv",
            "title": None,  # explicit null — the key exists but has no value
            "create_time": 1704067200,
            "update_time": 1704067200,
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"], "message": None},
                "n2": {
                    "id": "n2",
                    "parent": "n1",
                    "children": [],
                    "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Hi"]},
                    },
                },
            },
            "current_node": "n2",
        }
        with open(input_file, "w") as f:
            json.dump([conv], f)
        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        # extract_metadata substitutes the fallback title
        metadata = extractor.extract_metadata(conv)
        assert metadata["title"] == "Untitled Conversation"

        # sanitize_filename tolerates None directly
        assert extractor.sanitize_filename(None) == "untitled"

        # extract_all completes without raising the historical TypeError
        extractor.extract_all()
        # And a file actually got written under the fallback name
        assert any((output_dir / "md").glob("Untitled Conversation*.md"))

    def test_generate_markdown(self, temp_dirs, sample_data):
        """Test markdown generation."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        metadata = {
            "id": "test-001",
            "title": "Test Conversation",
            "created": "2024-01-01T00:00:00Z",
            "model": "gpt-4",
        }

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        markdown = extractor.generate_markdown(metadata, messages)

        # Check YAML frontmatter
        assert "---" in markdown
        assert "id: test-001" in markdown
        assert "title: Test Conversation" in markdown

        # Check content
        assert "# Test Conversation" in markdown
        assert "## User" in markdown
        assert "Hello" in markdown
        assert "## Assistant" in markdown
        assert "Hi there!" in markdown

    def test_sanitize_filename(self, temp_dirs):
        """Test filename sanitization."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump([], f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        # Test various problematic characters
        assert extractor.sanitize_filename("Hello/World") == "Hello_World"
        assert extractor.sanitize_filename("File:Name") == "File_Name"
        assert extractor.sanitize_filename("Question?") == "Question_"
        assert extractor.sanitize_filename("*Important*") == "_Important_"

        # Test length truncation
        long_title = "a" * 150
        sanitized = extractor.sanitize_filename(long_title)
        assert len(sanitized) <= 100

        # Test empty result
        assert extractor.sanitize_filename("...") == "untitled"

    def test_save_to_file(self, temp_dirs):
        """Test file saving functionality."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump([], f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        metadata = {"title": "Test Save", "id": "test-001"}
        content = "# Test Content"

        extractor.save_markdown_file(metadata, content)

        # Check file was created in md/ subdirectory
        output_file = output_dir / "md" / "Test Save.md"
        assert output_file.exists()

        # Check content
        with open(output_file, "r") as f:
            saved_content = f.read()
        assert saved_content == content

    def test_save_to_file_with_project(self, temp_dirs):
        """Test file saving with project organization."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump([], f)

        extractor = ConversationExtractorV2(str(input_file), str(output_dir))

        metadata = {
            "title": "Project Conv",
            "id": "test-001",
            "project_id": "g-p-test-123",
        }
        content = "# Project Content"

        extractor.save_markdown_file(metadata, content)

        # Check project directory was created in md/ subdirectory
        project_dir = output_dir / "md" / "g-p-test-123"
        assert project_dir.exists()

        # Check file in project directory
        output_file = project_dir / "Project Conv.md"
        assert output_file.exists()

    def test_extract_all_integration(self, temp_dirs, sample_data, capsys):
        """Integration test for full extraction process."""
        input_file, output_dir = temp_dirs

        with open(input_file, "w") as f:
            json.dump(sample_data, f)

        with capture_logs(
            "chatgpt_extractor.chatgpt_extractor.extractor"
        ) as log_capture:
            extractor = ConversationExtractorV2(str(input_file), str(output_dir))
            extractor.extract_all()

            # Check output files were created
            md_files = list(output_dir.glob("**/*.md"))
            assert len(md_files) >= 1  # At least one conversation extracted

            # Check for project folder in md/ subdirectory
            md_dir = output_dir / "md"
            if md_dir.exists():
                project_dirs = [
                    d
                    for d in md_dir.iterdir()
                    if d.is_dir() and d.name.startswith("g-p-")
                ]
                assert len(project_dirs) == 1  # One project folder

            # Check schema evolution log
            schema_log = output_dir / "schema_evolution.log"
            assert schema_log.exists()

            # Check log output instead of console output
            assert_in_logs(log_capture, "EXTRACTION COMPLETE!")
            assert_in_logs(log_capture, "Success rate:")


class TestBranchParentLinks:
    """Rendering of the branch → parent lineage footer.

    ChatGPT shows, inside a branched chat, a hyperlink to the chat it was
    branched from. The vault output mirrors that. A chatgpt.com URL is used
    rather than an Obsidian wiki-link because the parent's vault filename is
    not knowable at render time — it depends on collision suffixing, filename
    sanitisation and later renames, all decided outside the extractor. The URL
    survives all three; only the link *text* can age.
    """

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Own fixture — the one above is scoped to TestConversationExtractorV2."""
        input_file = tmp_path / "input.json"
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        yield input_file, output_dir

    @staticmethod
    def _extractor(temp_dirs, **kw):
        input_file, output_dir = temp_dirs
        input_file.write_text("[]", encoding="utf-8")
        return ConversationExtractorV2(str(input_file), str(output_dir), **kw)

    @staticmethod
    def _meta(**kw):
        base = {
            "id": "child-1",
            "title": "Child Conv",
            "created": "2024-01-01T00:00:00Z",
        }
        base.update(kw)
        return base

    def test_carrier_message_renders_branch_footer(self, temp_dirs):
        ex = self._extractor(temp_dirs)
        messages = [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": "Reply",
                "branched_from": {"id": "parent-9", "title": "Parent Title"},
            },
        ]
        md = ex.generate_markdown(self._meta(), messages)
        assert (
            "**Branched from:** [Parent Title]"
            "(https://chatgpt.com/c/parent-9) `parent-9`" in md
        )

    def test_non_carrier_messages_get_no_footer(self, temp_dirs):
        """Only the message that actually carries the marker is annotated."""
        ex = self._extractor(temp_dirs)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Reply"},
        ]
        md = ex.generate_markdown(self._meta(), messages)
        assert "**Branched from:**" not in md

    def test_footer_comes_after_the_url_blocks(self, temp_dirs):
        """The marker describes conversation structure, not message content,
        so it is the last block — after Citations / Sources / Web Search URLs."""
        ex = self._extractor(temp_dirs)
        messages = [
            {
                "role": "assistant",
                "content": "Reply",
                "web_urls": ["https://example.com/a"],
                "branched_from": {"id": "p1", "title": "P"},
            }
        ]
        md = ex.generate_markdown(self._meta(), messages)
        assert md.index("**Web Search URLs:**") < md.index("**Branched from:**")

    def test_missing_parent_title_falls_back_to_id(self, temp_dirs):
        """Never render an empty link label."""
        ex = self._extractor(temp_dirs)
        for title in (None, ""):
            messages = [
                {
                    "role": "assistant",
                    "content": "R",
                    "branched_from": {"id": "p2", "title": title or "p2"},
                }
            ]
            md = ex.generate_markdown(self._meta(), messages)
            assert "[p2](https://chatgpt.com/c/p2)" in md
            assert "[](" not in md

    def test_frontmatter_carries_branched_from_id(self, temp_dirs):
        ex = self._extractor(temp_dirs)
        md = ex.generate_markdown(
            self._meta(branched_from_id="parent-9"),
            [{"role": "user", "content": "Hi"}],
        )
        assert "branched_from_id: parent-9" in md

    def test_marker_survives_consecutive_assistant_merge(self, temp_dirs):
        """Regression: continuation merging must not drop the branch marker.

        Consecutive assistant messages are merged into one rendered turn, and
        the merge builds a fresh dict copying only an explicit allow-list of
        keys. ``branched_from`` was missing from that list, so any branch whose
        carrier sat in a merged run rendered no footer at all — while still
        getting the frontmatter id, because that comes from a separate
        conversation-level scan. Caught on real data (the Pavel Bocharov
        family), not by the simpler unit tests above.
        """
        ex = self._extractor(temp_dirs)

        def raw(role, text, branch=False):
            """A raw ChatGPT message as backward traversal yields it."""
            md = {}
            if branch:
                md = {
                    "branching_from_conversation_id": "p-merge",
                    "branching_from_conversation_title": "Parent",
                }
            return {
                "author": {"role": role},
                "content": {"content_type": "text", "parts": [text]},
                "metadata": md,
            }

        for position in ("first", "later"):
            msgs = [
                raw("user", "q"),
                raw("assistant", "part one", branch=(position == "first")),
                raw("assistant", "part two", branch=(position == "later")),
            ]
            # merge_continuations is what drops keys, and it runs inside
            # process_conversation -- NOT process_messages. Testing the
            # latter would pass while the real pipeline still lost the marker.
            merged = ex.merge_continuations(ex.process_messages(msgs, "conv-1", {}))
            md = ex.generate_markdown(self._meta(), merged)
            assert "**Branched from:**" in md, f"lost when carrier was {position}"
            assert "`p-merge`" in md

    def test_branch_links_flag_off_reproduces_pre_feature_output(self, temp_dirs):
        """A caller wanting byte-identical pre-feature output must have a way
        to get it — this writes into the message body, unlike frontmatter."""
        messages = [
            {
                "role": "assistant",
                "content": "Reply",
                "branched_from": {"id": "p3", "title": "P3"},
            }
        ]
        on = self._extractor(temp_dirs, branch_links=True).generate_markdown(
            self._meta(), messages
        )
        off = self._extractor(temp_dirs, branch_links=False).generate_markdown(
            self._meta(), messages
        )
        assert "**Branched from:**" in on
        assert "**Branched from:**" not in off
