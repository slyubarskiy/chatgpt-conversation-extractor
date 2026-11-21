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

    def test_extract_web_urls_from_message_safe_urls(self, processor):
        """Test URL extraction from newer message-level safe_urls."""
        msg = {
            "content": {"content_type": "text"},
            "metadata": {
                "safe_urls": [
                    "https://docs.example.com/a",
                    "https://docs.example.com/b",
                ]
            },
        }
        urls = processor.extract_web_urls(msg)
        assert "https://docs.example.com/a" in urls
        assert "https://docs.example.com/b" in urls

    def test_extract_web_urls_from_search_result_groups(self, processor):
        """Test URL extraction from newer search_result_groups metadata."""
        msg = {
            "content": {"content_type": "text"},
            "metadata": {
                "search_result_groups": [
                    {
                        "entries": [
                            {"url": "https://search.example.com/result-1"},
                            {
                                "url": "https://search.example.com/result-2",
                                "supporting_websites": [
                                    {"url": "https://search.example.com/supporting"}
                                ],
                            },
                        ]
                    }
                ]
            },
        }
        urls = processor.extract_web_urls(msg)
        assert "https://search.example.com/result-1" in urls
        assert "https://search.example.com/result-2" in urls
        assert "https://search.example.com/supporting" in urls

    def test_extract_web_urls_from_content_references(self, processor):
        """Test URL extraction from newer content_references metadata."""
        msg = {
            "content": {"content_type": "text"},
            "metadata": {
                "content_references": [
                    {
                        "safe_urls": ["https://refs.example.com/safe"],
                        "sources": [
                            {
                                "url": "https://refs.example.com/source",
                                "supporting_websites": [
                                    {"url": "https://refs.example.com/supporting"}
                                ],
                            }
                        ],
                    }
                ]
            },
        }
        urls = processor.extract_web_urls(msg)
        assert "https://refs.example.com/safe" in urls
        assert "https://refs.example.com/source" in urls
        assert "https://refs.example.com/supporting" in urls

    def test_extract_web_urls_dedupes_chatgpt_utm_source(self, processor):
        """Test dedupe across clean and ChatGPT-tracked URL variants."""
        msg = {
            "content": {"content_type": "text"},
            "metadata": {
                "citations": [
                    {
                        "metadata": {
                            "url": (
                                "https://example.com/article" "?utm_source=chatgpt.com"
                            )
                        }
                    }
                ],
                "content_references": [
                    {
                        "sources": [
                            {"url": "https://example.com/article"},
                        ],
                    }
                ],
            },
        }
        urls = processor.extract_web_urls(msg)
        assert urls.count("https://example.com/article") == 1
        assert "https://example.com/article?utm_source=chatgpt.com" not in urls

    def test_extract_web_urls_dedupes_text_fragments(self, processor):
        """Test dedupe across clean and text-fragment URL variants."""
        msg = {
            "content": {
                "content_type": "text",
                "parts": [
                    "See https://example.com/article" "#:~:text=Highlighted%20words"
                ],
            },
            "metadata": {
                "safe_urls": [
                    "https://example.com/article",
                    "https://example.com/section#intro:~:text=Highlighted%20words",
                ],
            },
        }
        urls = processor.extract_web_urls(msg)
        assert urls.count("https://example.com/article") == 1
        assert "https://example.com/article#:~:text=Highlighted%20words" not in urls
        assert "https://example.com/section#intro" in urls

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


class TestNormalizeWebUrlMalformedInput:
    """Guard against URLs that ``urllib.parse.urlsplit`` refuses to parse.

    Real-world trigger: the URL-extraction regex ``https?://[^\\s<>"]+``
    does not exclude ``]`` or ``)``, so a markdown link written as
    ``[https://example.com](https://example.com)`` is captured whole as
    ``https://example.com](https://example.com``. ``urlsplit`` raises
    ``ValueError: Invalid IPv6 URL`` on a netloc containing an unmatched
    bracket, which propagated up and aborted rendering of the *entire*
    conversation. Observed live on 3 of 41 conversations in the
    2026-08-30 sync.
    """

    @staticmethod
    def _norm(value):
        from chatgpt_extractor.processors import MessageProcessor

        return MessageProcessor._normalize_web_url(value)

    @pytest.mark.parametrize(
        "url",
        [
            # Captured from live conversations that failed to render.
            "https://Calendly.com](https://Calendly.com",
            "https://calendar.boardy.ai](https://calendar.boardy.ai",
            # Unmatched opening bracket is rejected by urlsplit too.
            "https://exa[mple.com/path",
        ],
    )
    def test_malformed_url_returns_none_instead_of_raising(self, url):
        """Unparseable URLs must be dropped, not propagated as an exception.

        Callers treat ``None`` as "not a usable URL" already — ``add_url``
        skips falsy values — so returning None loses the junk capture while
        keeping the rest of the conversation renderable.
        """
        assert self._norm(url) is None

    def test_legitimate_ipv6_url_still_parses(self):
        """The guard must not swallow well-formed bracketed IPv6 hosts."""
        assert self._norm("http://[::1]:8080/path") == "http://[::1]:8080/path"

    def test_valid_url_normalization_unaffected(self):
        """Existing utm_source stripping behaviour is unchanged."""
        assert (
            self._norm("https://example.com/a?utm_source=chatgpt.com")
            == "https://example.com/a"
        )


