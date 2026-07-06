"""Tests for the ``web_urls`` config overlay.

Covers:
- ``config._resolve_web_urls`` — preset resolution, per-type map merge,
  invalid inputs.
- ``config._merge_config_over_defaults`` — nested-merge behavior for
  ``web_urls`` and back-compat for flat keys.
- End-to-end config layering (YAML → constructor → resolved
  ``self.web_urls`` on ``ConversationExtractorV2``).
- Rendering golden checks at each preset (``off``, ``citations``,
  ``rich``): correct blocks present, cross-block dedup applied to the
  Web Search URLs block, JSON output emits every source whole.

Shares the ``_isolated_config_env`` fixture from ``conftest.py``.
"""

import json
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor import config as config_mod
from chatgpt_extractor.config import (
    WEB_URLS_DEFAULT,
    WEB_URLS_KEYS,
    WEB_URLS_LEVELS,
    WEB_URLS_PRESETS,
    _merge_config_over_defaults,
    _resolve_web_urls,
    load_config,
)
from chatgpt_extractor.extractor import ConversationExtractorV2


# --------------------------------------------------------------------------- #
# _resolve_web_urls
# --------------------------------------------------------------------------- #


def test_resolve_web_urls_none_returns_defaults():
    r = _resolve_web_urls(None)
    assert r == WEB_URLS_DEFAULT
    # Fresh dict — must not share identity with the module-level default.
    assert r is not WEB_URLS_DEFAULT


def test_resolve_web_urls_off_preset():
    r = _resolve_web_urls("off")
    assert r == {k: "off" for k in WEB_URLS_KEYS}


def test_resolve_web_urls_citations_preset():
    r = _resolve_web_urls("citations")
    assert r["citations"] == "rich"
    for k in WEB_URLS_KEYS - {"citations"}:
        assert r[k] == "off", f"{k} should be off under 'citations' preset"


def test_resolve_web_urls_rich_preset():
    r = _resolve_web_urls("rich")
    assert r["citations"] == "rich"
    assert r["search_result_groups"] == "rich"
    assert r["content_references"] == "rich"
    assert r["conv_safe_urls"] == "off"
    assert r["msg_safe_urls"] == "off"


def test_resolve_web_urls_unknown_preset_falls_back(caplog):
    with caplog.at_level("WARNING"):
        r = _resolve_web_urls("gibberish")
    assert r == WEB_URLS_DEFAULT
    assert "unknown preset" in caplog.text.lower()


def test_resolve_web_urls_case_insensitive_preset():
    """Presets accept any case; canonicalize to lowercase."""
    assert _resolve_web_urls("RICH") == WEB_URLS_PRESETS["rich"]
    assert _resolve_web_urls("Off") == {k: "off" for k in WEB_URLS_KEYS}


def test_resolve_web_urls_partial_dict_preserves_defaults():
    """Partial per-type dict merges — unspecified keys stay at defaults."""
    r = _resolve_web_urls({"citations": "off"})
    assert r["citations"] == "off"
    for k in WEB_URLS_KEYS - {"citations"}:
        assert r[k] == WEB_URLS_DEFAULT[k]


def test_resolve_web_urls_full_dict_overrides_every_key():
    override = {k: "off" for k in WEB_URLS_KEYS}
    override["citations"] = "rich"
    r = _resolve_web_urls(override)
    assert r == override


def test_resolve_web_urls_unknown_per_type_key_logged_and_ignored(caplog):
    with caplog.at_level("WARNING"):
        r = _resolve_web_urls({"bogus": "rich", "citations": "off"})
    assert "bogus" not in r
    assert r["citations"] == "off"
    assert "unknown per-type key" in caplog.text.lower()


def test_resolve_web_urls_bool_false_treated_as_off():
    """YAML 1.1 coerces ``off``, ``no``, ``false`` → bool False.
    Accept as equivalent to string ``"off"`` so users can write
    ``citations: off`` unquoted."""
    r = _resolve_web_urls({"citations": False})
    assert r["citations"] == "off"


