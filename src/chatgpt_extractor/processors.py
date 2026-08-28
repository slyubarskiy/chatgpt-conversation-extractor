"""
Message processing components for content extraction and filtering.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Dict, List, Optional, Any, Tuple

from .config import WEB_URLS_KEYS
from .trackers import SchemaEvolutionTracker


class MessageProcessor:
    """Process and filter messages with enhanced content handling."""

    def __init__(self, tracker: SchemaEvolutionTracker):
        self.tracker = tracker

    def should_filter_message(self, msg: Dict[str, Any]) -> bool:
        """Determine if message should be filtered out.

        Args:
            msg: Message dictionary from conversation node

        Returns:
            True if message should be excluded from output
        """
        # Check if visually hidden
        metadata = msg.get("metadata", {})
        if metadata.get("is_visually_hidden_from_conversation"):
            return True

        author = msg.get("author", {})
        author_role = author.get("role")

        # Filter internal system messages (but keep user system messages)
        if author_role == "system" and not self.is_user_system_message(msg):
            return True

        # Filter tool messages unless they carry user-visible content:
        # DALL-E images (existing carve-out) OR a Deep Research artifact
        # at metadata.chatgpt_sdk.widget_state.report_message (the
        # rendered answer when chatgpt_sdk_suppressed_response is True
        # on the flanking assistant turns).
        if author_role == "tool":
            content = msg.get("content", {})
            if self._contains_dalle_image(content):
                pass  # kept
            else:
                from .gpt_metadata import extract_dr_report_message

                if extract_dr_report_message(msg) is None:
                    return True

        # Filter specific content types
        content = msg.get("content", {})
        content_type = content.get("content_type", "")

        if content_type in ["model_editable_context", "thoughts", "reasoning_recap"]:
            return True

        # Filter empty assistant placeholder messages
        if (
            author.get("role") == "assistant"
            and content_type == "text"
            and content.get("parts") == [""]
        ):
            return True

        return False

    def _contains_dalle_image(self, content: Dict[str, Any]) -> bool:
        """Check if content contains DALL-E generated image."""
        if content.get("content_type") == "multimodal_text":
            for part in content.get("parts", []):
                if isinstance(part, dict):
                    if part.get("content_type") == "image_asset_pointer":
                        metadata = part.get("metadata")
                        # Fixed NoneType bug: Must check metadata exists before 'in' operator
                        if metadata and (
                            "dalle" in metadata or "dalle_prompt" in metadata
                        ):
                            return True
        return False

    def is_user_system_message(self, msg: Dict[str, Any]) -> bool:
        """Check if system message should be preserved."""
        metadata = msg.get("metadata", {})
        if metadata.get("is_user_system_message"):
            return True

        content = msg.get("content", {})
        if content.get("content_type") == "user_editable_context":
            return True

        return False

    def extract_message_content(
        self, msg: Dict[str, Any], conv_id: str
    ) -> Optional[str]:
        """Extract text content from message based on content_type.

        Args:
            msg: Message dictionary containing content and metadata
            conv_id: Conversation ID for tracking

        Returns:
            Formatted message content or None if empty/filtered
        """
        content = msg.get("content", {})
        content_type = content.get("content_type", "")

        # Track content type
        if content_type:
            self.tracker.track_content_type(content_type, conv_id)

        if content_type == "text":
            # Standard text message
            parts = content.get("parts", [])
            if parts:
                return self.extract_from_parts(parts, conv_id)

        elif content_type == "code":
            # Code message with language
            text = content.get("text", "")
            lang = content.get("language", "")
            if text:
                return f"```{lang}\n{text}\n```"

        elif content_type == "execution_output":
            # Code execution output
            text = content.get("text", "")
            if text:
                return f"```output\n{text}\n```"

        elif content_type == "multimodal_text":
            # Mixed content (text, images, etc.)
            parts = content.get("parts", [])
            if parts:
                return self.extract_from_parts(parts, conv_id)

        elif content_type == "user_editable_context":  # Custom GPT instructions
            text = content.get("text", "")
            if text:
                # Strip OpenAI's wrapper text from custom instructions
                lines = text.split("\n")
                result_lines = []
                in_instructions = False

                for line in lines:
                    if "The user provided the following information" in line:
                        in_instructions = True
                    elif in_instructions:
                        result_lines.append(line)

                result = "\n".join(result_lines).strip()
                # If extraction failed, try direct wrapper removal
                if not result or len(result) > len(text) * 0.9:
                    result = text
                    for wrapper in [
                        "The user provided the following information about themselves:",
                        "The user provided the additional info about how they would like you to respond:",
                    ]:
                        result = result.replace(wrapper, "").strip()

                return result if result else None

        elif content_type == "tether_browsing_display":  # Rendered webpage
            result = content.get("result", "")
            if result:
                return result

        elif content_type == "tether_quote":  # Web search citation
            title = content.get("title", "")
            text = content.get("text", "")
            url = content.get("url", "")

            parts = []
            if title:
                parts.append(f"**{title}**")
            if text:
                parts.append(f"> {text}")
            if url:
                parts.append(f"Source: {url}")

            return "\n".join(parts) if parts else None

        elif content_type == "sonic_webpage":  # Web reader content
            text = content.get("text", "")
            url = content.get("url", "")
            if text:
                result = text
                if url:
                    result = f"[Web Content from {url}]\n{result}"
                return result

        elif content_type == "system_error":
            error_text = content.get("text", "")
            error_name = content.get("name", "Error")
            return f"[System Error: {error_name}]\n{error_text}"

        elif content_type:
            # Unknown content type - attempt generic extraction
            self.tracker.track_content_type(content_type, conv_id)

            # Try common fields
            if text := content.get("text"):
                return text
            if parts := content.get("parts"):
                return self.extract_from_parts(parts, conv_id)

        return None

    def extract_from_parts(self, parts: List[Any], conv_id: str) -> Optional[str]:
        """Extract content from parts array (handles multimodal content)."""
        # Defensive programming for None or invalid parts
        if parts is None:
            return None
        if not isinstance(parts, list):
            return None
        if not parts:  # Empty list
            return None

        result_parts = []

        for part in parts:
            if part is None:  # Defensive: Handle None parts gracefully
                continue

            if isinstance(part, str):
                # Simple text part
                if part:
                    result_parts.append(part)

            elif isinstance(part, dict):
                # Complex part (could be image, file, etc.)
                part_type = part.get("content_type", "")

                if part_type:
                    self.tracker.track_part_type(part_type, conv_id)

                if part_type == "image_asset_pointer":
                    # Image reference - defensive metadata handling
                    metadata = part.get("metadata")
                    if metadata is not None:
                        # Check for DALL-E prompt in nested structure
                        dalle_dict = metadata.get("dalle")
                        if dalle_dict is not None and isinstance(dalle_dict, dict):
                            if dalle_prompt := dalle_dict.get("prompt"):
                                result_parts.append(f"[DALL-E Image: {dalle_prompt}]")
                            else:
                                result_parts.append("[Image]")
                        elif dalle_prompt := metadata.get("dalle_prompt"):
                            result_parts.append(f"[DALL-E Image: {dalle_prompt}]")
                        else:
                            result_parts.append("[Image]")
                    else:
                        result_parts.append("[Image]")

                elif part_type == "audio_transcription":
                    # Audio transcription
                    text = part.get("text", "")
                    if text:
                        result_parts.append(f"[Audio transcription]\n{text}")

                elif part_type == "audio_asset_pointer":
                    # Audio file reference
                    result_parts.append("[Audio file]")

                elif part_type == "video_asset_pointer":
                    # Video file reference
                    result_parts.append("[Video file]")

                elif part_type == "real_time_user_audio_video_asset_pointer":
                    # Real-time voice conversation with video
                    result_parts.append("[Voice conversation with video]")

                elif part_type == "code_interpreter_output":
                    # Code interpreter output
                    output = part.get("output", "")
                    if output:
                        result_parts.append(f"```output\n{output}\n```")

                else:
                    # Unknown part type - try to extract text
                    if text := part.get("text"):
                        result_parts.append(text)

        return "\n".join(result_parts) if result_parts else None

    def extract_citations(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract citations from message metadata."""
        citations = []
        metadata = msg.get("metadata", {})

        if "citations" in metadata:
            for citation in metadata.get("citations", []):
                citation_data = {}

                # Extract citation metadata
                if citation_meta := citation.get("metadata"):
                    if title := citation_meta.get("title"):
                        citation_data["title"] = title
                    if url := citation_meta.get("url"):
                        citation_data["url"] = url
                    if type_ := citation_meta.get("type"):
                        citation_data["type"] = type_

                # Extract quoted text
                if quote := citation.get("quote"):
                    citation_data["quote"] = quote

                if citation_data:
                    citations.append(citation_data)

        return citations

    def extract_web_urls(
        self,
        msg: Dict[str, Any],
        conv_data: Optional[Dict[str, Any]] = None,
        web_urls_cfg: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Extract web URLs from message and conversation metadata.

        ``web_urls_cfg``: optional per-type level map (see ``config.py``).
        When ``None`` (backward-compatible default matching PR #17), all
        metadata sources contribute their URLs at minimal level.

        Sources checked (config-gated):
        1. Citation metadata URLs (``citations`` config key)
        2. Message metadata safe_urls (``msg_safe_urls``)
        3. search_result_groups entries + supporting_websites (``search_result_groups``)
        4. content_references + nested sources + supporting_websites (``content_references``)
        5. Conversation-level safe_urls (``conv_safe_urls``)

        Sources always checked (not config-gated):
        - Content URL / domain fields (tether_quote, sonic_webpage)
        - Content result text regex (tether_browsing_display)
        - Parts array text regex
        """
        urls, _ = self._walk_url_sources(msg, conv_data, web_urls_cfg)
        return urls

    def extract_web_sources(
        self,
        msg: Dict[str, Any],
        web_urls_cfg: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract rich URL sources (title + url + snippet + attribution).

        Returns entries only for source types configured at ``rich`` level.
        Each entry: ``{"source": "citations"|"search_result_groups"|
        "content_references", "url": str, "title"?, "snippet"?,
        "attribution"?, "domain"?, "quote"?, "type"?}``.

        When ``web_urls_cfg`` is ``None`` (backward-compatible default), no
        rich entries are extracted — this preserves PR #17 behavior.
        Callers wanting rich sources must supply a config.
        """
        _, sources = self._walk_url_sources(msg, None, web_urls_cfg)
        return sources

    def _walk_url_sources(
        self,
        msg: Dict[str, Any],
        conv_data: Optional[Dict[str, Any]],
        web_urls_cfg: Optional[Dict[str, str]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Single-pass walk over URL-carrying sources.

        Returns ``(urls, rich_sources)`` in one traversal. Called once per
        message from ``process_messages`` to avoid double-walking metadata
        on large exports.

        Level semantics per source:
        - ``off``: source contributes nothing (not even URLs).
        - ``minimal``: URLs added to the deduped set only.
        - ``rich``: URLs added AND a rich source dict appended (only for
          rich-capable types: citations, search_result_groups,
          content_references). URL-only source types (safe_urls,
          supporting_websites) silently degrade ``rich`` to ``minimal``.

        Legacy fallback: when ``web_urls_cfg`` is ``None``, every source
        runs at minimal level (URL-only, no rich entries) — matches
        PR #17 behavior byte-for-byte for existing callers.
        """
        urls: set = set()
        rich_sources: List[Dict[str, Any]] = []

        def add_url(value: Any) -> None:
            normalized = self._normalize_web_url(value)
            if normalized:
                urls.add(normalized)

        # Legacy caller (web_urls_cfg=None): all metadata sources at minimal.
        # This preserves PR #17 behavior exactly for the extract_web_urls
        # backward-compat contract.
        if web_urls_cfg is None:
            cfg = {k: "minimal" for k in WEB_URLS_KEYS}
        else:
            cfg = web_urls_cfg

        content = msg.get("content") or {}
        content_type = content.get("content_type", "")
        metadata = msg.get("metadata") or {}

        # ---- Content-type-specific paths (NOT config-gated — baseline extraction) ----
        if content_type == "tether_quote":
            if url := content.get("url"):
                add_url(url)
            if domain := content.get("domain"):
                add_url(f"https://{domain}")
        elif content_type == "tether_browsing_display":
            if result := content.get("result"):
                # Critical: use module-level 're' (local import caused 89% of failures)
                for u in re.findall(r'https?://[^\s<>"]+', str(result)):
                    add_url(u)
            if url := content.get("url"):
                add_url(url)
        elif content_type == "sonic_webpage":
            if url := content.get("url"):
                add_url(url)
            if domain := content.get("domain"):
                add_url(f"https://{domain}")

        # ---- Citations (config-gated) ----
        # At "rich" level, citations feed the existing Citations block
        # via ``extract_citations`` (called in ``process_messages``) —
        # they are NOT duplicated into ``rich_sources`` here. The Sources
        # block is exclusively for search_result_groups + content_references.
        # This walk only contributes URLs to the dedup set.
        cit_level = cfg.get("citations", "off")
        if cit_level != "off":
            for citation in metadata.get("citations", []) or []:
                if not isinstance(citation, dict):
                    continue
                cm = citation.get("metadata") or {}
                url = cm.get("url")
                if not url:
                    continue
                add_url(url)

        # ---- Regex over string parts (NOT config-gated — baseline extraction) ----
        if "parts" in content:
            parts = content.get("parts", [])
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, str):
                        for u in re.findall(r'https?://[^\s<>"]+', part):
                            add_url(u)

        # ---- Conv-level safe_urls (config-gated, URL-only) ----
        if cfg.get("conv_safe_urls", "off") != "off":
            if conv_data and isinstance(conv_data.get("safe_urls"), list):
                for u in conv_data["safe_urls"]:
                    add_url(u)

        # ---- Msg-level safe_urls (config-gated, URL-only) ----
        if cfg.get("msg_safe_urls", "off") != "off":
            for u in metadata.get("safe_urls", []) or []:
                add_url(u)

        # ---- search_result_groups (config-gated, rich-capable) ----
        srg_level = cfg.get("search_result_groups", "off")
        if srg_level != "off":
            for group in metadata.get("search_result_groups", []) or []:
                if not isinstance(group, dict):
                    continue
                domain = group.get("domain")
                for entry in group.get("entries", []) or []:
                    if not isinstance(entry, dict):
                        continue
                    url = entry.get("url")
                    if url:
                        add_url(url)
                        if srg_level == "rich":
                            entry_dict: Dict[str, Any] = {
                                "source": "search_result_groups",
                                "url": self._normalize_web_url(url) or url,
                            }
                            if t := entry.get("title"):
                                entry_dict["title"] = t
                            if s := entry.get("snippet"):
                                entry_dict["snippet"] = s
                            if a := entry.get("attribution"):
                                entry_dict["attribution"] = a
                            if domain:
                                entry_dict["domain"] = domain
                            rich_sources.append(entry_dict)
                    # supporting_websites inherit parent's level (URL-only)
                    for site in entry.get("supporting_websites", []) or []:
                        if isinstance(site, dict):
                            add_url(site.get("url"))

        # ---- content_references (config-gated, rich-capable) ----
        # Sub-types observed in real exports:
        #   webpage_extended  → top-level url + title + snippet + attribution
        #   sources_footnote  → nested sources[] with title + url + attribution
        #   grouped_webpages  → matched_text + items (usually empty)
        #   image_inline      → no URLs, skip
        cr_level = cfg.get("content_references", "off")
        if cr_level != "off":
            for ref in metadata.get("content_references", []) or []:
                if not isinstance(ref, dict):
                    continue
                # webpage_extended: top-level url + title + snippet
                if url := ref.get("url"):
                    add_url(url)
                    if cr_level == "rich":
                        entry_dict = {
                            "source": "content_references",
                            "url": self._normalize_web_url(url) or url,
                        }
                        if t := ref.get("title"):
                            entry_dict["title"] = t
                        if s := ref.get("snippet"):
                            entry_dict["snippet"] = s
                        if a := ref.get("attribution"):
                            entry_dict["attribution"] = a
                        rich_sources.append(entry_dict)
                # Ref-level safe_urls (URL-only)
                for u in ref.get("safe_urls", []) or []:
                    add_url(u)
                # sources_footnote nested sources
                for source in ref.get("sources", []) or []:
                    if not isinstance(source, dict):
                        continue
                    src_url = source.get("url")
                    if src_url:
                        add_url(src_url)
                        if cr_level == "rich":
                            entry_dict = {
                                "source": "content_references",
                                "url": self._normalize_web_url(src_url) or src_url,
                            }
                            if t := source.get("title"):
                                entry_dict["title"] = t
                            if a := source.get("attribution"):
                                entry_dict["attribution"] = a
                            rich_sources.append(entry_dict)
                    # supporting_websites nested under sources (URL-only)
                    for site in source.get("supporting_websites", []) or []:
                        if isinstance(site, dict):
                            add_url(site.get("url"))

        return sorted(urls), rich_sources

    @staticmethod
    def _normalize_web_url(value: Any) -> Optional[str]:
        """Normalize noisy ChatGPT URL variants for dedupe."""
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return None

        parts = urlsplit(value)
        query = urlencode(
            [
                (key, val)
                for key, val in parse_qsl(parts.query, keep_blank_values=True)
                if not (key.lower() == "utm_source" and val.lower() == "chatgpt.com")
            ],
            doseq=True,
        )

        fragment = parts.fragment
        if ":~:text=" in fragment:
            fragment = fragment.split(":~:text=", 1)[0]

        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))

    def extract_file_names(self, msg: Dict[str, Any]) -> List[str]:
        """Extract uploaded file names from message attachments."""
        files = []

        # Check attachments metadata - defensive handling
        metadata = msg.get("metadata")
        if metadata is not None and isinstance(metadata, dict):
            if attachments := metadata.get("attachments"):
                if isinstance(attachments, list):
                    for attachment in attachments:
                        if isinstance(attachment, dict) and attachment is not None:
                            if name := attachment.get("name"):
                                files.append(name)

        # Check content for file references
        content = msg.get("content", {})

        # Check parts for file asset pointers
        if "parts" in content:
            parts = content.get("parts", [])
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and part is not None:
                        if part.get("asset_pointer"):
                            # File upload reference - defensive metadata handling
                            metadata = part.get("metadata")
                            if metadata is not None and isinstance(metadata, dict):
                                if file_name := metadata.get("file_name"):
                                    files.append(file_name)

        return files