class TestUrlBalancedDelimiterTrimming:
    """URL captures must stop where the URL stops, not where whitespace does.

    The extraction regex ``https?://[^\\s<>"]+`` cannot express balanced
    matching, so it runs past a URL's end into surrounding markup. The common
    case is a markdown link, ``[https://x.com](https://x.com)``, which yields
    ``https://x.com](https://x.com``. A blanket "strip trailing brackets" would
    corrupt legitimate URLs that contain balanced delimiters — Wikipedia
    disambiguation paths and bracketed IPv6 hosts — so depth counting is used
    instead. See ``_trim_unbalanced_delimiters``.
    """

    @staticmethod
    def _trim(value):
        from chatgpt_extractor.processors import MessageProcessor

        return MessageProcessor._trim_unbalanced_delimiters(value)

    @staticmethod
    def _extract(text):
        from chatgpt_extractor.processors import MessageProcessor

        return MessageProcessor._extract_urls_from_text(text)

    @pytest.mark.parametrize(
        "captured,expected",
        [
            # Real junk captures observed in the vault (2026-08-30 / 08-31 syncs).
            (
                "https://meet.google.com/qrk-uvwq-hew](https://meet.google.com/qrk-uvwq-hew)",
                "https://meet.google.com/qrk-uvwq-hew",
            ),
            (
                "https://Calendly.com](https://Calendly.com",
                "https://Calendly.com",
            ),
            # Trailing ')' from a markdown link with no opener in the URL.
            ("https://example.com/page)", "https://example.com/page"),
        ],
    )
    def test_unbalanced_closer_truncates_capture(self, captured, expected):
        assert self._trim(captured) == expected

    @pytest.mark.parametrize(
        "url",
        [
            # Balanced parens are legitimate URL content — must survive intact.
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "https://example.com/a_(b)_c_(d)",
            # Bracketed IPv6 host is balanced too.
            "http://[::1]:8080/path",
            # Nothing to trim.
            "https://example.com/plain?a=1#frag",
        ],
    )
    def test_balanced_delimiters_are_preserved(self, url):
        assert self._trim(url) == url

    def test_markdown_link_yields_a_single_clean_url(self):
        """``[url](url)`` is ONE regex capture, not two, and must trim clean.

        Nothing between the ``]`` and the ``(`` is excluded by the character
        class, so the regex runs straight through the markup and returns
        ``https://x.com/a](https://x.com/a)`` as a single token. Trimming at
        the unbalanced ``]`` leaves exactly one URL.
        """
        text = "see [https://x.com/a](https://x.com/a) for details"
        assert self._extract(text) == ["https://x.com/a"]

    def test_wikipedia_link_in_markdown_keeps_its_parens(self):
        """The hard case: markdown markup AND legitimate parens together."""
        text = "[Python](https://en.wikipedia.org/wiki/Python_(programming_language))"
        assert self._extract(text) == [
            "https://en.wikipedia.org/wiki/Python_(programming_language)"
        ]

    def test_scheme_only_capture_is_dropped(self):
        """A capture trimming down to a bare scheme carries no host."""
        assert self._extract("junk https://] more") == []

    def test_plain_text_urls_unaffected(self):
        text = "a https://one.example.com and https://two.example.com/x?y=1"
        assert self._extract(text) == [
            "https://one.example.com",
            "https://two.example.com/x?y=1",
        ]


