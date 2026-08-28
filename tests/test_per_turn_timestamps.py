"""Tests for per-turn timestamps + the YAML config layer.

Covers:
- ``config.load_config`` — built-in defaults, explicit path, env-var path,
  malformed YAML silently falls back, key precedence.
- ``ConversationExtractorV2`` — default-on emission of per-turn timestamps,
  ``--no-per-turn-timestamps`` / constructor-arg suppression matching the
  pre-config output, explicit arg overriding config.
- ``process_messages`` — propagates ``create_time`` through the per-message
  dict; ``merge_continuations`` keeps the earliest segment's timestamp.
- ``generate_json_data`` — emits ISO-8601 UTC under the ``timestamp`` field
  (regression test for the bug where the source key was the never-written
  ``timestamp`` instead of ``create_time``, leaving every JSON message with
  ``"timestamp": null``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatgpt_extractor import config as config_mod
from chatgpt_extractor.extractor import ConversationExtractorV2


# --------------------------------------------------------------------------- #
# config.load_config
# --------------------------------------------------------------------------- #


def test_load_config_returns_defaults_when_no_file_found(_isolated_config_env):
    cfg = config_mod.load_config()
    assert cfg == config_mod.DEFAULTS
    assert cfg["per_turn_timestamps"] is True


def test_load_config_reads_explicit_path(tmp_path, _isolated_config_env):
    cfg_file = tmp_path / "override.yaml"
    cfg_file.write_text("per_turn_timestamps: false\n", encoding="utf-8")
    cfg = config_mod.load_config(str(cfg_file))
    assert cfg["per_turn_timestamps"] is False


def test_load_config_uses_env_var_when_no_explicit_path(tmp_path, monkeypatch):
    cfg_file = tmp_path / "from_env.yaml"
    cfg_file.write_text("per_turn_timestamps: false\n", encoding="utf-8")
    monkeypatch.setenv("CHATGPT_EXTRACTOR_CONFIG", str(cfg_file))
    monkeypatch.setenv("HOME", str(tmp_path / "_empty_home"))
    monkeypatch.chdir(tmp_path / "_empty_cwd" if False else tmp_path)
    cfg = config_mod.load_config()
    assert cfg["per_turn_timestamps"] is False


def test_load_config_malformed_yaml_silently_falls_back(tmp_path, _isolated_config_env):
    cfg_file = tmp_path / "broken.yaml"
    cfg_file.write_text(": : : not yaml at all : : :", encoding="utf-8")
    cfg = config_mod.load_config(str(cfg_file))
    # Falls back to defaults — config errors must not block extraction.
    assert cfg == config_mod.DEFAULTS


def test_load_config_explicit_path_pointing_to_missing_file_returns_defaults(
    tmp_path, _isolated_config_env
):
    cfg = config_mod.load_config(str(tmp_path / "does_not_exist.yaml"))
    assert cfg == config_mod.DEFAULTS


# --------------------------------------------------------------------------- #
# Extractor — per-turn timestamps in markdown output
# --------------------------------------------------------------------------- #


@pytest.fixture
def _extractor_args(tmp_path):
    return {
        "input_file": str(tmp_path / "input.json"),
        "output_dir": str(tmp_path / "out"),
    }


def _msgs_with_timestamps():
    return [
        {"role": "user", "content": "Hello", "create_time": 1716638400.0},
        {"role": "assistant", "content": "Hi", "create_time": 1716638460.5},
    ]


def _metadata():
    return {
        "id": "x",
        "title": "T",
        "created": "2024-05-25T12:00:00Z",
        "model": "gpt-4",
    }


def test_extractor_emits_per_turn_timestamps_by_default(
    _extractor_args, _isolated_config_env
):
    ext = ConversationExtractorV2(**_extractor_args)
    md = ext.generate_markdown(_metadata(), _msgs_with_timestamps())
    # Italic ISO line appears beneath each role heading.
    assert "## User" in md
    # 1716638400 UTC = 2024-05-25T12:00:00Z
    assert "*2024-05-25T12:00:00Z*" in md
    # Order matters: the italic line is between heading and content.
    user_idx = md.index("## User")
    content_idx = md.index("Hello")
    italic_idx = md.index("*2024-05-25T12:00:00Z*")
    assert user_idx < italic_idx < content_idx


def test_extractor_no_per_turn_timestamps_matches_legacy(
    _extractor_args, _isolated_config_env
):
    ext = ConversationExtractorV2(per_turn_timestamps=False, **_extractor_args)
    md = ext.generate_markdown(_metadata(), _msgs_with_timestamps())
    # Headings present; no italic timestamps anywhere.
    assert "## User" in md
    assert "## Assistant" in md
    assert "*2024-05-25T" not in md


def test_extractor_constructor_arg_overrides_config_file(
    tmp_path, _extractor_args, _isolated_config_env
):
    cfg_file = tmp_path / "off.yaml"
    cfg_file.write_text("per_turn_timestamps: false\n", encoding="utf-8")
    # Config says False, explicit constructor arg says True → True wins.
    ext = ConversationExtractorV2(
        per_turn_timestamps=True,
        config_path=str(cfg_file),
        **_extractor_args,
    )
    md = ext.generate_markdown(_metadata(), _msgs_with_timestamps())
    assert "*2024-05-25T12:00:00Z*" in md


def test_extractor_config_file_used_when_constructor_arg_is_none(
    tmp_path, _extractor_args, _isolated_config_env
):
    cfg_file = tmp_path / "off.yaml"
    cfg_file.write_text("per_turn_timestamps: false\n", encoding="utf-8")
    ext = ConversationExtractorV2(
        per_turn_timestamps=None,
        config_path=str(cfg_file),
        **_extractor_args,
    )
    md = ext.generate_markdown(_metadata(), _msgs_with_timestamps())
    assert "*2024-05-25T" not in md


def test_extractor_skips_timestamp_on_system_message(
    _extractor_args, _isolated_config_env
):
    """System prompt's "send time" is the custom-instructions configuration
    moment, not a chat moment; per-turn timestamps don't apply."""
    ext = ConversationExtractorV2(**_extractor_args)
    msgs = [
        {"role": "system", "content": "sys", "create_time": 1716638000.0},
        {"role": "user", "content": "Hi", "create_time": 1716638400.0},
    ]
    md = ext.generate_markdown(_metadata(), msgs)
    # User timestamp present.
    assert "*2024-05-25T12:00:00Z*" in md
    # System timestamp absent — the only ISO line in the body is the user's.
    body = md.split("---", 2)[-1]
    assert body.count("*2024-05-") == 1