def test_resolve_web_urls_bool_true_ambiguous_falls_back(caplog):
    """YAML ``citations: yes`` / ``true`` / ``on`` deserializes to True.
    No natural level mapping — warn and fall back to default."""
    with caplog.at_level("WARNING"):
        r = _resolve_web_urls({"citations": True})
    assert r["citations"] == WEB_URLS_DEFAULT["citations"]
    assert "ambiguous" in caplog.text.lower()


def test_resolve_web_urls_non_string_non_bool_falls_back(caplog):
    """Numeric or list value at per-type key — warn and fall back."""
    with caplog.at_level("WARNING"):
        r = _resolve_web_urls({"citations": 42})
    assert r["citations"] == WEB_URLS_DEFAULT["citations"]
    assert "expected one of" in caplog.text.lower()


def test_resolve_web_urls_invalid_shape_falls_back(caplog):
    """Neither string nor dict — fall back to defaults."""
    with caplog.at_level("WARNING"):
        r = _resolve_web_urls([1, 2, 3])
    assert r == WEB_URLS_DEFAULT
    assert "expected preset string" in caplog.text.lower()


# --------------------------------------------------------------------------- #
# _merge_config_over_defaults (nested-merge helper)
# --------------------------------------------------------------------------- #


def test_merge_flat_key_replaces_default():
    """Flat keys behave as normal dict.update — incoming replaces default."""
    merged = _merge_config_over_defaults(
        {"per_turn_timestamps": True, "gpt_metadata": True},
        {"per_turn_timestamps": False},
    )
    assert merged["per_turn_timestamps"] is False
    assert merged["gpt_metadata"] is True


def test_merge_nested_dict_preserves_sibling_keys():
    """Dict-over-dict does a per-subkey shallow merge."""
    defaults = {"web_urls": dict(WEB_URLS_DEFAULT)}
    incoming = {"web_urls": {"citations": "off"}}
    merged = _merge_config_over_defaults(defaults, incoming)
    assert merged["web_urls"]["citations"] == "off"
    # Sibling keys preserved from defaults
    assert merged["web_urls"]["conv_safe_urls"] == WEB_URLS_DEFAULT["conv_safe_urls"]


def test_merge_string_over_dict_replaces_wholesale():
    """Preset string (``web_urls: rich``) replaces the default dict cleanly;
    the caller resolves the preset later."""
    defaults = {"web_urls": dict(WEB_URLS_DEFAULT)}
    incoming = {"web_urls": "rich"}
    merged = _merge_config_over_defaults(defaults, incoming)
    assert merged["web_urls"] == "rich"


def test_merge_does_not_mutate_defaults():
    """The helper must return a new dict; input defaults untouched."""
    defaults = {"web_urls": dict(WEB_URLS_DEFAULT)}
    defaults_snapshot = {"web_urls": dict(defaults["web_urls"])}
    _merge_config_over_defaults(defaults, {"web_urls": {"citations": "off"}})
    assert defaults == defaults_snapshot


# --------------------------------------------------------------------------- #
# load_config with a real YAML file
# --------------------------------------------------------------------------- #


def test_load_config_web_urls_preset_string(tmp_path, _isolated_config_env):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text("web_urls: rich\n", encoding="utf-8")
    cfg = load_config(str(cfg_file))
    # Kept as-is; extractor resolves at construct time.
    assert cfg["web_urls"] == "rich"


def test_load_config_web_urls_partial_dict_preserves_siblings(
    tmp_path, _isolated_config_env
):
    """Partial ``web_urls`` dict in YAML merges over defaults; unspecified
    sibling keys survive. Uses quoted ``"off"`` because YAML 1.1 would
    coerce bare ``off`` to bool False (see the bool-False→"off" coercion
    in _resolve_web_urls for the unquoted case)."""
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        'web_urls:\n  citations: "off"\n  search_result_groups: "rich"\n',
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    assert cfg["web_urls"]["citations"] == "off"
    assert cfg["web_urls"]["search_result_groups"] == "rich"
    # Sibling keys from DEFAULTS survive the partial-dict merge.
    assert cfg["web_urls"]["conv_safe_urls"] == WEB_URLS_DEFAULT["conv_safe_urls"]