# ChatGPT's inline-marker delimiters (Unicode private-use characters):
# START type SEP arg SEP arg ... END.
_S, _SEP, _E = "", "", ""


def _marker(kind: str, *args: str) -> str:
    """Build one inline marker exactly as the source writes it."""
    return _S + kind + "".join(_SEP + a for a in args) + _E


def _card_msg(
    fallback, source="<box><text>{turn1business0.name}</text></box>", **dil_extra
):
    """An assistant message carrying an interactive card.

    ``source`` is what the message text holds (the card's template code, with
    bound placeholders); ``fallback`` is the plain-Markdown rendering the
    source ships beside it at metadata.model_dil_v2.fallbackMarkdown. Pass
    ``fallback=None`` to omit the key entirely.
    """
    dil = {"code": "x", "constants": {}, "appData": {}, **dil_extra}
    if fallback is not None:
        dil["fallbackMarkdown"] = fallback
    return {
        "id": "msg-card-1",
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": [source]},
        "metadata": {"model_dil_v2": dil},
    }


class TestInteractiveCardFallback:
    """Cards render as the source's own text version, not their template code.

    Since about 2026-10-08 replies can embed an interactive card. The message
    text then holds the card's template code, where bound values appear only
    as placeholders (``{turn1business0.name}``), so a shop name shown on the
    site is absent from the note. The same message ships a plain-Markdown
    rendering with every value filled in; these tests pin that the extractor
    uses it, and how its inline markers and escapes are cleaned.
    """

    @pytest.fixture
    def processor(self):
        return MessageProcessor(SchemaEvolutionTracker())

    def _render(self, processor, fallback, **kw):
        return processor.extract_message_content(_card_msg(fallback, **kw), "conv-1")

    # ---- which text is used ------------------------------------------------

    def test_card_renders_fallback_with_bound_values_filled(self, processor):
        out = self._render(
            processor, "| Shop | Address |\n|---|---|\n| Shop Alpha | 1 High St |"
        )
        assert "Shop Alpha" in out and "1 High St" in out
        assert "{turn1business0" not in out
        assert "<box" not in out

    def test_message_without_card_metadata_is_unchanged(self, processor):
        msg = {
            "author": {"role": "assistant"},
            "content": {"content_type": "text", "parts": ["Plain reply: a \\: b"]},
            "metadata": {},
        }
        # Escape clean-up is for the fallback only; ordinary text passes through.
        assert processor.extract_message_content(msg, "c") == "Plain reply: a \\: b"

    @pytest.mark.parametrize("fallback", [None, "", "   ", 42])
    def test_card_without_usable_fallback_keeps_source_and_warns(
        self, processor, fallback, caplog
    ):
        """Never lose the message: with no usable fallback, render what the
        message text holds (today's behaviour) and say so in the log."""
        with caplog.at_level("WARNING", logger="chatgpt_extractor.processors"):
            out = self._render(processor, fallback, source="SOURCE TEXT\n<box/>")
        assert out == "SOURCE TEXT\n<box/>"
        assert any(
            r.levelname == "WARNING"
            and "fallbackMarkdown" in r.getMessage()
            and "msg-card-1" in r.getMessage()
            for r in caplog.records
        )

    def test_is_interactive_card(self, processor):
        assert processor.is_interactive_card(_card_msg("text")) is True
        assert processor.is_interactive_card(_card_msg(None)) is False
        assert processor.is_interactive_card({"metadata": None}) is False
        assert processor.is_interactive_card({}) is False

    # ---- inline markers ----------------------------------------------------

    def test_url_marker_becomes_markdown_link(self, processor):
        fb = (
            "See " + _marker("url", "Gallery website", "https://gallery.example/") + "."
        )
        assert (
            self._render(processor, fb)
            == "See [Gallery website](https://gallery.example/)."
        )

    def test_entity_marker_becomes_its_name(self, processor):
        fb = (
            "Founded by "
            + _marker("entity", '["people","Ada Example","a short description"]')
            + "."
        )
        assert self._render(processor, fb) == "Founded by Ada Example."

    @pytest.mark.parametrize(
        "marker",
        [
            _marker("cite", "turn1search1", "turn2search3"),
            _marker("filecite", "turn0file0", "L45-L55"),
            _marker("image_group", '{"query":["a picture"],"layout":"carousel"}'),
        ],
    )
    def test_citation_and_image_markers_are_dropped(self, processor, marker):
        """Citation ids mean nothing to a reader (the sources already reach the
        Citations block); an image group is only a search phrase, no image."""
        assert (
            self._render(processor, "Open daily. " + marker + "\nNext")
            == "Open daily.\nNext"
        )
        assert self._render(processor, "Fact " + marker + ".") == "Fact."

    def test_map_widget_becomes_name_and_address_list(self, processor):
        payload = (
            '{"map_widget_v2":{"points":['
            '{"name":"Gallery One","address":"1 Road, London","id":"a"},'
            '{"name":"Gallery Two","address":"2 Lane, London","id":"b"}]}}'
        )
        out = self._render(processor, "Map:\n" + _marker("genui", payload))
        assert "- **Gallery One** — 1 Road, London" in out
        assert "- **Gallery Two** — 2 Lane, London" in out
        assert _S not in out

    def test_chart_widget_keeps_its_data_in_a_json_block(self, processor):
        payload = (
            '{"charts_widget_v2":{"content":{"chartType":"bar",'
            '"meta":{"title":"Revenue growth"},"data":[1,2]}}}'
        )
        out = self._render(processor, _marker("genui", payload))
        assert "**Chart: Revenue growth**" in out
        assert "```json" in out and '"chartType": "bar"' in out

    def test_other_widget_keeps_its_data_in_a_json_block(self, processor):
        out = self._render(
            processor, _marker("genui", '{"timeline_widget":{"items":[1]}}')
        )
        assert "```json" in out and '"timeline_widget"' in out

    @pytest.mark.parametrize(
        "marker",
        [
            _marker("genui", "{not json"),
            _marker("entity", "not-a-list"),
            _marker("brand_new_kind", "payload"),
        ],
    )
    def test_unreadable_or_unknown_marker_is_kept_and_logged(
        self, processor, marker, caplog
    ):
        """Unknown shapes are left as they came (nothing guessed, nothing lost)
        and logged, so the sync's log review surfaces them."""
        with caplog.at_level("WARNING", logger="chatgpt_extractor.processors"):
            out = self._render(processor, "a " + marker + " b")
        assert marker in out
        assert any(r.levelname == "WARNING" for r in caplog.records)

    # ---- entities and escapes ----------------------------------------------

    def test_amp_entity_is_decoded_but_table_pipe_entity_kept(self, processor):
        out = self._render(processor, "| P&amp;L | a &#124; b |")
        assert out == "| P&L | a &#124; b |"

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("**Main takeaway\\:** text", "**Main takeaway:** text"),
            ("It went unanswered\\. Then", "It went unanswered. Then"),
            (
                'Email me\\@example and 50\\% off\\; a\\=b \\"q\\"',
                'Email me@example and 50% off; a=b "q"',
            ),
            ("Wow\\! Great", "Wow! Great"),
        ],
    )
    def test_needless_escapes_are_removed(self, processor, raw, expected):
        assert self._render(processor, raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "1\\. Not a list item",  # would become an ordered list
            "  12\\. Indented number",
            "\\![not an image](x)",  # would become an image embed
            "Costs \\$5 and \\$6",  # Obsidian reads $…$ as maths
            "\\- not a bullet",
            "a \\[b\\] \\(c\\) \\*d\\* \\~e\\~ \\#f",
        ],
    )
    def test_meaningful_escapes_are_kept(self, processor, raw):
        assert self._render(processor, raw) == raw

    def test_escapes_inside_code_are_untouched(self, processor):
        """Code in the fallback is not escaped by the source and holds real
        backslashes (seen: ``regex:^report.*\\.pdf$``)."""
        fb = (
            "Use `regex:^report.*\\.pdf$` here\\:\n"
            "```python\nre.compile(r'\\.md$')  # a\\: b\n```\n"
            "Done\\."
        )
        out = self._render(processor, fb)
        assert "`regex:^report.*\\.pdf$`" in out
        assert "re.compile(r'\\.md$')  # a\\: b" in out
        assert "here:" in out and out.endswith("Done.")


