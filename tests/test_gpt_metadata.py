"""Tests for the Custom GPT / per-turn model / plugin metadata feature.

Covers the pure functions in ``gpt_metadata.py`` plus the integration
through ``ConversationExtractorV2`` so a single config flag toggles the
whole feature end-to-end.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from chatgpt_extractor.extractor import ConversationExtractorV2
from chatgpt_extractor.gpt_metadata import (
    extract_conv_gpt_meta,
    extract_msg_gpt_signals,
    format_per_turn_suffix,
)


# --------------------------------------------------------------------------- #
# extract_conv_gpt_meta — pure function over the raw conversation shape
# --------------------------------------------------------------------------- #


def _msg_node(
    msg_id: str, role: str, slug: str | None = None, gizmo: str | None = None
) -> dict:
    """Build a mapping node mimicking the export shape."""
    msg = {"author": {"role": role}}
    meta: dict = {}
    if slug:
        meta["model_slug"] = slug
    if gizmo:
        meta["gizmo_id"] = gizmo
    if meta:
        msg["metadata"] = meta
    return {"id": msg_id, "message": msg}


def test_extract_conv_gpt_meta_custom_gpt():
    """Custom GPT (gizmo_type='gpt') → emit gizmo_id + gizmo_type + models_used."""
    conv = {
        "gizmo_id": "g-uefFoRnpX",
        "gizmo_type": "gpt",
        "default_model_slug": "text-davinci-002-render-sha",
        "mapping": {
            "n1": _msg_node("n1", "assistant", slug="gpt-4o", gizmo="g-uefFoRnpX"),
            "n2": _msg_node("n2", "user"),
            "n3": _msg_node("n3", "assistant", slug="gpt-4o", gizmo="g-uefFoRnpX"),
        },
    }
    out = extract_conv_gpt_meta(conv)
    assert out == {
        "gizmo_id": "g-uefFoRnpX",
        "gizmo_type": "gpt",
        "models_used": ["gpt-4o"],
    }


def test_extract_conv_gpt_meta_snorlax_project_suppresses_gizmo_id():
    """Project conv (gizmo_type='snorlax') → emit gizmo_type, NOT gizmo_id.

    The conv-level gizmo_id for a project is the same string already
    emitted as ``project_id`` from ``conversation_template_id`` (e.g.
    ``g-p-685bb57d…``). Duplicating it would clutter frontmatter.
    """
    conv = {
        "gizmo_id": "g-p-685bb57d8cec8191985f702d1b8f32dd",
        "gizmo_type": "snorlax",
        "conversation_template_id": "g-p-685bb57d8cec8191985f702d1b8f32dd",
        "mapping": {
            "n1": _msg_node(
                "n1",
                "assistant",
                slug="gpt-5",
                gizmo="g-p-685bb57d8cec8191985f702d1b8f32dd",
            ),
        },
    }
    out = extract_conv_gpt_meta(conv)
    assert "gizmo_id" not in out
    assert out["gizmo_type"] == "snorlax"
    assert out["models_used"] == ["gpt-5"]


def test_extract_conv_gpt_meta_default_chatgpt():
    """No Custom GPT / project signals → empty dict (no noise in frontmatter)."""
    conv = {
        "gizmo_type": None,
        "gizmo_id": None,
        "default_model_slug": "gpt-4o",
        "mapping": {
            "n1": _msg_node("n1", "user"),
        },
    }
    out = extract_conv_gpt_meta(conv)
    assert out == {}


def test_extract_conv_gpt_meta_models_used_dedupes_and_sorts():
    """models_used collapses duplicate slugs and sorts deterministically."""
    conv = {
        "mapping": {
            "n1": _msg_node("n1", "assistant", slug="gpt-4o"),
            "n2": _msg_node("n2", "assistant", slug="gpt-5-thinking"),
            "n3": _msg_node("n3", "assistant", slug="gpt-4o"),
            "n4": _msg_node("n4", "user"),  # no slug → not counted
        },
    }
    out = extract_conv_gpt_meta(conv)
    assert out["models_used"] == ["gpt-4o", "gpt-5-thinking"]


def test_extract_conv_gpt_meta_handles_legacy_2023_shape():
    """2023-era convs may omit default_model_slug and have sparse metadata.

    Validated against the corpus scan: 57/1485 convs in 2023 had
    gizmo signals; only 14 had default_model_slug. The extractor must
    not crash and should fall back to an empty dict cleanly.
    """
    conv = {
        "gizmo_type": None,
        "gizmo_id": None,
        "mapping": {
            "n1": {"id": "n1", "message": None},  # tombstone node
            "n2": {"id": "n2"},  # node without message
        },
    }
    out = extract_conv_gpt_meta(conv)
    assert out == {}


def test_extract_conv_gpt_meta_tolerates_missing_mapping():
    """Defensive: a conv with no mapping field (extreme edge case) doesn't crash."""
    out = extract_conv_gpt_meta({"gizmo_type": "gpt", "gizmo_id": "g-x"})
    assert out == {"gizmo_id": "g-x", "gizmo_type": "gpt"}


