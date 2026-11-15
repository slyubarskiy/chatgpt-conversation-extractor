"""
Message processing components for content extraction and filtering.
"""

import html
import json
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Dict, List, Optional, Any, Tuple

from .config import WEB_URLS_KEYS
from .trackers import SchemaEvolutionTracker

logger = logging.getLogger(__name__)

# Broad first-pass URL match over free text. It deliberately cannot express
# balanced delimiters -- regex does not do that -- so every capture is passed
# through _trim_unbalanced_delimiters before use.
URL_IN_TEXT_RE = re.compile(r'https?://[^\s<>"]+')

# Closing delimiter -> its opener. A closer with no matching opener earlier in
# the URL means the regex ran past the URL's end into surrounding markup.
_URL_CLOSERS = {")": "(", "]": "["}

# ---- Interactive cards (metadata.model_dil_v2, seen since ~2026-10-08) ----
#
# A card reply's message text is template code whose bound values are bare
# placeholders, so the note would lack names, prices and addresses the site
# shows. The same message carries ``fallbackMarkdown``: the source's own plain
# rendering with every value filled in. That text still uses ChatGPT's inline
# markers and escapes more than Markdown needs, so it is cleaned before use.

# Inline marker: U+E200 kind (U+E202 arg)* U+E201. Non-greedy and DOTALL
# because widget payloads are JSON that can span lines; markers never nest
# (measured: 0 unbalanced START/END pairs across 1,859 card messages).
_MARKER_RE = re.compile("\ue200([a-z_]+)((?:\ue202.*?)?)\ue201", re.S)
_MARKER_SEP = "\ue202"

# Markers a reader gets nothing from. Citation ids (``turn1search1``) only
# resolve against search results the text version does not carry; the
# previous rendering showed them as equally bare ids in <Cite> tags. Any
# sources block a note has comes from message metadata and is unaffected
# (verified: identical before and after on 260 card notes, though 30 of the
# 79 citing notes have none either way). An image group is a search phrase
# for pictures, not a picture. Leading spaces are part of the match so
# "text. <marker>" does not leave "text. ".
_DROPPED_MARKER_KINDS = {"cite", "filecite", "image_group"}
_DROPPED_MARKER_RE = re.compile(
    "[ \t]*(?:" + "|".join(sorted(_DROPPED_MARKER_KINDS)) + ")" "(?:.*?)?",
    re.S,
)

# Fenced blocks and inline code spans. The fallback leaves code unescaped and
# code holds real backslashes (seen: ``regex:^report.*\.pdf$``), so escape
# clean-up must skip these spans.
_CODE_SPAN_RE = re.compile(r"(```|~~~)[^\n]*\n.*?\n\1|`[^`\n]+`", re.S)

# Backslash escapes that Markdown never needs for these characters. Others
# are kept on purpose: ``\$`` (Obsidian reads $…$ as maths), ``\-``, ``\*``,
# ``\#``, ``\~``, brackets and parens can all change how a line renders.
_NEEDLESS_ESCAPE_RE = re.compile(r'\\([:@%;="])')
# ``\.`` is needless except after a line-leading number ("1\. x" would turn
# into an ordered list) and ``\!`` except before ``[`` (would become an
# image embed).
_NEEDLESS_DOT_RE = re.compile(r"(?<!\\)\\\.")
_LIST_NUMBER_DOT_RE = re.compile(r"(?m)^(\s*\d+)\\\.")
_NEEDLESS_BANG_RE = re.compile(r"\\!(?!\[)")

# ---- Completeness check: is the text version the whole message? ----------
#
# The text version is not always whole. On 1,850 real card messages, 1,790
# carried every prose line of the message, 13 stopped early (one
# mid-sentence at 5,732 of 10,571 characters) and 47 lacked lines elsewhere.
# So it is used only when every prose line of the message text -- lines that
# are not card code -- appears in it; otherwise the message keeps today's
# rendering. Comparison is on a normalised form that ignores what the two
# renderings legitimately do differently (escapes, entities, emphasis
# markers, inline markers, spacing, case).