class TestCardFallbackCompleteness:
    """The text version is used only when it carries all of the message's prose.

    Measured on 1,850 real card messages: 1,790 text versions hold every prose
    line of the message, but 13 stop early (one mid-sentence, at 5,732 of
    10,571 characters) and 47 miss lines elsewhere. Rendering such a text
    version would cut the reply, so the message keeps today's rendering.
    """

    @pytest.fixture
    def processor(self):
        return MessageProcessor(SchemaEvolutionTracker())

    SOURCE = (
        "## Findings\n\n"
        "The first warning is harmless and can be ignored safely.\n\n"
        "<box><text>{turn1business0.name}</text></box>\n\n"
        "## Next steps\n\n"
        "Check the event frequency across the previous seven days.\n"
    )

    def _render(self, processor, fallback):
        return processor.extract_message_content(
            _card_msg(fallback, source=self.SOURCE), "conv-1"
        )

    def test_complete_fallback_is_used(self, processor):
        fb = (
            "## Findings\n\nThe first warning is harmless and can be ignored "
            "safely\\.\n\n**Shop Alpha**\n\n## Next steps\n\n"
            "Check the event frequency across the previous seven days\\."
        )
        out = self._render(processor, fb)
        assert "Shop Alpha" in out and "<box>" not in out

    @pytest.mark.parametrize(
        "fallback",
        [
            # Cut at the end, mid-sentence, as seen in real data.
            "## Findings\n\nThe first warning is harmless and can be ignored "
            "safely.\n\n**Shop Alpha**\n\n## Next steps\n\nCheck the",
            # A line missing in the middle.
            "## Findings\n\n**Shop Alpha**\n\n## Next steps\n\n"
            "Check the event frequency across the previous seven days.",
        ],
        ids=["tail-cut", "line-missing"],
    )
    def test_incomplete_fallback_keeps_message_text_and_warns(
        self, processor, fallback, caplog
    ):
        with caplog.at_level("WARNING", logger="chatgpt_extractor.processors"):
            out = self._render(processor, fallback)
        assert out == self.SOURCE.strip("\n") or out == self.SOURCE
        assert any(
            r.levelname == "WARNING"
            and "incomplete" in r.getMessage()
            and "msg-card-1" in r.getMessage()
            for r in caplog.records
        )

    def test_is_interactive_card_false_for_incomplete_fallback(self, processor):
        """The frontmatter count must match what was actually rendered."""
        msg = _card_msg("## Findings\n\nShort.", source=self.SOURCE)
        assert processor.is_interactive_card(msg) is False

    def test_garbled_letters_in_message_do_not_block_a_clean_fallback(self, processor):
        """Some stored message texts carry U+FFFD where a letter was lost; the
        text version has the letter. Treat U+FFFD as any one or two
        characters when comparing, so the cleaner text version is used."""
        source = "Сколько раз в неделю ��ы ходите в спортзал по утрам?\n<box/>"
        fb = "Сколько раз в неделю вы ходите в спортзал по утрам?"
        out = processor.extract_message_content(_card_msg(fb, source=source), "c")
        assert out == fb