# --------------------------------------------------------------------------- #
# extract_msg_gpt_signals — pure function over a single message
# --------------------------------------------------------------------------- #


def test_extract_msg_gpt_signals_full():
    msg = {
        "metadata": {
            "model_slug": "gpt-4o",
            "gizmo_id": "g-uefFoRnpX",
            "invoked_plugin": {
                "namespace": "youtube_api_widenex_com__jit_plugin",
                "plugin_id": "g-01a7b246a025199ec0e24020f9416416915cb621",
                "http_response_status": 200,
            },
        }
    }
    out = extract_msg_gpt_signals(msg)
    assert out == {
        "model_slug": "gpt-4o",
        "gizmo_id": "g-uefFoRnpX",
        "plugin_namespace": "youtube_api_widenex_com__jit_plugin",
    }


def test_extract_msg_gpt_signals_empty_metadata():
    """User / legacy messages with no metadata block all-None."""
    assert extract_msg_gpt_signals({"author": {"role": "user"}}) == {
        "model_slug": None,
        "gizmo_id": None,
        "plugin_namespace": None,
    }


def test_extract_msg_gpt_signals_invoked_plugin_without_namespace():
    """Some invoked_plugin entries lack the namespace key — must not crash."""
    msg = {"metadata": {"invoked_plugin": {"plugin_id": "g-xyz"}}}
    out = extract_msg_gpt_signals(msg)
    assert out["plugin_namespace"] is None


# --------------------------------------------------------------------------- #
# format_per_turn_suffix — pure formatting
# --------------------------------------------------------------------------- #


def test_format_per_turn_suffix_full():
    """All three segments present, conv default differs → all emitted."""
    msg = {"model_slug": "gpt-4o", "gizmo_id": "g-other", "plugin_namespace": "p"}
    s = format_per_turn_suffix(msg, conv_default_gizmo_id="g-uefFoRnpX")
    assert s == " · gpt-4o · plugin:p · gpt:g-other"


def test_format_per_turn_suffix_gpt_id_suppressed_when_matches_conv_default():
    """Per-message gizmo matches conv default (the common Custom GPT case)
    → suppress redundant ``gpt:<id>`` segment."""
    msg = {"model_slug": "gpt-4o", "gizmo_id": "g-uefFoRnpX"}
    s = format_per_turn_suffix(msg, conv_default_gizmo_id="g-uefFoRnpX")
    assert s == " · gpt-4o"


def test_format_per_turn_suffix_gpt_id_emitted_on_mismatch_atmention():
    """The @mention case: per-message gizmo differs → emit gpt:<id>."""
    msg = {"model_slug": "gpt-5-thinking", "gizmo_id": "g-dZUgwxUeJ"}
    s = format_per_turn_suffix(msg, conv_default_gizmo_id=None)
    assert s == " · gpt-5-thinking · gpt:g-dZUgwxUeJ"


def test_format_per_turn_suffix_empty():
    """Nothing per-turn-specific → empty string so caller emits just timestamp."""
    assert format_per_turn_suffix({}, conv_default_gizmo_id=None) == ""
    assert (
        format_per_turn_suffix({"model_slug": None}, conv_default_gizmo_id=None) == ""
    )


def test_format_per_turn_suffix_only_plugin():
    """Plugin segment without model is valid (older / unusual messages)."""
    s = format_per_turn_suffix({"plugin_namespace": "Wolfram"}, None)
    assert s == " · plugin:Wolfram"


# --------------------------------------------------------------------------- #
# Integration through ConversationExtractorV2
# --------------------------------------------------------------------------- #