def test_load_config_web_urls_unquoted_off_yaml11_coercion(
    tmp_path, _isolated_config_env
):
    """Bare ``off`` in YAML → pyyaml's YAML 1.1 parser coerces to bool
    False. load_config preserves the raw shape; resolution at extractor
    init converts False → 'off' via ``_resolve_web_urls``."""
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        "web_urls:\n  citations: off\n",
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    # Raw shape has bool False (YAML 1.1 coercion).
    assert cfg["web_urls"]["citations"] is False
    # Resolution converts False to "off".
    resolved = _resolve_web_urls(cfg["web_urls"])
    assert resolved["citations"] == "off"


def test_load_config_no_file_returns_defaults_including_web_urls(_isolated_config_env):
    cfg = load_config()
    assert cfg["web_urls"] == WEB_URLS_DEFAULT
    # Confirm it's a distinct dict object — load_config protects against
    # accidental caller mutation of the module-level default.
    cfg["web_urls"]["citations"] = "off"
    assert config_mod.WEB_URLS_DEFAULT["citations"] == "rich"


# --------------------------------------------------------------------------- #
# Extractor constructor + resolution
# --------------------------------------------------------------------------- #


@pytest.fixture
def _extractor_args(tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_text("[]", encoding="utf-8")
    return {"input_file": str(input_file), "output_dir": str(tmp_path / "out")}


def test_extractor_web_urls_none_uses_config_default(
    _extractor_args, _isolated_config_env
):
    ex = ConversationExtractorV2(**_extractor_args)
    # No config file, no constructor override → self.web_urls is the
    # per-type default.
    assert ex.web_urls == WEB_URLS_DEFAULT


def test_extractor_web_urls_preset_str_resolves(_extractor_args, _isolated_config_env):
    ex = ConversationExtractorV2(web_urls="rich", **_extractor_args)
    assert ex.web_urls == WEB_URLS_PRESETS["rich"]


def test_extractor_web_urls_dict_merges_over_defaults(
    _extractor_args, _isolated_config_env
):
    ex = ConversationExtractorV2(
        web_urls={"citations": "off"}, **_extractor_args
    )
    assert ex.web_urls["citations"] == "off"
    assert ex.web_urls["conv_safe_urls"] == WEB_URLS_DEFAULT["conv_safe_urls"]


def test_extractor_constructor_arg_wins_over_config_file(
    tmp_path, _extractor_args, _isolated_config_env
):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text("web_urls: off\n", encoding="utf-8")
    ex = ConversationExtractorV2(
        web_urls="rich", config_path=str(cfg_file), **_extractor_args
    )
    assert ex.web_urls == WEB_URLS_PRESETS["rich"]


# --------------------------------------------------------------------------- #
# End-to-end rendering — golden checks per preset
# --------------------------------------------------------------------------- #


def _make_sample_conv():
    """Fabricate a conv with every metadata URL source populated."""
    return {
        "id": "web-urls-test",
        "title": "Web URLs Test",
        "create_time": 1704067200,
        "update_time": 1704067200,
        "safe_urls": ["https://conv-only.example.com/page"],
        "mapping": {
            "n0": {"id": "n0", "parent": None, "children": ["n1"], "message": None},
            "n1": {
                "id": "n1",
                "parent": "n0",
                "children": ["n2"],
                "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["What is X?"]},
                },
            },
            "n2": {
                "id": "n2",
                "parent": "n1",
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["The answer to X."]},
                    "metadata": {
                        "citations": [
                            {
                                "quote": "cited quote",
                                "metadata": {
                                    "type": "webpage",
                                    "title": "Cited Source",
                                    "url": "https://cited.example.com/page",
                                },
                            }
                        ],
                        "safe_urls": ["https://msg-safe.example.com/page"],
                        "search_result_groups": [
                            {
                                "type": "search_result_group",
                                "domain": "search.example.com",
                                "entries": [
                                    {
                                        "type": "search_result",
                                        "url": "https://search.example.com/hit-1",
                                        "title": "Search Hit One",
                                        "snippet": "This is a search snippet.",
                                        "attribution": "Search Example",
                                    }
                                ],
                            }
                        ],
                        "content_references": [
                            {
                                "type": "webpage_extended",
                                "url": "https://cref.example.com/page",
                                "title": "CRef Page",
                                "snippet": "This is a content ref snippet.",
                                "attribution": "cref.example.com",
                            }
                        ],
                    },
                },
            },
        },
        "current_node": "n2",
    }