class TestCardHiddenContent:
    """Card strings the text version leaves out go into a collapsed callout.

    The text version renders a card's default view only. Strings behind a tab,
    filter, accordion, form option or follow-up button (measured: 428 text
    fragments in 60 of 323 vault notes) would otherwise vanish from the note,
    though today's rendering carries them inside the card code.
    """

    @pytest.fixture
    def processor(self):
        return MessageProcessor(SchemaEvolutionTracker())

    SOURCE = (
        "Intro paragraph.\n"
        "{@body const rows = [\n"
        '  ["Which feature should ship first in the next release?", "A credible answer."],\n'
        '  ["How should the rollout be staged across regions?", "Two examples with results."]\n'
        "]}\n"
        '<box><text size="lg">Release planning overview</text>\n'
        '<svg><path d="M35 14 V145 H326" fill="var(--viz-text)"/></svg>\n'
        '<Link url="https://example.com/page">Read more</Link>\n'
        '<pressable onClick={()=>GenUI.issueNewTurn("My drive contains mostly photos and videos")}/>\n'
        "</box>"
    )

    def _render(self, processor, fallback):
        return processor.extract_message_content(
            _card_msg(fallback, source=self.SOURCE), "conv-1"
        )

    def test_strings_missing_from_text_version_are_listed_in_a_callout(self, processor):
        fb = "Intro paragraph.\n\n**Release planning overview**\n\n- Which feature should ship first in the next release?"
        out = self._render(processor, fb)
        body, _, callout = out.partition("> [!note]-")
        assert "Release planning overview" in body
        assert callout, "expected a collapsed callout"
        assert "> - How should the rollout be staged across regions?" in out
        assert "> - Two examples with results." in out
        assert "> - My drive contains mostly photos and videos" in out
        # Already shown in the body: not repeated.
        assert callout.count("Which feature should ship") == 0

    def test_code_noise_is_not_listed(self, processor):
        fb = "Intro paragraph."
        out = self._render(processor, fb)
        # "Read more" (a link label) is visible text, so it may be listed;
        # attribute values, colours, paths and addresses never are.
        for noise in (
            "M35 14",
            "var(--viz-text)",
            "https://example.com/page",
            "lg",
        ):
            assert noise not in out.partition("> [!note]-")[2], noise

    def test_no_callout_when_nothing_is_missing(self, processor):
        fb = (
            "Intro paragraph. Release planning overview. "
            "Which feature should ship first in the next release? A credible answer. "
            "How should the rollout be staged across regions? Two examples "
            "with results. My drive contains mostly photos and videos. "
            "[Read more](https://example.com/page)"
        )
        assert "[!note]" not in self._render(processor, fb)