@pytest.fixture
def custom_gpt_conv_fixture():
    """A Custom GPT conv with two assistant turns, one invoking a plugin."""
    return {
        "id": "17050a25-ff53-4d8c-9925-e4bcec0d2f51",
        "conversation_id": "17050a25-ff53-4d8c-9925-e4bcec0d2f51",
        "title": "Video Transkrip Ringkasan",
        "create_time": 1716793111.222095,
        "update_time": 1716793260.354665,
        "default_model_slug": "text-davinci-002-render-sha",
        "gizmo_id": "g-uefFoRnpX",
        "gizmo_type": "gpt",
        "conversation_template_id": "g-uefFoRnpX",
        "current_node": "a3",
        "mapping": {
            "u1": {
                "id": "u1",
                "parent": None,
                "children": ["a1"],
                "message": {
                    "id": "u1",
                    "author": {"role": "user"},
                    "create_time": 1716793112.0,
                    "content": {"content_type": "text", "parts": ["Summarise this"]},
                    "metadata": {},
                },
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "children": ["u2"],
                "message": {
                    "id": "a1",
                    "author": {"role": "assistant"},
                    "create_time": 1716793113.0,
                    "content": {"content_type": "text", "parts": ["On it"]},
                    "metadata": {
                        "model_slug": "gpt-4o",
                        "gizmo_id": "g-uefFoRnpX",
                        "invoked_plugin": {"namespace": "youtube_api"},
                    },
                },
            },
            "u2": {
                "id": "u2",
                "parent": "a1",
                "children": ["a3"],
                "message": {
                    "id": "u2",
                    "author": {"role": "user"},
                    "create_time": 1716793220.0,
                    "content": {"content_type": "text", "parts": ["Now in Indonesian"]},
                    "metadata": {},
                },
            },
            "a3": {
                "id": "a3",
                "parent": "u2",
                "children": [],
                "message": {
                    "id": "a3",
                    "author": {"role": "assistant"},
                    "create_time": 1716793259.0,
                    "content": {"content_type": "text", "parts": ["Ringkasan"]},
                    "metadata": {
                        "model_slug": "gpt-4o",
                        "gizmo_id": "g-uefFoRnpX",
                    },
                },
            },
        },
    }


def _extractor(tmp_path, **kw):
    """Helper: minimal extractor instance with output dir under tmp_path."""
    return ConversationExtractorV2(
        output_dir=str(tmp_path / "out"),
        output_format="both",
        **kw,
    )


def test_integration_custom_gpt_frontmatter_contains_new_fields(
    tmp_path, custom_gpt_conv_fixture
):
    ex = _extractor(tmp_path)
    out = ex.process_conversation(custom_gpt_conv_fixture)
    assert out is not None
    metadata, _msgs, _json = out
    assert metadata["gizmo_id"] == "g-uefFoRnpX"
    assert metadata["gizmo_type"] == "gpt"
    assert metadata["models_used"] == ["gpt-4o"]
    # Pre-existing field unchanged (backwards compat)
    assert metadata["model"] == "text-davinci-002-render-sha"


def test_integration_per_turn_line_includes_model_and_plugin(
    tmp_path, custom_gpt_conv_fixture
):
    ex = _extractor(tmp_path)
    out = ex.process_conversation(custom_gpt_conv_fixture)
    assert out is not None
    metadata, msgs, _json = out
    md = ex.generate_markdown(metadata, msgs)
    # First assistant turn invoked a plugin
    assert " · gpt-4o · plugin:youtube_api" in md
    # Second assistant turn has model only (no plugin)
    assert "· gpt-4o*\n" in md or "· gpt-4o*\r\n" in md
    # gpt:<id> should NOT appear — per-msg gizmo matches conv default
    assert "gpt:g-uefFoRnpX" not in md


def test_integration_no_gpt_metadata_flag_produces_legacy_output(
    tmp_path, custom_gpt_conv_fixture
):
    """--no-gpt-metadata: frontmatter has no new fields; per-turn line is
    just the bare timestamp (legacy)."""
    ex = _extractor(tmp_path, gpt_metadata=False)
    out = ex.process_conversation(custom_gpt_conv_fixture)
    assert out is not None
    metadata, msgs, _json = out
    assert "gizmo_id" not in metadata
    assert "gizmo_type" not in metadata
    assert "models_used" not in metadata
    md = ex.generate_markdown(metadata, msgs)
    assert "gpt-4o" not in md  # no per-turn model emission
    assert "plugin:" not in md
    # But per-turn timestamps stay on (default)
    assert "*2024-" in md