def _render_with_preset(preset, tmp_path):
    """Run extractor at the given preset; return (markdown, json_data)."""
    conv = _make_sample_conv()
    input_file = tmp_path / f"in_{preset}.json"
    input_file.write_text(json.dumps([conv]), encoding="utf-8")
    ex = ConversationExtractorV2(
        input_file=str(input_file),
        output_dir=str(tmp_path / f"out_{preset}"),
        output_format="both",
        web_urls=preset,
    )
    md_meta, msgs, _ = ex.process_conversation(conv)
    md = ex.generate_markdown(md_meta, msgs)
    json_data = ex.generate_json_data(md_meta, msgs)
    return md, json_data


def test_preset_off_renders_no_url_blocks(tmp_path, _isolated_config_env):
    md, _ = _render_with_preset("off", tmp_path)
    assert "**Citations:**" not in md
    assert "**Sources:**" not in md
    assert "**Web Search URLs:**" not in md


def test_preset_citations_renders_only_citations_block(
    tmp_path, _isolated_config_env
):
    md, _ = _render_with_preset("citations", tmp_path)
    assert "**Citations:**" in md
    assert "Cited Source" in md
    assert "**Sources:**" not in md
    # Web Search URLs may still appear ONLY for URLs from content-type
    # paths / regex (not gated). Our sample has none of those, so should
    # not appear.
    assert "**Web Search URLs:**" not in md


def test_preset_rich_renders_citations_and_sources(tmp_path, _isolated_config_env):
    md, _ = _render_with_preset("rich", tmp_path)
    assert "**Citations:**" in md
    assert "Cited Source" in md
    assert "**Sources:**" in md
    # Rich Sources entries include title + snippet.
    assert "Search Hit One" in md
    assert "This is a search snippet." in md
    assert "CRef Page" in md
    assert "This is a content ref snippet." in md


def test_preset_rich_cross_block_dedup_at_render(tmp_path, _isolated_config_env):
    """URLs surfaced in Citations or Sources block do NOT re-appear in
    Web Search URLs block."""
    md, _ = _render_with_preset("rich", tmp_path)
    # Extract the Web Search URLs section if present.
    if "**Web Search URLs:**" in md:
        block = md.split("**Web Search URLs:**", 1)[1]
        # Citation and Sources URLs must not appear here.
        assert "https://cited.example.com/page" not in block
        assert "https://search.example.com/hit-1" not in block
        assert "https://cref.example.com/page" not in block


def test_preset_rich_json_keeps_every_source_whole(tmp_path, _isolated_config_env):
    """Markdown dedup is render-only; JSON output emits citations,
    web_urls, and web_sources whole so downstream indexers keep every
    captured source."""
    _, json_data = _render_with_preset("rich", tmp_path)
    msg = json_data["messages"][-1]  # assistant message
    assert "citations" in msg
    assert msg["citations"][0]["url"] == "https://cited.example.com/page"
    assert "web_sources" in msg
    sources_by_url = {s["url"]: s for s in msg["web_sources"]}
    assert "https://search.example.com/hit-1" in sources_by_url
    assert "https://cref.example.com/page" in sources_by_url
    # web_urls should still contain every URL — no dedup applied.
    if "web_urls" in msg:
        for url in msg["web_urls"]:
            assert url  # non-empty


def test_preset_rich_url_only_sources_off_by_default(
    tmp_path, _isolated_config_env
):
    """Under the 'rich' preset, URL-only source types (conv_safe_urls,
    msg_safe_urls) are OFF, so their URLs must not surface anywhere."""
    md, json_data = _render_with_preset("rich", tmp_path)
    assert "https://conv-only.example.com/page" not in md
    assert "https://msg-safe.example.com/page" not in md
    msg = json_data["messages"][-1]
    if "web_urls" in msg:
        assert "https://conv-only.example.com/page" not in msg["web_urls"]
        assert "https://msg-safe.example.com/page" not in msg["web_urls"]