class TestCardStringExtraction:
    """Layouts of card text seen in real cards, each of which must be listed
    when the text version lacks it, and code that must not be."""

    @pytest.mark.parametrize(
        "line, expected",
        [
            # Prose running straight into a closing tag.
            (
                "- Provided product feedback recognised by the vendor.</WritingBlock>",
                "- Provided product feedback recognised by the vendor.",
            ),
            # Text after an opening tag, continued on the next line.
            (
                "<caption>Illustrative capability model of the product, not exact",
                "Illustrative capability model of the product, not exact",
            ),
            # Table cells.
            (
                "<table-row><table-cell>Decisiveness and ownership</table-cell></table-row>",
                "Decisiveness and ownership",
            ),
        ],
    )
    def test_text_pieces_on_card_lines_are_found(self, line, expected):
        from chatgpt_extractor.processors import _card_strings

        assert expected in _card_strings(line)

    @pytest.mark.parametrize(
        "line",
        [
            "<pressable onClick={()=>setSelected(old=>v?null:v)}>",
            '<text size="xs" color="secondary"',
            "{const x=16+i*2.05;return `${x}`}",
            '<path d="M35 14 V145 H326"/>',
        ],
    )
    def test_code_on_card_lines_is_not_found(self, line):
        from chatgpt_extractor.processors import _card_strings

        assert _card_strings(line) == []


def test_card_template_string_is_found_with_holes_marked():
    """Follow-up buttons can build their prompt as a JavaScript template string."""
    from chatgpt_extractor.processors import _card_strings

    line = (
        "<block onClick={()=>GenUI.issueNewTurn(`I mostly travel by "
        "${modes.find(m=>m.value===mode).label}. Recommend a modular setup.`)}>"
    )
    assert "I mostly travel by …. Recommend a modular setup." in _card_strings(line)


def test_blank_runs_left_by_dropped_markers_collapse_outside_code():
    """Dropping an image group leaves a run of blank lines; code keeps its own."""
    proc = MessageProcessor(SchemaEvolutionTracker())
    fb = (
        "Item one\n\n---\n\n"
        + _marker("image_group", '{"query":["x"]}')
        + "\n\n\n\nItem two\n```\na\n\n\n\nb\n```"
    )
    out = proc.extract_message_content(_card_msg(fb), "c")
    assert "---\n\nItem two" in out
    assert "a\n\n\n\nb" in out


class TestCardDetection:
    """Only messages whose text holds card code are cards.

    Measured: 758 of 1,564 on-path messages carry card metadata (and a text
    version) while their text is an ordinary Markdown reply. Those keep
    today's rendering, byte for byte, and are not counted.
    """

    @pytest.fixture
    def processor(self):
        return MessageProcessor(SchemaEvolutionTracker())

    def test_plain_reply_with_card_metadata_is_unchanged(self, processor, caplog):
        msg = _card_msg(
            "Plain reply\\: text version", source="Plain reply: the message text"
        )
        with caplog.at_level("WARNING", logger="chatgpt_extractor.processors"):
            assert (
                processor.extract_message_content(msg, "c")
                == "Plain reply: the message text"
            )
        assert processor.is_interactive_card(msg) is False
        assert not caplog.records

    def test_tags_inside_a_code_block_are_not_card_code(self, processor):
        source = "Example:\n```html\n<box>hi</box>\n```"
        msg = _card_msg("Example text version", source=source)
        assert processor.extract_message_content(msg, "c") == source

    @pytest.mark.parametrize(
        "source",
        [
            "Intro\n<box gap={2}>",
            "Price: {turn3product0.displayed_price}",
            "{@body const [a, setA] = DIL.useState(1)}",
            "{#each rows as r}",
        ],
    )
    def test_card_code_is_recognised(self, processor, source):
        assert processor.is_interactive_card(_card_msg("Text version", source=source))