def test_integration_json_carries_per_turn_gpt_fields(
    tmp_path, custom_gpt_conv_fixture
):
    """JSON output mirrors the frontmatter additions + per-msg signals."""
    ex = _extractor(tmp_path)
    out = ex.process_conversation(custom_gpt_conv_fixture)
    metadata, msgs, json_data = out
    assert json_data["gizmo_id"] == "g-uefFoRnpX"
    assert json_data["gizmo_type"] == "gpt"
    assert json_data["models_used"] == ["gpt-4o"]
    # Find the first assistant message in JSON
    asst = [m for m in json_data["messages"] if m["role"] == "assistant"]
    assert asst[0]["model_slug"] == "gpt-4o"
    assert asst[0]["plugin_namespace"] == "youtube_api"


def test_integration_atmention_emits_gpt_id_in_per_turn(tmp_path):
    """A conv where one assistant turn used a different Custom GPT than the
    conversation default (@mention) — per-turn line shows ``gpt:<id>``."""
    conv = {
        "id": "x",
        "conversation_id": "x",
        "title": "@mention",
        "create_time": 1.0,
        "update_time": 2.0,
        "default_model_slug": "gpt-5",
        "gizmo_id": "g-p-PROJECT",
        "gizmo_type": "snorlax",
        "conversation_template_id": "g-p-PROJECT",
        "current_node": "a1",
        "mapping": {
            "u1": {
                "id": "u1",
                "parent": None,
                "children": ["a1"],
                "message": {
                    "id": "u1",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {
                        "content_type": "text",
                        "parts": ["@gpt-x do something"],
                    },
                    "metadata": {},
                },
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "children": [],
                "message": {
                    "id": "a1",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"content_type": "text", "parts": ["sure"]},
                    "metadata": {"model_slug": "gpt-5", "gizmo_id": "g-dZUgwxUeJ"},
                },
            },
        },
    }
    ex = _extractor(tmp_path)
    out = ex.process_conversation(conv)
    metadata, msgs, _json = out
    md = ex.generate_markdown(metadata, msgs)
    # Project context: project_id present, gizmo_id suppressed
    assert metadata["project_id"] == "g-p-PROJECT"
    assert "gizmo_id" not in metadata
    # Per-turn line shows gpt:<id> because per-msg gizmo differs from conv default (g-p-PROJECT)
    assert "gpt:g-dZUgwxUeJ" in md


def test_integration_default_chatgpt_no_new_frontmatter(tmp_path):
    """A plain default-ChatGPT conv (no gizmo signals at all) gets the
    standard frontmatter, no gpt-metadata fields."""
    conv = {
        "id": "y",
        "conversation_id": "y",
        "title": "Plain",
        "create_time": 1.0,
        "update_time": 2.0,
        "default_model_slug": "gpt-4o",
        "current_node": "a1",
        "mapping": {
            "u1": {
                "id": "u1",
                "parent": None,
                "children": ["a1"],
                "message": {
                    "id": "u1",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {"content_type": "text", "parts": ["hi"]},
                    "metadata": {},
                },
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "children": [],
                "message": {
                    "id": "a1",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"content_type": "text", "parts": ["hello"]},
                    "metadata": {"model_slug": "gpt-4o"},
                },
            },
        },
    }
    ex = _extractor(tmp_path)
    metadata, msgs, _json = ex.process_conversation(conv)
    assert "gizmo_id" not in metadata
    assert "gizmo_type" not in metadata
    # models_used DOES appear (it's purely informative — emit when known)
    assert metadata["models_used"] == ["gpt-4o"]
    md = ex.generate_markdown(metadata, msgs)
    # Per-turn line should include the model
    assert "· gpt-4o*" in md


# --------------------------------------------------------------------------- #
# Config-file integration: defaults + override
# --------------------------------------------------------------------------- #


def test_config_gpt_metadata_default_true(tmp_path):
    """No CLI arg, no config file: gpt_metadata is True (config default)."""
    ex = _extractor(tmp_path, gpt_metadata=None, config_path="/does/not/exist")
    assert ex.gpt_metadata is True


