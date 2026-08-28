"""
Main extractor class for ChatGPT conversation processing.
"""

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from collections import defaultdict

import yaml

from .processors import MessageProcessor
from .trackers import SchemaEvolutionTracker, ProgressTracker
from .logging_config import get_logger, log_exception

# Constants for JSON output formatting
JSON_EXPORT_FILENAME_PATTERN = "conversations_export_{timestamp}.json"
TIMESTAMP_FORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S.%fZ"


class ConversationExtractorV2:
    """Enhanced ChatGPT conversation extractor with multi-format output support.

    Supports markdown and JSON output formats with configurable directory
    structure and timestamp synchronization. Single JSON consolidates all
    conversations for bulk analysis; multiple JSON preserves individual
    conversation context for targeted processing.
    """

    def __init__(
        self,
        input_file: Optional[str] = None,
        output_dir: Optional[str] = None,
        output_format: str = "markdown",
        json_format: str = "multiple",
        markdown_dir: Optional[str] = None,
        json_dir: Optional[str] = None,
        json_file: Optional[str] = None,
        preserve_timestamps: bool = True,
        per_turn_timestamps: Optional[bool] = None,
        gpt_metadata: Optional[bool] = None,
        gpt_names_xlsx: Optional[str] = None,
        web_urls: Optional[Union[str, Dict[str, str]]] = None,
        config_path: Optional[str] = None,
    ):
        """Initialize the extractor with multi-format configuration.

        Args:
            input_file: Path to conversations.json. Optional — only required if
                        extract_all() will be called. Per-conversation methods
                        (process_conversation, generate_markdown, save_markdown_file,
                        sanitize_filename) operate on dicts already in memory and
                        do not need a file on disk.
            output_dir: Base directory for output files (required). Typed Optional
                        only because Python signature ordering requires a default
                        once input_file has one; runtime-validated as required.
            output_format: 'markdown', 'json', or 'both'
            json_format: 'single' or 'multiple' for JSON output
            markdown_dir: Override path for markdown output (bypasses md/ subdirectory)
            json_dir: Override path for multiple JSON output (bypasses json/ subdirectory)
            json_file: Override path for single JSON output file
            preserve_timestamps: Sync file timestamps with conversation metadata
                                 (individual files only; single JSON uses processing time)
            per_turn_timestamps: When True (default), emit per-message
                        timestamps as italic ISO-8601 UTC lines beneath each
                        role heading in markdown output, and as the
                        ``timestamp`` field in JSON output. Pass ``False`` to
                        match the pre-config behaviour (conversation-level
                        timestamps in YAML frontmatter only). Pass ``None``
                        (default) to read from the config file; the config
                        file itself defaults to ``True``.
            gpt_metadata: When True (default), enrich output with Custom
                        GPT / per-turn model / plugin signals. Frontmatter
                        gains ``gizmo_id`` (only for Custom GPTs, not
                        projects), ``gizmo_type``, ``conversation_origin``
                        (provenance, e.g. ``tpp`` for the desktop app),
                        and ``models_used`` (the
                        deduped set of per-message ``model_slug`` values).
                        The per-turn italic line gains ``· model_slug``,
                        ``· plugin:<namespace>``, and ``· gpt:<id>`` (the
                        last only when the per-message gizmo differs from
                        the conversation default — the @mention case). JSON
                        per-message dicts gain ``model_slug``, ``gizmo_id``,
                        ``plugin_namespace``. Pass ``False`` for legacy
                        output; ``None`` (default) reads from the config
                        file (itself defaults to ``True``).
            gpt_names_xlsx: Optional path to a ``GPT_Names.xlsx`` sidecar
                        (id → human-readable name). When provided AND the
                        file is readable, frontmatter gains a ``gpt_name:``
                        field for Custom GPT conversations, and per-turn
                        ``gpt:<id>`` is replaced by ``gpt:<Pretty Name>``
                        where a name is known. Missing file or malformed
                        workbook silently degrades to id-only output —
                        the extractor never crashes on a bad sidecar.
                        ``None`` (default) reads from the config file
                        (itself defaults to ``None``, i.e. no resolution).
            web_urls: Per-type URL-extraction control. Accepts a preset
                        string (``off | citations | rich``) or an explicit
                        per-type dict (see ``config.py``). ``None``
                        (default) reads from the config file, which itself
                        defaults in this fork to rich source context for
                        desktop search (citations rich + safe_urls off +
                        search_result_groups/content_references rich).
                        The ``citations`` preset
                        is the leanest useful setting for BM25/embedding
                        indexers wanting inline citation context but no
                        URL bulk; ``rich`` adds title + snippet blocks
                        from search_result_groups + content_references.
            config_path: Path to a YAML config file overriding built-in
                        defaults. Searches ``$CHATGPT_EXTRACTOR_CONFIG``,
                        ``./chatgpt_extractor.yaml``, and
                        ``~/.config/chatgpt_extractor/config.yaml`` if not
                        explicitly supplied. See ``config.py`` for the
                        layering rules.
        """
        self.logger = get_logger(__name__)
        if output_dir is None:
            raise ValueError("output_dir is required")
        # input_file is optional: callers using only per-conversation methods on
        # in-memory dicts don't need a file on disk. extract_all() validates that
        # it was supplied (clear error instead of a cryptic open(None) failure).
        self.input_file = Path(input_file) if input_file else None
        self.output_dir = Path(output_dir)

        # Store format configuration
        self.output_format = output_format
        self.json_format = json_format
        self.preserve_timestamps = preserve_timestamps

        # Resolve flag-style config values: explicit constructor arg wins;
        # otherwise consult the config file (which itself falls back to a
        # True default). Loaded once and shared across all flags so a
        # single config-file read covers all knobs.
        _cfg = None
        if (
            per_turn_timestamps is None
            or gpt_metadata is None
            or gpt_names_xlsx is None
            or web_urls is None
        ):
            from .config import load_config

            _cfg = load_config(config_path)
        if per_turn_timestamps is None:
            per_turn_timestamps = bool(_cfg.get("per_turn_timestamps", True))
        if gpt_metadata is None:
            gpt_metadata = bool(_cfg.get("gpt_metadata", True))
        if gpt_names_xlsx is None:
            # ``None`` here means "no name resolution" — distinct from
            # the per_turn / gpt_metadata booleans which default True.
            gpt_names_xlsx = _cfg.get("gpt_names_xlsx") if _cfg else None
        if web_urls is None:
            web_urls = _cfg.get("web_urls") if _cfg else None
        # Normalize into a fully-populated per-type dict. Preset strings +
        # partial dicts + invalid values are resolved / logged / coerced
        # per config._resolve_web_urls.
        from .config import _resolve_web_urls
        self.web_urls: Dict[str, str] = _resolve_web_urls(
            web_urls, log=self.logger
        )
        self.per_turn_timestamps = per_turn_timestamps
        self.gpt_metadata = gpt_metadata
        # Load the gpt_id → name map once at construct time; downstream
        # reads (extract_metadata + generate_markdown) reuse the same
        # dict. Missing / bad sidecar → empty dict, no crash.
        from .gpt_metadata import load_gpt_names_xlsx

        self._gpt_names: Dict[str, str] = load_gpt_names_xlsx(gpt_names_xlsx)

        # Determine output paths based on configuration
        self.output_paths = self.determine_output_paths(
            markdown_dir, json_dir, json_file
        )

        # Create necessary directories early for permission validation
        self._create_output_directories()

        self.schema_tracker = SchemaEvolutionTracker()
        self.message_processor = MessageProcessor(self.schema_tracker)

        self.conversion_failures: List[Dict[str, Any]] = []

        # Track format-specific processing for enhanced reporting
        self.markdown_processed = 0
        self.json_processed = 0
        self.timestamp_sync_failures = 0

    def determine_output_paths(
        self,
        markdown_dir: Optional[str] = None,
        json_dir: Optional[str] = None,
        json_file: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Resolve output paths based on format configuration and override arguments.

        Default structure creates md/ and json/ subdirectories unless overridden.
        Override paths bypass subdirectory creation to support legacy workflows
        and custom organizational needs. Single JSON path includes timestamp
        unless explicitly specified via json_file override.

        Args:
            markdown_dir: Override path for markdown output
            json_dir: Override path for JSON multiple output
            json_file: Override path for single JSON file

        Returns:
            Dictionary with resolved paths for each output format
        """
        paths = {}

        # Markdown output path resolution
        if self.output_format in ["markdown", "both"]:
            if markdown_dir:
                # Override bypasses subdirectory structure
                paths["markdown_dir"] = Path(markdown_dir)
            else:
                # Default: create md/ subdirectory
                paths["markdown_dir"] = self.output_dir / "md"

        # JSON output path resolution
        if self.output_format in ["json", "both"]:
            if self.json_format == "multiple":
                if json_dir:
                    # Override bypasses subdirectory structure
                    paths["json_dir"] = Path(json_dir)
                else:
                    # Default: create json/ subdirectory
                    paths["json_dir"] = self.output_dir / "json"
            else:  # single JSON format
                if json_file:
                    # Explicit file path override
                    paths["json_file"] = Path(json_file)
                else:
                    # Default: timestamped file in output root
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = JSON_EXPORT_FILENAME_PATTERN.format(timestamp=timestamp)
                    paths["json_file"] = self.output_dir / filename

        return paths

    def _create_output_directories(self) -> None:
        """Create necessary output directories with early permission validation.

        Directory creation failures halt processing immediately since write
        permissions are required for all subsequent operations. Project
        subdirectories created on-demand during processing to avoid empty folders.
        """
        try:
            # Always create base output directory
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Create format-specific directories
            if "markdown_dir" in self.output_paths:
                self.output_paths["markdown_dir"].mkdir(parents=True, exist_ok=True)
                self.logger.debug(
                    f"Created markdown directory: {self.output_paths['markdown_dir']}"
                )

            if "json_dir" in self.output_paths:
                self.output_paths["json_dir"].mkdir(parents=True, exist_ok=True)
                self.logger.debug(
                    f"Created JSON directory: {self.output_paths['json_dir']}"
                )

            # For single JSON, ensure parent directory exists
            if "json_file" in self.output_paths:
                self.output_paths["json_file"].parent.mkdir(parents=True, exist_ok=True)

        except PermissionError as e:
            self.logger.critical(f"Permission denied creating output directory: {e}")
            raise
        except Exception as e:
            log_exception(self.logger, e, "creating output directories")
            raise

    def extract_all(self) -> None:
        """Main extraction process for all conversations."""
        if self.input_file is None:
            raise ValueError(
                "extract_all() requires input_file to be set at construction time"
            )
        self.logger.info(f"ChatGPT Conversation Extractor v2.0")
        self.logger.info(f"{'='*60}")

        try:
            self.logger.info(f"Loading conversations from {self.input_file}")
            with open(self.input_file, "r", encoding="utf-8") as f:
                conversations = json.load(f)
        except FileNotFoundError:
            self.logger.critical(f"Input file not found: {self.input_file}")
            raise
        except json.JSONDecodeError as e:
            self.logger.critical(
                f"Invalid JSON in {self.input_file}: Line {e.lineno}, Column {e.colno}"
            )
            self.logger.debug(f"JSON error details: {e.msg}")
            raise
        except PermissionError as e:
            self.logger.critical(f"Permission denied reading {self.input_file}")
            raise
        except Exception as e:
            log_exception(self.logger, e, "loading conversations")
            raise

        self.logger.info(f"Found {len(conversations)} conversations to process")
        self.logger.info(f"Output directory: {self.output_dir}")
        if self.output_format in ["markdown", "both"]:
            self.logger.info(
                f"Markdown output: {self.output_paths.get('markdown_dir', 'N/A')}"
            )
        if self.output_format in ["json", "both"]:
            if self.json_format == "multiple":
                self.logger.info(
                    f"JSON output: {self.output_paths.get('json_dir', 'N/A')}"
                )
            else:
                self.logger.info(
                    f"JSON output: {self.output_paths.get('json_file', 'N/A')}"
                )

        progress = ProgressTracker(total=len(conversations))

        # Collect conversations for single JSON if needed
        json_conversations = (
            []
            if (self.output_format in ["json", "both"] and self.json_format == "single")
            else None
        )

        for conv in conversations:
            try:
                result = self.process_conversation(conv)
                if result:
                    metadata, messages, json_data = result

                    # Save markdown if enabled
                    if self.output_format in ["markdown", "both"]:
                        content = self.generate_markdown(metadata, messages)
                        file_path = self.save_markdown_file(metadata, content)
                        self.markdown_processed += 1
                        # Sync timestamps for individual files
                        if self.preserve_timestamps:
                            self.synchronize_file_timestamps(file_path, metadata)

                    # Handle JSON output
                    if self.output_format in ["json", "both"]:
                        if self.json_format == "multiple":
                            # Save individual JSON file
                            file_path = self.save_json_multiple(
                                json_data, self.output_paths["json_dir"]
                            )
                            # Sync timestamps for individual files
                            if self.preserve_timestamps:
                                self.synchronize_file_timestamps(file_path, metadata)
                        else:
                            # Collect for single file
                            json_conversations.append(json_data)

                progress.update(success=True)
            except Exception as e:
                conv_id = conv.get("id", conv.get("conversation_id", "unknown"))
                title = (conv.get("title") or "Untitled")[:50]
                self.log_conversion_failure(conv, conv_id, title, e)
                progress.update(success=False)

        # Save single JSON file if needed
        if json_conversations is not None and json_conversations:
            try:
                self.save_json_single(
                    json_conversations, self.output_paths["json_file"]
                )
                self.json_processed = len(json_conversations)
            except Exception as e:
                self.logger.error(f"Failed to save consolidated JSON: {e}")

        if not self.logger.handlers:
            print()  # Only print if no logging handlers

        self.save_schema_report()
        if self.conversion_failures:
            self.save_conversion_log()

        self.print_summary(progress)

    def process_conversation(
        self, conv: Dict[str, Any]
    ) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]]:
        """Process single conversation for all configured output formats.

        Returns tuple of (metadata, messages, json_data) for format-specific
        processing. None return indicates empty/invalid conversation that
        should be skipped. JSON data pre-generated for consistency between
        single and multiple output modes.

        Args:
            conv: Raw conversation dictionary from export

        Returns:
            Tuple of (metadata, messages, json_data) or None if empty
        """
        if not conv:
            self.logger.warning("Skipping None or empty conversation")
            return None

        metadata = self.extract_metadata(conv)
        conv_id = metadata["id"]

        mapping = conv.get("mapping", {})
        current_node = conv.get("current_node")

        messages = self.backward_traverse(mapping, current_node, conv_id)

        # Collect statistics from raw messages
        stats = self.collect_message_statistics(messages, conv_id)

        processed = self.process_messages(messages, conv_id, conv)

        merged = self.merge_continuations(processed)

        if merged:
            # Enrich metadata with usage analytics for search and filtering
            metadata["total_messages"] = len(merged)
            code_count = stats["code_count"]
            assert isinstance(code_count, int)
            metadata["code_messages"] = code_count
            if stats["content_types"]:
                content_types = stats["content_types"]
                assert isinstance(content_types, set)
                metadata["message_types"] = ", ".join(sorted(content_types))
            if stats["custom_instructions"]:
                custom_instructions = stats["custom_instructions"]
                assert isinstance(custom_instructions, dict)
                metadata["custom_instructions"] = custom_instructions

            # Generate JSON data if needed
            json_data = None
            if self.output_format in ["json", "both"]:
                json_data = self.generate_json_data(metadata, merged)

            return metadata, merged, json_data

        return None

    def extract_metadata(self, conv: Dict[str, Any]) -> Dict[str, Any]:
        """Extract conversation metadata for YAML frontmatter.

        Args:
            conv: Conversation dictionary from JSON export

        Returns:
            Metadata dict with id, title, timestamps, model, URLs
        """
        metadata = {}

        metadata["id"] = conv.get("id", conv.get("conversation_id", "unknown"))

        metadata["title"] = conv.get("title") or "Untitled Conversation"

        # Emit timestamps as true UTC. A prior version of this code used
        # ``datetime.fromtimestamp(t).isoformat() + "Z"`` which returns local
        # wall time (naive) and then falsely labelled it UTC — the resulting
        # frontmatter values were off by the operator's local UTC offset
        # (e.g. +1h under BST). Passing ``tz=timezone.utc`` makes the value
        # authoritative regardless of host timezone; the ``+00:00`` suffix
        # is replaced with ``Z`` to keep the byte-level layout consumers
        # already parse (matches _format_per_turn_ts).
        if create_time := conv.get("create_time"):
            metadata["created"] = (
                datetime.fromtimestamp(create_time, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        if update_time := conv.get("update_time"):
            metadata["updated"] = (
                datetime.fromtimestamp(update_time, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        if model := conv.get("default_model_slug"):
            metadata["model"] = model

        # Always include starred and archived flags
        # Convert None to False for consistency
        metadata["starred"] = conv.get("is_starred", False) or False
        metadata["archived"] = conv.get("is_archived", False)

        metadata["chat_url"] = f"https://chatgpt.com/c/{metadata['id']}"

        if project_id := conv.get("conversation_template_id"):
            if project_id.startswith("g-p-"):
                metadata["project_id"] = project_id

        # Custom GPT / per-turn model / models_used. Module-isolated so the
        # extractor doesn't grow another paragraph of inline shape-poking;
        # online_sync inherits via OnlineRenderer wrapping this class.
        if self.gpt_metadata:
            from .gpt_metadata import (
                extract_conv_deep_research_meta,
                extract_conv_gpt_meta,
            )

            metadata.update(extract_conv_gpt_meta(conv))
            # Resolve gizmo_id → human-readable name when the sidecar map
            # has it. Lookups against an empty dict are O(1) no-ops, so we
            # don't gate this on a separate "names enabled" flag.
            if gid := metadata.get("gizmo_id"):
                if name := self._gpt_names.get(gid):
                    metadata["gpt_name"] = name
            # Deep Research detection. Empty dict for non-DR convs is a
            # safe no-op merge; positive detections add `deep_research:
            # true` (and `deep_research_version` when known) so DR convs
            # become greppable even though their artifact body remains
            # absent from the export.
            metadata.update(extract_conv_deep_research_meta(conv))

        return metadata

    def collect_message_statistics(
        self, messages: List[Dict[str, Any]], conv_id: str
    ) -> Dict[str, Union[int, Set[str], Optional[Dict[str, str]]]]:
        """Collect statistics from raw messages.

        Args:
            messages: Raw messages from backward traversal
            conv_id: Conversation ID for tracking

        Returns:
            Dictionary with message statistics
        """
        stats: Dict[str, Union[int, Set[str], Optional[Dict[str, str]]]] = {
            "code_count": 0,
            "content_types": set(),
            "custom_instructions": None,
        }

        for msg in messages:
            # Track content types
            content = msg.get("content", {})
            content_type = content.get("content_type", "")
            if content_type:
                content_types = stats["content_types"]
                assert isinstance(content_types, set)
                content_types.add(content_type)

            # Count code messages
            if content_type == "code":
                code_count = stats["code_count"]
                assert isinstance(code_count, int)
                stats["code_count"] = code_count + 1
            elif content_type == "execution_output":
                code_count = stats["code_count"]
                assert isinstance(code_count, int)
                stats["code_count"] = code_count + 1
            elif content_type == "multimodal_text":
                # Code outputs in multimodal messages indicate code execution occurred
                for part in content.get("parts", []):
                    if (
                        isinstance(part, dict)
                        and part.get("content_type") == "code_interpreter_output"
                    ):
                        code_count = stats["code_count"]
                        assert isinstance(code_count, int)
                        stats["code_count"] = code_count + 1
                        break

            # Capture user's ChatGPT personalization settings from first system message
            if (
                content_type == "user_editable_context"
                and not stats["custom_instructions"]
            ):
                # Custom instructions can be in two places:
                # 1. In metadata.user_context_message_data (newer format)
                # 2. In content.text (older format)

                # First check metadata (newer format)
                metadata = msg.get("metadata", {})
                user_context_data = metadata.get("user_context_message_data")
                if user_context_data and isinstance(user_context_data, dict):
                    instructions = {}
                    if about_user := user_context_data.get("about_user_message"):
                        instructions["about_user_message"] = about_user
                    if about_model := user_context_data.get("about_model_message"):
                        instructions["about_model_message"] = about_model
                    if instructions:
                        stats["custom_instructions"] = instructions

                # If not found in metadata, check content.text (older format)
                elif text := content.get("text", ""):
                    # Parse the custom instructions format
                    about_user = None
                    about_model = None

                    # Look for the two sections
                    if (
                        "The user provided the following information about themselves:"
                        in text
                    ):
                        parts = text.split(
                            "The user provided the additional info about how they would like you to respond:"
                        )
                        if len(parts) == 2:
                            about_user = (
                                parts[0]
                                .replace(
                                    "The user provided the following information about themselves:",
                                    "",
                                )
                                .strip()
                            )
                            about_model = parts[1].strip()
                        else:
                            # Try alternative format
                            about_user = text.replace(
                                "The user provided the following information about themselves:",
                                "",
                            ).strip()

                    if about_user or about_model:
                        instructions = {}
                        if about_user:
                            instructions["about_user_message"] = about_user
                        if about_model:
                            instructions["about_model_message"] = about_model
                        stats["custom_instructions"] = instructions

        return stats

    def backward_traverse(
        self, mapping: Dict[str, Any], current_node: Optional[str], conv_id: str
    ) -> List[Dict[str, Any]]:
        """Traverse conversation graph backwards from current node to root.

        Args:
            mapping: Node ID to node object mapping from conversation
            current_node: Starting node ID (may be None)
            conv_id: Conversation ID for error tracking

        Returns:
            List of messages in chronological order (root to current)

        Note:
            O(n) complexity vs O(n² for forward traversal with branches.
            Automatically excludes edited/regenerated branches.
        """
        if not mapping:
            return []

        # Fallback strategy: Find highest-weight leaf if current_node missing
        if not current_node or current_node not in mapping:
            leaves = []
            for node_id, node in mapping.items():
                if not node.get("children"):
                    if node.get("message"):
                        leaves.append(node)

            if not leaves:
                return []

            # Prioritize by weight, then update_time for deterministic selection
            current_node = max(
                leaves,
                key=lambda n: (
                    n.get("message", {}).get("weight", 0),
                    n.get("message", {}).get("update_time", 0),
                ),
            ).get("id")

        # O(n) backward traversal automatically excludes edited branches
        messages = []
        node_id = current_node
        visited = set()  # Prevent infinite loops in malformed graphs

        while node_id and node_id not in visited:
            visited.add(node_id)
            node = mapping.get(node_id)

            if not node:
                break

            if msg := node.get("message"):
                if metadata := msg.get("metadata"):
                    self.schema_tracker.track_metadata_keys(metadata, conv_id)

                if author := msg.get("author"):
                    if role := author.get("role"):
                        self.schema_tracker.track_author_role(role, conv_id)
                    if recipient := author.get("recipient"):
                        self.schema_tracker.track_recipient(recipient, conv_id)

                if finish_details := msg.get("finish_details"):
                    if finish_details.get("type"):
                        self.schema_tracker.track_finish_type(
                            finish_details["type"], conv_id
                        )

                messages.append(msg)

            node_id = node.get("parent") if node else None

        return list(reversed(messages))

    @staticmethod
    def _format_per_turn_ts(unix_seconds: float) -> str:
        """Format a Unix timestamp as ISO-8601 UTC for per-turn rendering.

        Uses true UTC (``datetime.fromtimestamp(t, tz=timezone.utc)``),
        matching the conversation-level ``created`` / ``updated`` fields
        in YAML frontmatter. Both surfaces emit true UTC as of the TZ-skew
        fix; a previous version of frontmatter used naive local wall time
        (mislabelled ``"Z"``), and this divergence has been removed.
        """
        return (
            datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def process_messages(
        self, messages: List[Dict[str, Any]], conv_id: str, conv_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter and process messages for markdown output.

        Args:
            messages: Raw messages from backward traversal
            conv_id: Conversation ID for tracking
            conv_data: Full conversation data for URL extraction

        Returns:
            Processed messages with content, role, and metadata
        """
        processed = []
        system_prompt_added = False

        for msg in messages:
            if self.message_processor.should_filter_message(msg):
                continue

            author_role = msg.get("author", {}).get("role")

            if author_role == "system":
                if (
                    not system_prompt_added
                    and self.message_processor.is_user_system_message(msg)
                ):
                    content = self.message_processor.extract_message_content(
                        msg, conv_id
                    )
                    if content:
                        processed.append({"role": "system", "content": content})
                        system_prompt_added = True
                continue

            if author_role in ["user", "assistant"]:
                content = self.message_processor.extract_message_content(msg, conv_id)
                if content:  # Only add if has content after filtering
                    msg_data = {"role": author_role, "content": content}

                    # Preserve per-message create_time when present on the
                    # source. Surfaced under each role heading in markdown
                    # output and as the ``timestamp`` field in JSON output
                    # (gated on the per_turn_timestamps flag at render time).
                    if (ct := msg.get("create_time")) is not None:
                        msg_data["create_time"] = ct

                    # Per-turn GPT signals (model_slug, gizmo_id, plugin
                    # namespace). Stashed unconditionally because their
                    # cost is trivial; the render-time flag decides
                    # whether they reach the markdown / JSON output.
                    from .gpt_metadata import extract_msg_gpt_signals

                    for k, v in extract_msg_gpt_signals(msg).items():
                        if v is not None:
                            msg_data[k] = v

                    # Citations are only surfaced as the **Citations:**
                    # block when the citations config level is "rich". At
                    # "minimal", the URLs still contribute via
                    # _walk_url_sources but no rich block renders. At
                    # "off", citations aren't extracted at all.
                    if self.web_urls.get("citations") == "rich":
                        citations = self.message_processor.extract_citations(msg)
                        if citations:
                            msg_data["citations"] = citations

                    # Single-pass URL walk — one traversal per message
                    # halves metadata-scan cost on large exports.
                    urls, web_sources = self.message_processor._walk_url_sources(
                        msg, conv_data, self.web_urls
                    )
                    if urls:
                        msg_data["web_urls"] = urls
                    if web_sources:
                        msg_data["web_sources"] = web_sources

                    files = self.message_processor.extract_file_names(msg)
                    if files:
                        msg_data["files"] = files

                    # Graph index needed for validating true adjacency in merging
                    if "_graph_index" in msg:
                        msg_data["_graph_index"] = msg["_graph_index"]

                    processed.append(msg_data)

            # Tool messages included only if they contain DALL-E images
            # OR a Deep Research artifact (widget_state.report_message).
            elif author_role == "tool":
                content = msg.get("content", {})
                if self.message_processor._contains_dalle_image(content):
                    extracted = self.message_processor.extract_message_content(
                        msg, conv_id
                    )
                    if extracted:
                        tool_msg_data = {"role": "assistant", "content": extracted}
                        if (ct := msg.get("create_time")) is not None:
                            tool_msg_data["create_time"] = ct
                        from .gpt_metadata import extract_msg_gpt_signals

                        for k, v in extract_msg_gpt_signals(msg).items():
                            if v is not None:
                                tool_msg_data[k] = v
                        processed.append(tool_msg_data)
                else:
                    # Deep Research artifact carve-out: the substantive
                    # answer lives on a tool message at
                    # metadata.chatgpt_sdk.widget_state.report_message
                    # (stringified JSON). The flanking assistant turns
                    # are empty (chatgpt_sdk_suppressed_response: True),
                    # so without this branch the body is silently dropped
                    # — the vault gets a 59-line stub.
                    from .gpt_metadata import (
                        extract_dr_report_message,
                        extract_msg_gpt_signals,
                    )

                    report_msg = extract_dr_report_message(msg)
                    if report_msg:
                        rm_parts = (
                            (report_msg.get("content") or {}).get("parts") or []
                        )
                        text = "\n\n".join(
                            p for p in rm_parts if isinstance(p, str) and p
                        )
                        if text:
                            dr_data: Dict[str, Any] = {
                                "role": "assistant",
                                "content": text,
                            }
                            # Inherit per-turn signals from the
                            # report_message's own metadata (its
                            # model_slug / gizmo_id / plugin_namespace
                            # describe the synthesis turn, not the
                            # surrounding tool-call wrapper).
                            if (rct := report_msg.get("create_time")) is not None:
                                dr_data["create_time"] = rct
                            for k, v in extract_msg_gpt_signals(report_msg).items():
                                if v is not None:
                                    dr_data[k] = v
                            # Citations from the research live on the
                            # report_message — preserve via the standard
                            # MessageProcessor helper.
                            citations = self.message_processor.extract_citations(
                                report_msg
                            )
                            if citations:
                                dr_data["citations"] = citations
                            processed.append(dr_data)

        return processed

    def merge_continuations(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge consecutive assistant messages that are continuations.

        Validates messages are truly consecutive using graph indices when available.
        """
        if not messages:
            return messages

        merged = []
        i = 0

        while i < len(messages):
            current = messages[i]

            if current["role"] != "assistant":
                merged.append(current)
                i += 1
                continue

            if (
                i + 1 < len(messages)
                and current["role"] == "assistant"
                and messages[i + 1]["role"] == "assistant"
            ):

                combined_content = current["content"]

                # Collect all consecutive assistant messages
                j = i + 1
                while j < len(messages) and messages[j]["role"] == "assistant":
                    combined_content += "\n\n" + messages[j]["content"]

                    if "citations" in messages[j]:
                        if "citations" not in current:
                            current["citations"] = []
                        current["citations"].extend(messages[j]["citations"])

                    if "web_urls" in messages[j]:
                        if "web_urls" not in current:
                            current["web_urls"] = []
                        current["web_urls"].extend(messages[j]["web_urls"])

                    if "web_sources" in messages[j]:
                        if "web_sources" not in current:
                            current["web_sources"] = []
                        current["web_sources"].extend(messages[j]["web_sources"])

                    j += 1

                merged_msg = {"role": "assistant", "content": combined_content}

                # Inherit the earliest segment's create_time as the response's
                # start time — matches how a reader would interpret "when did
                # the assistant begin replying."
                if "create_time" in current:
                    merged_msg["create_time"] = current["create_time"]

                # Per-turn GPT signals inherit from the earliest segment too
                # (the assistant's reply may continue across segments but the
                # model / gizmo / plugin context applies to the whole reply).
                for k in ("model_slug", "gizmo_id", "plugin_namespace"):
                    if k in current:
                        merged_msg[k] = current[k]

                if "citations" in current:
                    merged_msg["citations"] = current["citations"]
                if "web_urls" in current:
                    merged_msg["web_urls"] = sorted(list(set(current["web_urls"])))
                if "web_sources" in current:
                    # Dedupe by normalized URL — sets don't work on dicts, so
                    # walk once and keep the first occurrence per URL.
                    seen_urls: Set[str] = set()
                    deduped_sources: List[Dict[str, Any]] = []
                    for src in current["web_sources"]:
                        u = src.get("url") if isinstance(src, dict) else None
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            deduped_sources.append(src)
                    if deduped_sources:
                        merged_msg["web_sources"] = deduped_sources

                merged.append(merged_msg)
                i = j
            else:
                merged.append(current)
                i += 1

        return merged

    def generate_markdown(
        self, metadata: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> str:
        """Generate markdown content with YAML frontmatter for conversation."""
        lines = []

        lines.append("---")
        for key, value in metadata.items():
            if key == "custom_instructions" and isinstance(value, dict):
                # Format custom instructions as a YAML block string
                lines.append("custom_instructions: |")
                for inst_key, inst_value in value.items():
                    # Escape the value properly for YAML
                    escaped_value = inst_value.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'  {inst_key}: "{escaped_value}"')
            elif isinstance(value, str) and (":" in value or '"' in value):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")

        lines.append(f"# {metadata['title']}")
        lines.append("")

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                lines.append("## System")
            elif role == "user":
                lines.append("## User")
            elif role == "assistant":
                lines.append("## Assistant")
            else:
                lines.append(f"## {role.title()}")

            # Per-turn timestamp (italic ISO line under the role heading).
            # Gated on the flag so callers using --no-per-turn-timestamps
            # get exactly the pre-config output. System messages are skipped
            # because the system prompt's "send time" is conceptually the
            # custom-instructions configuration time, not a chat moment.
            if (
                self.per_turn_timestamps
                and role != "system"
                and (ct := msg.get("create_time")) is not None
            ):
                # GPT-metadata suffix piggybacks on the per-turn timestamp
                # line: " · model_slug · plugin:<ns> · gpt:<name-or-id>"
                # where any absent segment is suppressed. gpt:<...> only
                # fires when the per-message gizmo differs from the
                # conversation default (the @mention pattern). The
                # ``gpt:`` segment shows the human-readable name when
                # ``_gpt_names`` resolves it, else falls back to the id.
                suffix = ""
                if self.gpt_metadata:
                    from .gpt_metadata import format_per_turn_suffix

                    suffix = format_per_turn_suffix(
                        msg,
                        metadata.get("gizmo_id"),
                        names_map=self._gpt_names,
                    )
                lines.append(f"*{self._format_per_turn_ts(ct)}{suffix}*")

            if role == "user" and "files" in msg:
                for file in msg["files"]:
                    lines.append(f"[File: {file}]")

            lines.append(content)

            # Citations block (existing behavior — only surfaces when
            # web_urls.citations is "rich", gated in process_messages).
            # Collect its URLs for cross-block dedup below.
            citation_urls: Set[str] = set()
            if "citations" in msg:
                lines.append("")
                lines.append("**Citations:**")
                for citation in msg["citations"]:
                    title = citation.get("title") or "Untitled"
                    url = citation.get("url", "")
                    type_ = citation.get("type", "webpage")

                    if url:
                        lines.append(f"- [{type_}] {title} - {url}")
                        citation_urls.add(url)
                    else:
                        lines.append(f"- [{type_}] {title}")

            # Sources block (new — rich extraction from search_result_groups
            # + content_references at "rich" level). Format:
            #   - [title](url) — snippet
            # Snippet omitted if absent; title falls back to url host.
            source_urls: Set[str] = set()
            if "web_sources" in msg and msg["web_sources"]:
                lines.append("")
                lines.append("**Sources:**")
                for src in msg["web_sources"]:
                    if not isinstance(src, dict):
                        continue
                    url = src.get("url") or ""
                    title = src.get("title") or url or "Untitled"
                    snippet = src.get("snippet")
                    if url:
                        source_urls.add(url)
                        if snippet:
                            lines.append(f"- [{title}]({url}) — {snippet}")
                        else:
                            lines.append(f"- [{title}]({url})")
                    else:
                        lines.append(f"- {title}")

            # Web Search URLs block — URL-only bulk. Apply cross-block
            # markdown dedup: skip URLs already surfaced in the Citations
            # or Sources block above. Dedup is MARKDOWN-ONLY; the JSON
            # output keeps citations / web_urls / web_sources whole so
            # downstream indexers don't silently lose data.
            if "web_urls" in msg and msg["web_urls"]:
                already_shown = citation_urls | source_urls
                remaining = [u for u in msg["web_urls"] if u not in already_shown]
                if remaining:
                    lines.append("")
                    lines.append("**Web Search URLs:**")
                    for url in remaining:
                        lines.append(f"- {url}")

            lines.append("")

        return "\n".join(lines)

    def save_markdown_file(self, metadata: Dict[str, Any], content: str) -> Path:
        """Save markdown content to file with proper directory structure.

        Project conversations maintain subfolder organization. Collision
        handling uses numbered suffixes to preserve all conversations.
        Returns path for optional timestamp synchronization.

        Args:
            metadata: Conversation metadata including title and project_id
            content: Generated markdown content

        Returns:
            Path to the created markdown file
        """
        title = metadata["title"]
        safe_title = self.sanitize_filename(title)

        # Use markdown_dir from output_paths
        output_dir = self.output_paths.get("markdown_dir", self.output_dir)

        if project_id := metadata.get("project_id"):
            project_dir = output_dir / project_id
            try:
                project_dir.mkdir(exist_ok=True)
            except PermissionError:
                self.logger.error(
                    f"Permission denied creating project directory {project_dir}"
                )
                raise
            except Exception as e:
                log_exception(
                    self.logger, e, f"creating project directory {project_dir}"
                )
                raise
            file_path = project_dir / f"{safe_title}.md"
        else:
            file_path = output_dir / f"{safe_title}.md"

        # Handle filename collisions with numeric suffix
        if file_path.exists():
            counter = 2
            while True:
                if metadata.get("project_id"):
                    new_path = file_path.parent / f"{safe_title} ({counter}).md"
                else:
                    new_path = output_dir / f"{safe_title} ({counter}).md"

                if not new_path.exists():
                    file_path = new_path
                    break
                counter += 1

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.debug(f"Successfully wrote {file_path}")
            return file_path
        except PermissionError:
            self.logger.error(f"Permission denied writing to {file_path}")
            raise
        except IOError as e:
            self.logger.error(f"I/O error writing to {file_path}: {e}")
            raise
        except Exception as e:
            log_exception(self.logger, e, f"writing to {file_path}")
            raise

    def sanitize_filename(self, title: Optional[str], max_length: int = 100) -> str:
        """Convert title to safe filename."""
        # Handle None title
        if title is None:
            title = "untitled"
        
        # Windows/Unix forbidden characters: <>:"/\|?*
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)

        # ASCII control characters (0-31) break filesystem operations
        safe_title = "".join(char for char in safe_title if ord(char) >= 32)

        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rstrip()

        # Windows silently strips trailing dots/spaces, causing mismatches
        safe_title = safe_title.rstrip(". ")

        if not safe_title:
            safe_title = "untitled"

        return safe_title

    def generate_json_data(
        self, metadata: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Convert conversation data to exportable JSON structure.

        Strips internal tracking fields (_graph_index) and normalizes
        custom_instructions from legacy string format to structured dict.
        Single-conversation format used for both individual files and
        consolidated export array elements. Message timestamps preserved
        from original data when available, null otherwise.

        Args:
            metadata: Conversation metadata including id, title, timestamps
            messages: Processed and filtered message list

        Returns:
            Dictionary ready for JSON serialization
        """
        json_data = {
            "id": metadata.get("id"),
            "title": metadata.get("title"),
            "created": metadata.get("created"),
            "updated": metadata.get("updated"),
            "model": metadata.get("model"),
            "project_id": metadata.get("project_id"),
            "total_messages": metadata.get("total_messages", len(messages)),
            "code_messages": metadata.get("code_messages", 0),
            "message_types": (
                metadata.get("message_types", "").split(", ")
                if metadata.get("message_types")
                else []
            ),
            "starred": metadata.get("starred", False),
            "archived": metadata.get("archived", False),
            "chat_url": metadata.get("chat_url"),
            "messages": [],
        }

        # Mirror gpt_metadata frontmatter additions in the JSON envelope
        # so JSON consumers don't have to re-derive them. Only fields the
        # extractor actually populated are surfaced; absence stays absent.
        if self.gpt_metadata:
            for k in (
                "gizmo_id",
                "gizmo_type",
                "models_used",
                "gpt_name",
                "deep_research",
                "deep_research_version",
                "conversation_origin",
            ):
                if k in metadata:
                    json_data[k] = metadata[k]

        # Handle custom instructions - already in dict format from metadata
        if custom_instructions := metadata.get("custom_instructions"):
            json_data["custom_instructions"] = custom_instructions

        # Transform messages to JSON structure, preserving optional fields only when present to minimize output size
        for msg in messages:
            # ``timestamp`` is the per-message create_time (Unix seconds in the
            # source) rendered as ISO-8601 UTC for consistency with the
            # conversation-level ``created`` / ``updated`` style. Emitted when
            # the source carries it AND the per_turn_timestamps flag is on;
            # otherwise null, matching the legacy field shape.
            ct = msg.get("create_time")
            ts_str = (
                self._format_per_turn_ts(ct)
                if (self.per_turn_timestamps and ct is not None)
                else None
            )
            json_msg = {
                "role": msg.get("role"),
                "content": msg.get("content", ""),
                "timestamp": ts_str,
            }

            # Per-turn GPT signals — only emit when the flag is on AND the
            # signal is actually present on this message, so legacy JSON
            # consumers don't see new keys for conversations that had no
            # per-turn GPT data anyway.
            if self.gpt_metadata:
                for k in ("model_slug", "gizmo_id", "plugin_namespace"):
                    if k in msg:
                        json_msg[k] = msg[k]

            # Include auxiliary data only when present to keep JSON compact.
            # citations / web_urls / web_sources are emitted whole (no
            # cross-block dedup) so downstream indexers can access every
            # captured source. Markdown output does dedup at render for
            # human readability.
            if citations := msg.get("citations"):
                json_msg["citations"] = citations
            if web_urls := msg.get("web_urls"):
                json_msg["web_urls"] = web_urls
            if web_sources := msg.get("web_sources"):
                json_msg["web_sources"] = web_sources
            if files := msg.get("files"):
                json_msg["files"] = files

            json_data["messages"].append(json_msg)

        return json_data

    def save_json_single(
        self, conversations: List[Dict[str, Any]], output_path: Path
    ) -> Path:
        """Save all conversations to a single consolidated JSON file.

        Single JSON uses processing timestamps (not conversation timestamps)
        because consolidation happens after individual processing completes.
        Export metadata provides processing context and statistics for
        downstream analysis tools.

        Args:
            conversations: List of conversation dictionaries
            output_path: Path for the consolidated JSON file

        Returns:
            Path to the created JSON file
        """
        export_data = {
            "export_metadata": {
                "timestamp": datetime.now().strftime(TIMESTAMP_FORMAT_ISO8601),
                "total_conversations": len(conversations),
                "successful_conversations": len([c for c in conversations if c]),
                "failed_conversations": len(self.conversion_failures),
                "extractor_version": "3.1",
                "export_format": "single",
                "source_file": str(self.input_file) if self.input_file else None,
                "timestamp_sync_enabled": self.preserve_timestamps,
            },
            "conversations": conversations,
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved consolidated JSON to {output_path}")
            return output_path
        except PermissionError:
            self.logger.error(f"Permission denied writing to {output_path}")
            raise
        except Exception as e:
            log_exception(self.logger, e, f"saving JSON to {output_path}")
            raise

    def save_json_multiple(self, json_data: Dict[str, Any], output_dir: Path) -> Path:
        """Save individual conversation to its own JSON file.

        File naming follows markdown convention for consistency across formats.
        Project conversations maintain subfolder structure. Collision handling
        uses numbered suffixes matching markdown behavior.

        Args:
            json_data: Single conversation dictionary
            output_dir: Base directory for JSON files

        Returns:
            Path to the created JSON file
        """
        title = json_data.get("title") or "untitled"
        safe_title = self.sanitize_filename(title)

        # Handle project subfolder structure
        if project_id := json_data.get("project_id"):
            if project_id.startswith("g-p-"):
                project_dir = output_dir / project_id
                project_dir.mkdir(exist_ok=True)
                output_dir = project_dir

        # Handle file collisions with numbered suffixes
        file_path = output_dir / f"{safe_title}.json"
        if file_path.exists():
            counter = 2
            while True:
                file_path = output_dir / f"{safe_title} ({counter}).json"
                if not file_path.exists():
                    break
                counter += 1

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved JSON to {file_path}")
            self.json_processed += 1
            return file_path
        except PermissionError:
            self.logger.error(f"Permission denied writing to {file_path}")
            raise
        except Exception as e:
            log_exception(self.logger, e, f"saving JSON to {file_path}")
            raise

    def parse_iso_timestamp(self, timestamp_str: str) -> Optional[float]:
        """Convert ISO 8601 to Unix timestamp for filesystem operations.

        ChatGPT exports use 'Z' suffix consistently, but fallback handles
        timezone-aware strings. Returns None for pre-1970 dates which
        cause filesystem errors on some platforms. Malformed timestamps
        logged and skipped to maintain processing flow.

        Args:
            timestamp_str: ISO 8601 formatted timestamp string

        Returns:
            Unix timestamp as float, or None if parsing fails
        """
        if not timestamp_str:
            return None

        try:
            # Handle ChatGPT's specific ISO format with Z suffix
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"

            # Parse to datetime
            dt = datetime.fromisoformat(timestamp_str)

            # Convert to Unix timestamp
            timestamp = dt.timestamp()

            # Skip pre-1970 dates (negative timestamps)
            # These cause errors on Windows and older Unix systems
            if timestamp < 0:
                self.logger.debug(f"Skipping pre-1970 timestamp: {timestamp_str}")
                return None

            return timestamp

        except (ValueError, TypeError) as e:
            self.logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None

    def synchronize_file_timestamps(
        self, file_path: Path, metadata: Dict[str, Any]
    ) -> None:
        """Set file creation and modification times from conversation metadata.

        Creation time setting only supported on Windows/macOS due to
        filesystem limitations. Failures logged as warnings to maintain
        processing flow - temporal accuracy is enhancement, not requirement.
        Platform-specific implementations isolated for testability.

        Args:
            file_path: Path to file needing timestamp update
            metadata: Conversation metadata containing created/updated timestamps
        """
        if not self.preserve_timestamps:
            return

        try:
            created_ts = self.parse_iso_timestamp(metadata.get("created"))
            updated_ts = self.parse_iso_timestamp(
                metadata.get("updated", metadata.get("created"))
            )

            if not created_ts or not updated_ts:
                return  # Skip if timestamps missing or invalid

            # Set access and modification times (works on all platforms)
            os.utime(file_path, (updated_ts, updated_ts))

            # Platform-specific creation time setting
            if sys.platform == "win32":
                self._set_windows_creation_time(file_path, created_ts)
            elif sys.platform == "darwin":
                self._set_macos_creation_time(file_path, created_ts)
            # Linux: Creation time (birth time) not reliably settable
            # Most Linux filesystems don't support changing creation time

        except Exception as e:
            self.logger.warning(f"Failed to sync timestamps for {file_path}: {e}")
            self.timestamp_sync_failures += 1
            # Non-critical failure, continue processing

    def _set_windows_creation_time(self, file_path: Path, timestamp: float) -> None:
        """Windows-specific creation time setting via Win32 API.

        pywin32 optional dependency - degrades gracefully if missing.
        Handles both local and UNC paths. Requires write permissions
        even for timestamp-only changes due to Windows security model.

        Args:
            file_path: Path to file
            timestamp: Unix timestamp for creation time
        """
        try:
            import win32file
            import win32con
            import pywintypes

            # Convert Unix timestamp to Windows FILETIME
            # Windows epoch is 1601-01-01, Unix is 1970-01-01
            # Difference is 11644473600 seconds
            windows_timestamp = int((timestamp + 11644473600) * 10000000)
            filetime = pywintypes.FILETIME(windows_timestamp)

            # Open file handle
            handle = win32file.CreateFile(
                str(file_path),
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )

            # Set creation time (None for access/modified keeps them unchanged)
            win32file.SetFileTime(handle, filetime, None, None)
            win32file.CloseHandle(handle)

        except ImportError:
            self.logger.debug("pywin32 not available - skipping Windows creation time")
        except Exception as e:
            self.logger.debug(f"Failed to set Windows creation time: {e}")

    def _set_macos_creation_time(self, file_path: Path, timestamp: float) -> None:
        """macOS-specific creation time setting via xattr.

        Uses com.apple.metadata:kMDItemDateAdded extended attribute.
        Requires xattr command-line tool (standard on macOS).
        Some filesystem types may not support extended attributes.

        Args:
            file_path: Path to file
            timestamp: Unix timestamp for creation time
        """
        try:
            import subprocess
            import struct

            # Convert timestamp to macOS format (seconds since 2001-01-01)
            # Difference between Unix epoch and macOS epoch is 978307200 seconds
            macos_timestamp = timestamp - 978307200

            # Pack as binary data (double precision float)
            binary_data = struct.pack(">d", macos_timestamp)

            # Set extended attribute using xattr command
            subprocess.run(
                [
                    "xattr",
                    "-w",
                    "com.apple.metadata:kMDItemDateAdded",
                    binary_data.hex(),
                    str(file_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.debug(f"Failed to set macOS creation time: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error setting macOS creation time: {e}")

    def print_summary(self, progress: ProgressTracker) -> None:
        """Print extraction summary with format-specific statistics."""
        stats = progress.final_stats()

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("EXTRACTION COMPLETE!")
        self.logger.info("=" * 60)
        self.logger.info(f"  Total conversations: {stats['total']}")
        self.logger.info(
            f"  Successfully processed: {stats['processed'] - stats['failed']}"
        )
        self.logger.info(f"  Failed: {stats['failed']}")
        self.logger.info(f"  Success rate: {stats['success_rate']:.1f}%")

        # Format-specific statistics
        if self.output_format in ["markdown", "both"]:
            self.logger.info(f"  Markdown files created: {self.markdown_processed}")
        if self.output_format in ["json", "both"]:
            self.logger.info(f"  JSON files created: {self.json_processed}")
        if self.preserve_timestamps and self.timestamp_sync_failures > 0:
            self.logger.info(
                f"  Timestamp sync failures: {self.timestamp_sync_failures}"
            )

        self.logger.info(f"  Time elapsed: {stats['elapsed_time']:.1f}s")
        self.logger.info(f"  Processing rate: {stats['rate']:.1f} conv/s")
        self.logger.info(f"  Output directory: {self.output_dir}")
        self.logger.info("=" * 60)

    def save_schema_report(self) -> None:
        """Save schema evolution tracking report."""
        report_path = self.output_dir / "schema_evolution.log"
        report = self.schema_tracker.generate_report()

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            self.logger.debug(f"Schema report saved to {report_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save schema report: {e}")

    def log_conversion_failure(
        self, conv: Dict[str, Any], conv_id: str, title: str, error: Exception
    ) -> None:
        """Log detailed information about conversion failure for analysis."""
        import traceback

        error_str = str(error)
        error_type = type(error).__name__

        if "NoneType" in error_str:
            category = "NoneType_error"
        elif error_type == "KeyError":
            category = "KeyError"
        elif "list index out of range" in error_str:
            category = "IndexError"
        elif "expected string or bytes-like object" in error_str:
            category = "TypeError_regex"
        else:
            category = "Other"

        mapping = conv.get("mapping", {})
        structural_issues = []

        none_content_count = 0
        none_parts_count = 0
        empty_parts_count = 0
        problematic_nodes = []

        for node_id, node in mapping.items():
            if msg := node.get("message"):
                content = msg.get("content")
                author = msg.get("author", {})

                if content is None:
                    none_content_count += 1
                    problematic_nodes.append(
                        {
                            "node_id": node_id[:8],
                            "role": author.get("role"),
                            "issue": "None content",
                        }
                    )
                elif content:
                    if content.get("parts") is None:
                        none_parts_count += 1
                        problematic_nodes.append(
                            {
                                "node_id": node_id[:8],
                                "role": author.get("role"),
                                "content_type": content.get("content_type"),
                                "issue": "None parts",
                            }
                        )
                    elif content.get("parts") == []:
                        empty_parts_count += 1

        if none_content_count > 0:
            structural_issues.append(f"None content in {none_content_count} messages")
        if none_parts_count > 0:
            structural_issues.append(f"None parts in {none_parts_count} messages")
        if empty_parts_count > 0:
            structural_issues.append(f"Empty parts in {empty_parts_count} messages")

        if not conv.get("current_node"):
            structural_issues.append("Missing current_node")
        elif conv.get("current_node") not in mapping:
            structural_issues.append("Invalid current_node")

        # Extract most relevant traceback line for debugging
        tb_lines = traceback.format_exc().split("\n")
        trace_snippet = None
        for line in reversed(tb_lines):
            if "File" in line and ".py" in line:
                trace_snippet = line.strip()
                break

        failure_record = {
            "conversation_id": conv_id,
            "title": title,
            "error_message": error_str[:500],  # Truncate long errors
            "error_type": error_type,
            "category": category,
            "structural_issues": structural_issues,
            "message_count": len([n for n in mapping.values() if n.get("message")]),
            "metadata": {
                "has_current_node": bool(conv.get("current_node")),
                "has_mapping": bool(mapping),
                "project_id": conv.get("conversation_template_id"),
            },
            "problematic_nodes": problematic_nodes[:5],  # Sample
            "trace_snippet": trace_snippet,
        }

        self.conversion_failures.append(failure_record)

    def save_conversion_log(self) -> None:
        """Save detailed conversion failure log to file."""
        if not self.conversion_failures:
            return

        log_path = self.output_dir / "conversion_log.log"

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("CONVERSATION EXTRACTION FAILURE LOG\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Total Failures: {len(self.conversion_failures)}\n")
                f.write("=" * 80 + "\n\n")

                categories: Dict[str, int] = defaultdict(int)
                for fail in self.conversion_failures:
                    categories[fail["category"]] += 1

                f.write("FAILURE CATEGORIES:\n")
                for cat, count in sorted(
                    categories.items(), key=lambda x: x[1], reverse=True
                ):
                    f.write(f"  {cat}: {count}\n")
                f.write("\n")

                f.write("FAILED CONVERSATION IDs:\n")
                for fail in self.conversion_failures:
                    f.write(f"  - {fail['conversation_id']}\n")
                f.write("\n")

                f.write("=" * 80 + "\n")
                f.write("DETAILED FAILURE INFORMATION\n")
                f.write("=" * 80 + "\n\n")

                for i, fail in enumerate(self.conversion_failures, 1):
                    f.write(f"Failure #{i}\n")
                    f.write(f"ID: {fail['conversation_id']}\n")
                    f.write(f"Title: {fail['title']}\n")
                    f.write(f"Category: {fail['category']}\n")
                    f.write(f"Error Type: {fail['error_type']}\n")
                    f.write(f"Error: {fail['error_message']}\n")

                    if fail["structural_issues"]:
                        f.write(
                            f"Structural Issues: {', '.join(fail['structural_issues'])}\n"
                        )

                    if fail["problematic_nodes"]:
                        f.write(f"\nProblematic Nodes (sample):\n")
                        for node in fail["problematic_nodes"][:3]:
                            f.write(
                                f"  - Node {node['node_id']}: role={node.get('role')}, "
                            )
                            f.write(
                                f"content_type={node.get('content_type')}, issue={node.get('issue')}\n"
                            )

                    if fail["trace_snippet"]:
                        f.write(f"\nTrace: {fail['trace_snippet']}\n")

                    f.write("\n" + "=" * 80 + "\n\n")

                # JSON format enables programmatic failure analysis
                json_path = self.output_dir / "conversion_failures.json"
                try:
                    with open(json_path, "w", encoding="utf-8") as jf:
                        json.dump(self.conversion_failures, jf, indent=2, default=str)
                    f.write(f"\nJSON version saved to: conversion_failures.json\n")
                except Exception as e:
                    self.logger.warning(f"Failed to save JSON failure log: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to save conversion log: {e}")
            # Non-critical, so we don't raise
