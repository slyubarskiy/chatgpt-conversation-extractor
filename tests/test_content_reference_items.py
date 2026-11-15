"""Synthetic regression cases for sources stored inside reference-item lists."""

import pytest

from chatgpt_extractor.config import WEB_URLS_DEFAULT, WEB_URLS_KEYS
from chatgpt_extractor.extractor import ConversationExtractorV2
from chatgpt_extractor.processors import MessageProcessor
from chatgpt_extractor.trackers import SchemaEvolutionTracker


def message(kind="grouped_webpages", field="items", items=None):
    if items is None:
        items = [
            {
                "url": "https://example.org/paper?utm_source=chatgpt.com#section:~:text=evidence",
                "title": "Synthetic paper",
                "snippet": "Searchable evidence",
                "attribution": "Example research group",
                "supporting_websites": [
                    {"url": "https://example.org/support-a"},
                    "https://example.org/support-b",
                ],
            }
        ]
    return {
        "author": {"role": "assistant"},
        "content": {
            "content_type": "text",
            "parts": ["An answer without inline links."],
        },
        "metadata": {"content_references": [{"type": kind, field: items}]},
    }


def config(level):
    return {
        key: level if key == "content_references" else "off" for key in WEB_URLS_KEYS
    }


@pytest.fixture
def processor():
    return MessageProcessor(SchemaEvolutionTracker())


@pytest.mark.parametrize("kind", ["grouped_webpages", "nav_list"])
@pytest.mark.parametrize("field", ["items", "fallback_items"])
@pytest.mark.parametrize("level", ["off", "minimal", "rich"])
def test_reference_items_respect_source_levels(processor, kind, field, level):
    msg = message(kind, field)
    urls = processor.extract_web_urls(msg, web_urls_cfg=config(level))
    sources = processor.extract_web_sources(msg, web_urls_cfg=config(level))
    if level == "off":
        assert urls == sources == []
        return
    assert urls == [
        "https://example.org/paper#section",
        "https://example.org/support-a",
        "https://example.org/support-b",
    ]
    if level == "minimal":
        assert sources == []
    else:
        assert sources == [
            {
                "source": "content_references",
                "url": "https://example.org/paper#section",
                "title": "Synthetic paper",
                "snippet": "Searchable evidence",
                "attribution": "Example research group",
            }
        ]


@pytest.mark.parametrize(
    "invalid", [None, True, 7, "not a list", {"url": "https://example.org/wrong-shape"}]
)
def test_invalid_item_containers_do_not_hide_fallback_sources(processor, invalid):
    msg = message(field="fallback_items")
    msg["metadata"]["content_references"][0]["items"] = invalid
    assert "https://example.org/paper#section" in processor.extract_web_urls(
        msg, web_urls_cfg=config("minimal")
    )


def test_invalid_items_urls_and_supporting_sites_do_not_abort_extraction(processor):
    msg = message(
        items=[
            None,
            7,
            "not an item",
            {},
            {"url": False},
            {"url": "javascript:alert(1)"},
            {"url": "https://[invalid"},
            {
                "url": "https://example.org/valid",
                "title": "Valid source",
                "supporting_websites": True,
            },
        ]
    )
    assert processor.extract_web_urls(msg, web_urls_cfg=config("rich")) == [
        "https://example.org/valid"
    ]
    assert processor.extract_web_sources(msg, web_urls_cfg=config("rich")) == [
        {
            "source": "content_references",
            "url": "https://example.org/valid",
            "title": "Valid source",
        }
    ]


def test_upstream_defaults_and_legacy_url_only_api_remain_intact(processor):
    msg = message()
    assert WEB_URLS_DEFAULT["content_references"] == "off"
    assert processor.extract_web_urls(msg, web_urls_cfg=WEB_URLS_DEFAULT) == []
    assert processor.extract_web_sources(msg, web_urls_cfg=WEB_URLS_DEFAULT) == []
    # Omitting the config retains the existing public API's all-sources,
    # URL-only behavior, including the newly supported nested source path.
    assert "https://example.org/paper#section" in processor.extract_web_urls(msg)
    assert processor.extract_web_sources(msg) == []


def test_nested_sources_reach_markdown_and_json(tmp_path, _isolated_config_env):
    msg = message()
    conv = {
        "id": "synthetic-conversation",
        "title": "Synthetic conversation",
        "mapping": {"answer": {"id": "answer", "parent": None, "message": msg}},
        "current_node": "answer",
    }
    extractor = ConversationExtractorV2(
        output_dir=str(tmp_path / "output"),
        output_format="both",
        web_urls=config("rich"),
        gpt_metadata=False,
        per_turn_timestamps=False,
    )
    metadata, messages, json_data = extractor.process_conversation(conv)
    markdown = extractor.generate_markdown(metadata, messages)
    assert (
        "[Synthetic paper](https://example.org/paper#section) — Searchable evidence"
        in markdown
    )
    assert json_data["messages"][0]["web_sources"][0] == {
        "source": "content_references",
        "url": "https://example.org/paper#section",
        "title": "Synthetic paper",
        "snippet": "Searchable evidence",
        "attribution": "Example research group",
    }