# A line holding a tag or a {template expression} is card code, and a line
# opening with data punctuation is a row of a card's data array; neither is
# expected verbatim in the text version.
_CARD_CODE_LINE_RE = re.compile(r"<[^>\n]*>|\{[^{}\n]*\}")
_DATA_ROW_RE = re.compile(r'^\s*[\[\]{}(),"]')
# Lines shorter than this (after normalising) are not checked: numbering and
# short labels are where the two renderings differ in form, and the 25-char
# floor is what the 1,790-of-1,850 measurement above used.
_MIN_CHECKED_LINE = 25


# Card code proper. Card metadata alone is not enough: 758 of 1,564 measured
# messages carry it while their text is an ordinary Markdown reply, and those
# must keep today's rendering byte for byte. Component tags are capitalised
# (<Entity>, <AsyncImage>) and may sit mid-line; layout tags (<box>, <row>)
# open a line. Fenced code is removed first, since a reply can show HTML in
# a code block without being a card.
_FENCE_RE = re.compile(r"(```|~~~)[^\n]*\n.*?\n\1", re.S)
_CARD_CODE_RE = re.compile(
    r"(?m)^\s*<[a-z][\w-]*[\s/>]|<[A-Z][A-Za-z0-9]*[\s/>]"
    r"|\{turn\d+|\{@body|\{#each|\{/each|\{:else"
)
_MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\n]*)\)")
_BARE_ADDRESS_RE = re.compile(r"(?:https?|sandbox):\S+")
_QUOTE_MARK_RE = re.compile(r"(?m)^[ \t]*>[ \t]?")


def _has_card_code(message_text: str) -> bool:
    """Whether a message's text holds card code outside fenced code blocks."""
    return bool(_CARD_CODE_RE.search(_FENCE_RE.sub("", message_text)))


def _marker_words(match: "re.Match[str]") -> str:
    """The words a marker shows, for comparison only (never rendered).

    Links keep their label, entities their name; everything else counts as
    blank. Stripping links outright made a message line that is a link look
    missing, and complete text versions were refused. Addresses are left out
    because the two renderings write the same one differently (encoding,
    sandbox file paths).
    """
    kind = match.group(1)
    args = (match.group(2) or "").split(_MARKER_SEP)[1:]
    if kind == "url" and len(args) == 2:
        return f" {args[0]} "
    if kind == "entity" and len(args) == 1:
        try:
            value = json.loads(args[0])
        except ValueError:
            return " "
        if isinstance(value, list) and len(value) >= 2 and isinstance(value[1], str):
            return f" {value[1]} "
    return " "