# --------------------------------------------------------------------------- #
# Extractor — JSON output bug fix
# --------------------------------------------------------------------------- #


def test_json_output_timestamp_uses_create_time(_extractor_args, _isolated_config_env):
    ext = ConversationExtractorV2(output_format="json", **_extractor_args)
    data = ext.generate_json_data(_metadata(), _msgs_with_timestamps())
    msgs = data["messages"]
    assert msgs[0]["timestamp"] == "2024-05-25T12:00:00Z"
    # 1716638460.5 → 2024-05-25T12:01:00.500000Z
    assert msgs[1]["timestamp"].startswith("2024-05-25T12:01:00")


def test_json_output_timestamp_null_when_disabled(
    _extractor_args, _isolated_config_env
):
    ext = ConversationExtractorV2(
        output_format="json", per_turn_timestamps=False, **_extractor_args
    )
    data = ext.generate_json_data(_metadata(), _msgs_with_timestamps())
    msgs = data["messages"]
    assert msgs[0]["timestamp"] is None
    assert msgs[1]["timestamp"] is None


# --------------------------------------------------------------------------- #
# process_messages + merge_continuations propagate create_time
# --------------------------------------------------------------------------- #


def _conv_with_timestamps():
    """Minimal mapping-graph conversation with user + assistant + 2 assistant
    continuation messages, each carrying create_time."""
    return {
        "id": "c1",
        "title": "t",
        "create_time": 1716638000.0,
        "update_time": 1716638600.0,
        "mapping": {
            "n0": {"id": "n0", "parent": None, "children": ["n1"], "message": None},
            "n1": {
                "id": "n1",
                "parent": "n0",
                "children": ["n2"],
                "message": {
                    "id": "n1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Q"]},
                    "weight": 1.0,
                    "create_time": 1716638400.0,
                    "update_time": 1716638400.0,
                },
            },
            "n2": {
                "id": "n2",
                "parent": "n1",
                "children": ["n3"],
                "message": {
                    "id": "n2",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["A1"]},
                    "weight": 1.0,
                    "create_time": 1716638460.0,
                    "update_time": 1716638460.0,
                },
            },
            "n3": {
                "id": "n3",
                "parent": "n2",
                "children": [],
                "message": {
                    "id": "n3",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["A2"]},
                    "weight": 1.0,
                    "create_time": 1716638480.0,
                    "update_time": 1716638480.0,
                },
            },
        },
        "current_node": "n3",
    }


def test_process_messages_propagates_create_time(_extractor_args, _isolated_config_env):
    ext = ConversationExtractorV2(**_extractor_args)
    conv = _conv_with_timestamps()
    raw = ext.backward_traverse(conv["mapping"], conv["current_node"], conv["id"])
    processed = ext.process_messages(raw, conv["id"], conv)
    user_msgs = [m for m in processed if m["role"] == "user"]
    asst_msgs = [m for m in processed if m["role"] == "assistant"]
    assert user_msgs and asst_msgs
    assert user_msgs[0].get("create_time") == 1716638400.0
    assert asst_msgs[0].get("create_time") == 1716638460.0


def test_merge_continuations_uses_first_segments_create_time(
    _extractor_args, _isolated_config_env
):
    ext = ConversationExtractorV2(**_extractor_args)
    msgs = [
        {"role": "user", "content": "Q", "create_time": 1716638400.0},
        {"role": "assistant", "content": "A1", "create_time": 1716638460.0},
        {"role": "assistant", "content": "A2", "create_time": 1716638480.0},
    ]
    merged = ext.merge_continuations(msgs)
    assert len(merged) == 2
    assistant = [m for m in merged if m["role"] == "assistant"][0]
    # Earliest assistant segment's start time — when the response began.
    assert assistant.get("create_time") == 1716638460.0
    assert "A1" in assistant["content"] and "A2" in assistant["content"]