def test_config_gpt_metadata_from_file_false(tmp_path):
    """Config file can flip the default to False."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({"gpt_metadata": False}), encoding="utf-8")
    ex = _extractor(tmp_path, gpt_metadata=None, config_path=str(cfg))
    assert ex.gpt_metadata is False


def test_constructor_arg_overrides_config_file(tmp_path):
    """Explicit constructor / CLI arg wins over config file."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({"gpt_metadata": False}), encoding="utf-8")
    ex = _extractor(tmp_path, gpt_metadata=True, config_path=str(cfg))
    assert ex.gpt_metadata is True


# --------------------------------------------------------------------------- #
# load_gpt_names_xlsx + integration with extractor
# --------------------------------------------------------------------------- #


def _write_gpt_names_xlsx(path, rows):
    """Helper: write a 2- or 3-column GPT_Names.xlsx matching the sidecar shape.

    Skips the test if openpyxl is not installed — the public extractor
    doesn't list openpyxl as a hard dependency (only the private online-sync
    package + the GPT_Names.xlsx reader, both of which fall back silently
    when it's missing). CI environments without openpyxl skip cleanly.
    """
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value="Gizmo ID")
    ws.cell(row=1, column=2, value="GPT Name")
    ws.cell(row=1, column=3, value="Previous Name (review)")
    for i, row in enumerate(rows, start=2):
        for j, value in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=value)
    wb.save(path)


def test_load_gpt_names_xlsx_returns_dict(tmp_path):
    """Happy-path read of a 3-column xlsx returns {id: name} with whitespace stripped."""
    from chatgpt_extractor.gpt_metadata import load_gpt_names_xlsx

    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(
        xlsx,
        [
            ("g-uefFoRnpX", "Summarizer 2", ""),
            ("g-dZUgwxUeJ", "  Unorthodox Humor XI  ", "Unorthodox Humor"),
            ("g-other", "Trip Planner", None),
        ],
    )
    names = load_gpt_names_xlsx(xlsx)
    assert names == {
        "g-uefFoRnpX": "Summarizer 2",
        "g-dZUgwxUeJ": "Unorthodox Humor XI",  # whitespace stripped
        "g-other": "Trip Planner",
    }


def test_load_gpt_names_xlsx_missing_file_is_silent_noop(tmp_path):
    """Missing file / None path → empty dict, no exception."""
    from chatgpt_extractor.gpt_metadata import load_gpt_names_xlsx

    assert load_gpt_names_xlsx(None) == {}
    assert load_gpt_names_xlsx(tmp_path / "nope.xlsx") == {}


def test_load_gpt_names_xlsx_corrupt_file_does_not_crash(tmp_path, caplog):
    """Garbage bytes in xlsx → empty dict + WARNING log, never raises.

    Requires openpyxl: without it the loader takes the ImportError branch
    (returns empty dict + debug log) before ever touching the file, so the
    WARNING assertion can't run. CI without openpyxl just skips.
    """
    pytest.importorskip("openpyxl")
    import logging
    from chatgpt_extractor.gpt_metadata import load_gpt_names_xlsx

    xlsx = tmp_path / "GPT_Names.xlsx"
    xlsx.write_bytes(b"this is not a real xlsx file")
    with caplog.at_level(logging.WARNING, logger="chatgpt_extractor.gpt_metadata"):
        names = load_gpt_names_xlsx(xlsx)
    assert names == {}
    assert any("could not be read" in rec.message for rec in caplog.records)


def test_extract_metadata_resolves_gpt_name_from_xlsx(
    tmp_path, custom_gpt_conv_fixture
):
    """Integration: extractor with gpt_names_xlsx populates metadata['gpt_name']."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [("g-uefFoRnpX", "Summarizer 2", "")])
    ex = _extractor(tmp_path, gpt_names_xlsx=str(xlsx))
    metadata, _msgs, _json = ex.process_conversation(custom_gpt_conv_fixture)
    assert metadata["gizmo_id"] == "g-uefFoRnpX"
    assert metadata["gpt_name"] == "Summarizer 2"


def test_extract_metadata_no_gpt_name_when_xlsx_missing_id(
    tmp_path, custom_gpt_conv_fixture
):
    """When the sidecar has rows but none matches → no gpt_name field at all."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [("g-otherUnrelated", "Some Other GPT", "")])
    ex = _extractor(tmp_path, gpt_names_xlsx=str(xlsx))
    metadata, _msgs, _json = ex.process_conversation(custom_gpt_conv_fixture)
    assert metadata["gizmo_id"] == "g-uefFoRnpX"
    assert "gpt_name" not in metadata