def test_link_lines_match_the_text_versions_link_markers():
    """A message line that is a link must match the text version's url
    marker, or a complete text version is wrongly refused."""
    proc = MessageProcessor(SchemaEvolutionTracker())
    source = (
        "Companies to check, with their sites listed below:\n"
        "- [Kennel Example Removals](https://removals.example.com/)\n"
        "https://www.example.org/exhibitions/long-page-name\n"
        "<box/>"
    )
    fb = (
        "Companies to check, with their sites listed below:\n- "
        + _marker("url", "Kennel Example Removals", "https://removals.example.com/")
        + "\n"
        + _marker(
            "url",
            "Exhibition page",
            "https://www.example.org/exhibitions/long-page-name",
        )
    )
    out = proc.extract_message_content(_card_msg(fb, source=source), "c")
    assert "[Kennel Example Removals](https://removals.example.com/)" in out
    assert "<box/>" not in out


@pytest.mark.parametrize(
    "message_line, fallback_line",
    [
        # Same link, address written differently (sandbox file, encoding).
        (
            "1. [Claim form for the local branch office](sandbox:/mnt/data/Claim%20form.md) — to file in person",
            "1. [Claim form for the local branch office](sandbox:/mnt/data/Claim form.md) — to file in person",
        ),
        # A table separator row: alignment syntax differs, no words to compare.
        ("|---|---:|---:|---:|---:|---:|---:|", "|--------|--------|--------|"),
        # A blockquote the text version wraps over several lines.
        (
            "> Please verify the registered address of the association and report the outcome.",
            "> Please verify the registered address\n> of the association and report the outcome.",
        ),
    ],
    ids=["link-address-differs", "table-separator", "wrapped-blockquote"],
)
def test_completeness_ignores_differences_in_form(message_line, fallback_line):
    from chatgpt_extractor.processors import _missing_prose_lines

    assert _missing_prose_lines(message_line + "\n<box/>", fallback_line) == []


class TestShortCardLabels:
    """Short labels a card displays (tab names, options, badges) are content.

    The 12-character, two-word floor alone dropped them; measured on the vault
    they include "1. Context", "A: Strategy", "+1 better" and "London, UK".
    Attribute values (size="md", color="secondary") stay excluded.
    """

    @pytest.mark.parametrize(
        "line, label",
        [
            ('<tab label="x"><text>1. Context</text></tab>', "1. Context"),
            ("<badge>+1 better</badge>", "+1 better"),
            ('  ["8", "Foundations"],', "Foundations"),
            ('const where = {city: "London, UK"}', "London, UK"),
            ('{options: ["Backup A", "Backup B"]}', "Backup A"),
        ],
    )
    def test_short_labels_are_found(self, line, label):
        from chatgpt_extractor.processors import _card_strings

        assert label in _card_strings(line)

    @pytest.mark.parametrize(
        "line",
        [
            '<text size="md" color="secondary" align="center">',
            '<icon name="arrow-down"/>',
            '{style: {variant: "secondary", tone: "subtle"}}',
        ],
    )
    def test_attribute_and_style_values_are_not(self, line):
        from chatgpt_extractor.processors import _card_strings

        assert _card_strings(line) == []


def test_garbled_text_version_is_refused(caplog):
    """The source's text version can itself be garbled (U+FFFD where letters
    were lost; 8 card messages measured) while the message text is clean.
    Rendering it would put garbling into a note that has none today."""
    proc = MessageProcessor(SchemaEvolutionTracker())
    source = "<box><text>Синие поезда и красные машины</text></box>"
    fb = "Синие поезд�� и красные машины"
    msg = _card_msg(fb, source=source)
    with caplog.at_level("WARNING", logger="chatgpt_extractor.processors"):
        assert proc.extract_message_content(msg, "c") == source
    assert proc.is_interactive_card(msg) is False
    assert any("U+FFFD" in r.getMessage() for r in caplog.records)