def _comparable(text: str) -> str:
    """Normalise text so the message and its text version can be compared.

    Ignores what the two renderings legitimately write differently: escapes,
    entities, emphasis, link addresses, blockquote markers (the text version
    may wrap one quote over several "> " lines), spacing and case.
    """
    text = html.unescape(text)
    text = _MARKER_RE.sub(_marker_words, text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _BARE_ADDRESS_RE.sub(" ", text)
    text = _QUOTE_MARK_RE.sub("", text)
    text = re.sub(r"\\([^\w\s])", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip().lower()


def _missing_prose_lines(message_text: str, fallback: str) -> List[str]:
    """Prose lines of the message that its text version does not contain.

    U+FFFD in the message (a letter lost before it was stored) matches any
    one or two characters, so a text version that has the letter still
    counts as complete -- and is then the better rendering.
    """
    haystack = _comparable(fallback)
    missing: List[str] = []
    for line in message_text.splitlines():
        if _CARD_CODE_LINE_RE.search(line) or _DATA_ROW_RE.match(line):
            continue
        core = _comparable(line).strip(" |#->*")
        # No letters: a table separator or rule, whose syntax differs freely.
        if len(core) < _MIN_CHECKED_LINE or not re.search(r"[^\W\d_]", core):
            continue
        if "\ufffd" in core:
            pattern = ".{1,2}".join(re.escape(p) for p in re.split("\ufffd+", core))
            if re.search(pattern, haystack):
                continue
        elif core in haystack:
            continue
        missing.append(line)
    return missing


# ---- Card content the text version leaves out ----------------------------
#
# The text version renders a card's default view only: strings behind a tab,
# filter, accordion, form option or follow-up button are dropped (measured:
# 428 fragments in 60 of 323 vault notes). They sit in the card code as
# string literals or tag text, so they are collected from there and listed
# in a collapsed callout under the text version.
_STRING_LITERAL_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
# Follow-up buttons can build their prompt as a JavaScript template string;
# each ${...} hole depends on what the reader picked, so it is shown as "…".
_TEMPLATE_STRING_RE = re.compile(r"`((?:[^`\\\n]|\\.)*)`")
_TEMPLATE_HOLE_RE = re.compile(r"\$\{[^{}]*\}")
# Text pieces are what remains of a card line between tags and {expressions}.
# Splitting rather than matching ">text<" also catches prose that runs into a
# closing tag ("…the result.</WritingBlock>") and text after an opening tag
# that continues on the next line ("<caption>A model of …"), both seen.
_TAG_OR_EXPR_RE = re.compile(r"<[^>]*>|\{[^{}]*\}")
# A piece holding these is code left by a tag or expression spanning lines.
_CODE_CHARS_RE = re.compile(r'[<>{}=;`"]')
# Readable text has at least two words of three or more letters; this keeps
# out ids, sizes, colours, SVG path data and the like.
_READABLE_RE = re.compile(r"[^\W\d_]{3,}\W+(?:.*\W)?[^\W\d_]{3,}", re.S)
_MIN_CARD_STRING = 12
_LETTERS_RE = re.compile(r"[^\W\d_]{3,}")
# Citation ids (turn0file0, turn841160search1) are references, not text.
_CITATION_ID_RE = re.compile(r"turn\d+[a-z_]+\d+")
_HIDDEN_CONTENT_CALLOUT = (
    "> [!note]- More card content (other tabs, options and buttons)"
)


def _keep_card_string(s: str, kind: str) -> bool:
    """Whether one candidate string from card code is reader-visible content.

    ``kind`` is where it came from, which decides how strict to be:
    - "attr": a quoted value right after ``=`` -- mostly layout (size="md",
      color="secondary"); kept only when long and wordy (a title or alt text).
    - "data": a quoted value in the card's data -- kept when wordy, or when it
      looks like a label: three or more letters plus a space, a digit or a
      capital ("Backup A", "London, UK", "Foundations"). Bare lowercase words
      there are style values ("secondary", "arrow-down").
    - "text": text between tags, which the card displays -- kept with three
      or more letters ("1. Context", "+1 better").
    """
    if (
        s.startswith(("http://", "https://"))
        or "var(--" in s
        or _CITATION_ID_RE.fullmatch(s)
        or not _LETTERS_RE.search(s)
    ):
        return False
    wordy = len(s) >= _MIN_CARD_STRING and bool(_READABLE_RE.search(s))
    if kind == "attr":
        return wordy
    if kind == "data":
        return wordy or bool(re.search(r"[\s\d]", s)) or s[0].isupper()
    return True


def _card_strings(message_text: str) -> List[str]:
    """Readable strings in a message's card code, in order, de-duplicated."""
    seen: set = set()
    found: List[str] = []
    for line in message_text.splitlines():
        if not (_CARD_CODE_LINE_RE.search(line) or _DATA_ROW_RE.match(line)):
            continue  # prose lines are covered by the completeness check
        candidates = []
        for m in _STRING_LITERAL_RE.finditer(line):
            kind = "attr" if line[: m.start()].rstrip().endswith("=") else "data"
            try:
                # Card code is JavaScript-like; its string escapes match JSON's
                # for everything seen in practice (\" \n \u2014).
                candidates.append((json.loads('"' + m.group(1) + '"'), kind))
            except ValueError:
                candidates.append((m.group(1), kind))
        candidates.extend(
            (_TEMPLATE_HOLE_RE.sub("…", m.group(1)), "data")
            for m in _TEMPLATE_STRING_RE.finditer(line)
        )
        # Only lines that hold tags or expressions have text pieces; a data
        # row ('["a", "b"],') is covered by the string literals above.
        pieces = _TAG_OR_EXPR_RE.split(line)
        if len(pieces) > 1:
            candidates.extend(
                (p, "text") for p in pieces if not _CODE_CHARS_RE.search(p)
            )
        for s, kind in candidates:
            s = " ".join(s.split())
            if s in seen or not _keep_card_string(s, kind):
                continue
            seen.add(s)
            found.append(s)
    return found


def _message_text(msg: Dict[str, Any]) -> str:
    """The string parts of a message, joined as extract_from_parts joins them."""
    parts = (msg.get("content") or {}).get("parts") or []
    return "\n".join(p for p in parts if isinstance(p, str))


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

        # A card's text version replaces its template code (see the module
        # notes on interactive cards). When the card has no usable text
        # version, fall through to today's rendering so nothing is lost.
        fallback = self._card_fallback(msg, conv_id)
        if fallback is not None:
            return self.render_card_fallback(fallback, conv_id, _message_text(msg))

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

    @staticmethod
    def _raw_fallback(msg: Dict[str, Any]) -> Optional[str]:
        """The card's text version if present and non-blank, else None."""
        dil = (msg.get("metadata") or {}).get("model_dil_v2")
        if not isinstance(dil, dict):
            return None
        fallback = dil.get("fallbackMarkdown")
        if isinstance(fallback, str) and fallback.strip():
            return fallback
        return None

    @classmethod
    def is_interactive_card(cls, msg: Dict[str, Any]) -> bool:
        """Whether a message will render from a card's text version.

        True exactly when ``extract_message_content`` uses it: the message
        holds card code, and the text version is present, non-blank and
        complete. Callers count these per conversation for the
        ``interactive_cards`` frontmatter field, so the count matches what
        the note shows.
        """
        text = _message_text(msg)
        fallback = cls._raw_fallback(msg)
        return (
            fallback is not None
            and _has_card_code(text)
            and not _missing_prose_lines(text, fallback)
        )

    def _card_fallback(self, msg: Dict[str, Any], conv_id: str) -> Optional[str]:
        """Return a card's raw text version, or None to render as before.

        Both refusals log at WARNING because the note then shows template
        code, with placeholders where values belong:
        - no usable text version (absent, blank, not a string): not seen in
          1,859 card messages, so it would mean the source changed;
        - an incomplete one: about 3% of card messages (see the module notes);
          rendering it would cut the reply short.
        """
        dil = (msg.get("metadata") or {}).get("model_dil_v2")
        if not isinstance(dil, dict) or not _has_card_code(_message_text(msg)):
            # No card code: an ordinary reply that happens to carry card
            # metadata. Rendered as before, silently -- that is the normal case.
            return None
        fallback = self._raw_fallback(msg)
        if fallback is None:
            logger.warning(
                "Interactive card without a usable fallbackMarkdown: conv=%s "
                "msg=%s type=%s; rendering the card's template code instead",
                conv_id,
                msg.get("id"),
                type(dil.get("fallbackMarkdown")).__name__,
            )
            return None
        missing = _missing_prose_lines(_message_text(msg), fallback)
        if missing:
            logger.warning(
                "Interactive card text version is incomplete (%d prose line(s) "
                "of the message absent, first: %r): conv=%s msg=%s; rendering "
                "the card's template code instead",
                len(missing),
                missing[0][:80],
                conv_id,
                msg.get("id"),
            )
            return None
        return fallback

    def render_card_fallback(
        self, text: str, conv_id: str, message_text: str = ""
    ) -> str:
        """Clean a card's text version for the note.

        Steps, in this order:
        1. Resolve inline markers (links, entity names, widget data) and drop
           the ones a reader gets nothing from. Done first so marker payloads
           (JSON) are never touched by the escape clean-up.
        2. Decode ``&amp;``. ``&#124;`` is kept: it is a literal pipe inside a
           table cell, and decoding it would split the cell.
        3. Remove backslash escapes Markdown does not need, outside code only,
           so exact-text search finds "signals:" rather than "signals\\:".
        4. List, in a collapsed callout, readable strings of the card code
           (``message_text``) that the result lacks -- content behind tabs,
           filters, accordions, options and buttons.
        """
        # Dropped markers go first, together with the spaces just before them,
        # so "Fact <cite>." becomes "Fact." rather than "Fact .". Trimming
        # only there keeps spacing elsewhere (code included) untouched.
        text = _DROPPED_MARKER_RE.sub("", text)
        text = _MARKER_RE.sub(lambda m: self._resolve_marker(m, conv_id), text)
        text = text.replace("&amp;", "&")
        text = self._unescape_outside_code(text)

        shown = _comparable(text)
        hidden = [s for s in _card_strings(message_text) if _comparable(s) not in shown]
        if hidden:
            text = (
                text.rstrip("\n")
                + "\n\n"
                + _HIDDEN_CONTENT_CALLOUT
                + "\n"
                + "\n".join(f"> - {s}" for s in hidden)
            )
        return text

    def _resolve_marker(self, match: "re.Match[str]", conv_id: str) -> str:
        """Render one inline marker; keep it verbatim when its shape is unknown."""
        kind = match.group(1)
        args = match.group(2).split(_MARKER_SEP)[1:]
        try:
            if kind == "url" and len(args) == 2 and args[1].startswith("http"):
                return f"[{args[0]}]({args[1]})"
            if kind == "entity" and len(args) == 1:
                # ["type", "display name", optional description, ...]
                value = json.loads(args[0])
                if (
                    isinstance(value, list)
                    and len(value) >= 2
                    and isinstance(value[1], str)
                ):
                    return value[1]
            if kind == "genui" and len(args) == 1:
                return self._render_widget(json.loads(args[0]))
        except (ValueError, TypeError, AttributeError, KeyError):
            # Fall through to the keep-and-log path below: a payload that
            # does not parse is a shape this code was not built for.
            pass
        logger.warning(
            "Unrecognised inline marker kept verbatim: conv=%s kind=%s args=%d",
            conv_id,
            kind,
            len(args),
        )
        return match.group(0)

    @staticmethod
    def _render_widget(payload: Dict[str, Any]) -> str:
        """Render a ``genui`` widget payload as readable Markdown.

        Maps become a name/address list (the reader wants the places, not
        coordinates). Charts and any other widget keep their full data in a
        fenced JSON block: lossless, and Obsidian shows it as code rather
        than trying to render it.
        """
        if not isinstance(payload, dict) or len(payload) != 1:
            raise ValueError("widget payload must be a one-key object")
        ((name, body),) = payload.items()
        if name == "map_widget_v2":
            lines = []
            for point in body["points"]:
                label = point.get("name") or point.get("address") or "?"
                address = point.get("address")
                lines.append(
                    f"- **{label}** — {address}" if address else f"- **{label}**"
                )
            return "\n".join(lines)
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        if name == "charts_widget_v2":
            title = (body.get("content") or {}).get("meta", {}).get("title")
            heading = f"**Chart: {title}**\n" if title else "**Chart**\n"
            return f"{heading}```json\n{data}\n```"
        return f"```json\n{data}\n```"

    @staticmethod
    def _unescape_outside_code(text: str) -> str:
        """Remove needless escapes and blank-line runs, except in code spans."""

        def clean(chunk: str) -> str:
            # Shield "1\." at line start with a private-use sentinel, unescape
            # the remaining "\.", then restore the shielded list numbers.
            chunk = _LIST_NUMBER_DOT_RE.sub(lambda m: m.group(1) + "", chunk)
            chunk = _NEEDLESS_DOT_RE.sub(".", chunk)
            chunk = chunk.replace("", "\\.")
            chunk = _NEEDLESS_BANG_RE.sub("!", chunk)
            chunk = _NEEDLESS_ESCAPE_RE.sub(r"\1", chunk)
            # A dropped image group leaves its line empty; collapse the run
            # (only here, outside code, where blank runs carry no meaning).
            return re.sub(r"\n[ \t]*(?:\n[ \t]*){2,}", "\n\n", chunk)

        out, pos = [], 0
        for m in _CODE_SPAN_RE.finditer(text):
            out.append(clean(text[pos : m.start()]))
            out.append(m.group(0))
            pos = m.end()
        out.append(clean(text[pos:]))
        return "".join(out)

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
                for u in self._extract_urls_from_text(str(result)):
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
                        for u in self._extract_urls_from_text(part):
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
    def _trim_unbalanced_delimiters(url: str) -> str:
        """Truncate a captured URL at its first unbalanced closing delimiter.

        ``URL_IN_TEXT_RE`` stops only at whitespace, ``<``, ``>`` and ``"``, so
        a markdown link ``[https://x.com](https://x.com)`` is captured whole as
        ``https://x.com](https://x.com``. Unconditionally stripping trailing
        brackets would be wrong: plenty of real URLs contain *balanced*
        delimiters, notably Wikipedia disambiguation paths
        (``/wiki/Python_(programming_language)``) and bracketed IPv6 hosts
        (``http://[::1]:8080/``). Counting depth distinguishes the two -- a
        closer that has no opener earlier in the same URL was never part of it.

        Args:
            url: A raw capture from ``URL_IN_TEXT_RE``.

        Returns:
            The capture truncated at the first unbalanced closer, or unchanged
            when every delimiter balances.
        """
        depth = {"(": 0, "[": 0}
        for index, char in enumerate(url):
            if char in depth:
                depth[char] += 1
            elif char in _URL_CLOSERS:
                opener = _URL_CLOSERS[char]
                if depth[opener] == 0:
                    return url[:index]
                depth[opener] -= 1
        return url

    @classmethod
    def _extract_urls_from_text(cls, text: str) -> List[str]:
        """Extract URLs from free text, stopping each at surrounding markup.

        Duplicates are intentionally preserved -- a markdown link contains its
        URL twice, and the caller collects into a set -- so this stays a pure
        "what did the text contain" helper.
        """
        urls: List[str] = []
        for raw in URL_IN_TEXT_RE.findall(text):
            trimmed = cls._trim_unbalanced_delimiters(raw)
            # A capture that trims back to just the scheme had no host at all
            # (e.g. the text contained a bare "https://]").
            if trimmed.rstrip("/") in ("http:", "https:"):
                continue
            urls.append(trimmed)
        return urls

    @staticmethod
    def _normalize_web_url(value: Any) -> Optional[str]:
        """Normalize noisy ChatGPT URL variants for dedupe."""
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return None

        # The URL-extraction regex (https?://[^\s<>"]+) does not exclude ']'
        # or ')', so a markdown link written as [https://x.com](https://x.com)
        # is captured whole as 'https://x.com](https://x.com'. urlsplit raises
        # ValueError on a netloc holding an unmatched bracket, and that used to
        # propagate all the way up and abort rendering of the ENTIRE
        # conversation over one junk capture. Treat unparseable input the way
        # every caller already treats None -- as "not a usable URL" -- so the
        # bad capture is dropped and the conversation still renders.
        try:
            parts = urlsplit(value)
            query = urlencode(
                [
                    (key, val)
                    for key, val in parse_qsl(parts.query, keep_blank_values=True)
                    if not (
                        key.lower() == "utm_source" and val.lower() == "chatgpt.com"
                    )
                ],
                doseq=True,
            )

            fragment = parts.fragment
            if ":~:text=" in fragment:
                fragment = fragment.split(":~:text=", 1)[0]

            return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))
        except ValueError:
            logger.debug("Dropping unparseable URL: %r", value[:200])
            return None

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