def test_per_turn_suffix_substitutes_name_when_available(tmp_path):
    """@mention case + populated xlsx → per-turn line shows gpt:<Pretty Name>."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [("g-dZUgwxUeJ", "Unorthodox Humor XI", "")])
    conv = {
        "id": "x",
        "conversation_id": "x",
        "title": "@mention",
        "create_time": 1.0,
        "update_time": 2.0,
        "default_model_slug": "gpt-5",
        "gizmo_id": "g-p-PROJECT",
        "gizmo_type": "snorlax",
        "conversation_template_id": "g-p-PROJECT",
        "current_node": "a1",
        "mapping": {
            "u1": {
                "id": "u1",
                "parent": None,
                "children": ["a1"],
                "message": {
                    "id": "u1",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {"content_type": "text", "parts": ["@gpt-x"]},
                    "metadata": {},
                },
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "children": [],
                "message": {
                    "id": "a1",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"content_type": "text", "parts": ["sure"]},
                    "metadata": {"model_slug": "gpt-5", "gizmo_id": "g-dZUgwxUeJ"},
                },
            },
        },
    }
    ex = _extractor(tmp_path, gpt_names_xlsx=str(xlsx))
    metadata, msgs, _json = ex.process_conversation(conv)
    md = ex.generate_markdown(metadata, msgs)
    assert "gpt:Unorthodox Humor XI" in md
    assert "gpt:g-dZUgwxUeJ" not in md  # raw id not emitted when name known


def test_per_turn_suffix_falls_back_to_id_when_unknown(tmp_path):
    """@mention case + empty xlsx → per-turn line keeps gpt:<g-XXX> raw id."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [])  # header only, no rows
    conv = {
        "id": "x",
        "conversation_id": "x",
        "title": "@mention",
        "create_time": 1.0,
        "update_time": 2.0,
        "default_model_slug": "gpt-5",
        "gizmo_id": "g-p-PROJECT",
        "gizmo_type": "snorlax",
        "conversation_template_id": "g-p-PROJECT",
        "current_node": "a1",
        "mapping": {
            "u1": {
                "id": "u1",
                "parent": None,
                "children": ["a1"],
                "message": {
                    "id": "u1",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {"content_type": "text", "parts": ["@gpt-x"]},
                    "metadata": {},
                },
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "children": [],
                "message": {
                    "id": "a1",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"content_type": "text", "parts": ["sure"]},
                    "metadata": {"model_slug": "gpt-5", "gizmo_id": "g-dZUgwxUeJ"},
                },
            },
        },
    }
    ex = _extractor(tmp_path, gpt_names_xlsx=str(xlsx))
    metadata, msgs, _json = ex.process_conversation(conv)
    md = ex.generate_markdown(metadata, msgs)
    assert "gpt:g-dZUgwxUeJ" in md


def test_json_output_includes_gpt_name(tmp_path, custom_gpt_conv_fixture):
    """JSON envelope mirrors the new gpt_name field when set."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [("g-uefFoRnpX", "Summarizer 2", "")])
    ex = _extractor(tmp_path, gpt_names_xlsx=str(xlsx))
    _metadata, _msgs, json_data = ex.process_conversation(custom_gpt_conv_fixture)
    assert json_data["gpt_name"] == "Summarizer 2"


def test_gpt_names_xlsx_via_config_file(tmp_path, custom_gpt_conv_fixture):
    """Config file value is honoured when no ctor arg supplied."""
    xlsx = tmp_path / "GPT_Names.xlsx"
    _write_gpt_names_xlsx(xlsx, [("g-uefFoRnpX", "Summarizer 2", "")])
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({"gpt_names_xlsx": str(xlsx)}), encoding="utf-8")
    ex = _extractor(tmp_path, gpt_names_xlsx=None, config_path=str(cfg))
    metadata, _msgs, _json = ex.process_conversation(custom_gpt_conv_fixture)
    assert metadata["gpt_name"] == "Summarizer 2"