class TestWordSequenceComparison:
    """The completeness check compares words in order, not formatted text.

    Each case is a form difference seen between a message and its text
    version on real data. The first is the 2026-11-21 false refusal: a
    sentence ending in a link right before its full stop (14 of 32 refused
    cards). Comparing formatted text needed one special rule per difference;
    comparing words makes punctuation, escapes, emphasis, entities, spacing
    and link addresses irrelevant by construction.
    """

    @pytest.mark.parametrize(
        "message_line, fallback",
        [
            (
                "For the full steps see the official [Setup guide](https://x.example/a).",
                "For the full steps see the official "
                + _marker("url", "Setup guide", "https://x.example/a")
                + "\\.",
            ),
            (
                "Read [the vendor notes](https://x.example/n), then restart the service.",
                "Read "
                + _marker("url", "the vendor notes", "https://x.example/n")
                + ", then restart the service\\.",
            ),
            (
                "Signature of the receiving clerk: ______________________",
                "Signature of the receiving clerk\\: \\_\\_\\_\\_\\_\\_",
            ),
            (
                "**Priority:** medium, unless the warning repeats every hour",
                "**Priority\\:** medium, unless the warning repeats every hour\\.",
            ),
            (
                "Costs &amp; benefits are compared in the table below",
                "Costs & benefits are compared in the table below:",
            ),
        ],
        ids=[
            "link-then-full-stop",
            "link-then-comma",
            "escaped-underscores",
            "escaped-colon-and-emphasis",
            "html-entity",
        ],
    )
    def test_form_differences_are_not_missing(self, message_line, fallback):
        from chatgpt_extractor.processors import _missing_prose_lines

        assert _missing_prose_lines(message_line + "\n<box/>", fallback) == []

    def test_tag_spanning_two_lines_is_card_code(self):
        """A card tag can open on one line and close on a later one; neither
        line is prose, so neither may be required in the text version."""
        from chatgpt_extractor.processors import _missing_prose_lines

        message = (
            "Composite parts are made in layers by hand.\n"
            '<AsyncImage query="fibreglass resin infusion vacuum bag composite\n'
            'manufacturing close up workshop photograph" aspectRatio="3:4"/>\n'
        )
        assert (
            _missing_prose_lines(message, "Composite parts are made in layers by hand.")
            == []
        )

    def test_cut_off_text_version_is_still_refused(self):
        from chatgpt_extractor.processors import _missing_prose_lines

        message = (
            "First the context section explains the purpose of the review.\n"
            "<box/>\n"
            "Finally the recommendation section lists the three next steps.\n"
        )
        fallback = "First the context section explains the purpose of the review."
        missing = _missing_prose_lines(message, fallback)
        assert [m.strip() for m in missing] == [
            "Finally the recommendation section lists the three next steps."
        ]

    def test_reordered_words_are_still_missing(self):
        """Words in a different order are different text, not a form change."""
        from chatgpt_extractor.processors import _missing_prose_lines

        message = "The supplier must confirm the delivery date in writing.\n<box/>"
        fallback = "The delivery date must confirm the supplier in writing."
        assert _missing_prose_lines(message, fallback) != []

    def test_callout_does_not_repeat_text_shown_in_another_form(self):
        """The callout's 'already shown?' test uses the same comparison, so a
        string shown with different punctuation is not listed again."""
        proc = MessageProcessor(SchemaEvolutionTracker())
        source = (
            "Intro line for the card.\n"
            '<tab label="x"><text>Release plan: phase one, then phase two</text></tab>'
        )
        fb = "Intro line for the card.\n\n**Release plan\\:** phase one \\- then phase two"
        out = proc.extract_message_content(_card_msg(fb, source=source), "c")
        assert "[!note]" not in out


@pytest.mark.parametrize(
    "msg, status",
    [
        (_card_msg("Text version"), "text"),
        (
            _card_msg(
                "Short.", source="The first section explains the purpose.\n<box/>"
            ),
            "code",
        ),
        (_card_msg("Blue tra�� text", source="<box>Blue train text</box>"), "code"),
        (_card_msg(None), "code"),
        (_card_msg("Text version", source="A plain reply with no card code"), None),
        ({"content": {"parts": ["<box/>"]}, "metadata": {}}, None),
    ],
    ids=[
        "complete",
        "cut-off",
        "garbled",
        "no-text-version",
        "plain-reply",
        "no-card-metadata",
    ],
)
def test_card_status(msg, status):
    """One decision, shared by rendering and both frontmatter counts."""
    assert MessageProcessor.card_status(msg) == status
