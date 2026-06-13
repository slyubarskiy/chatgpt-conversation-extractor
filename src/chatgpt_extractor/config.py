"""Configuration loading for the extractor.

Layered configuration (later sources override earlier ones):

1. Built-in defaults (``DEFAULTS`` in this module).
2. Optional YAML config file. Search order, first match wins:
   - Path passed via ``ConversationExtractorV2(config_path=...)`` /
     ``--config <path>`` CLI argument.
   - ``$CHATGPT_EXTRACTOR_CONFIG`` environment variable.
   - ``./chatgpt_extractor.yaml`` in the current working directory.
   - ``~/.config/chatgpt_extractor/config.yaml``.
3. Explicit constructor / CLI arguments — always win over file values.

Currently recognised keys:

- ``per_turn_timestamps`` (bool, default ``True``) — emit per-message
  timestamps as italic ISO-8601 UTC lines beneath each role heading in the
  markdown output, and surface the same value as the ``timestamp`` field in
  JSON output. When ``False``, output matches the pre-config behaviour
  (frontmatter conversation-level timestamps only).

- ``gpt_metadata`` (bool, default ``True``) — emit Custom GPT / per-turn
  model / plugin signals (``gizmo_id``, ``gizmo_type``, ``models_used`` in
  frontmatter; ``· model_slug``, ``· plugin:<ns>``, ``· gpt:<id>``
  appended to the per-turn timestamp line in markdown; ``model_slug`` /
  ``gizmo_id`` / ``plugin_namespace`` fields in JSON output). When
  ``False``, output matches the pre-config behaviour (only the
  conversation-level ``model:`` from ``default_model_slug``).

A malformed YAML file falls back silently to the built-in defaults — config
file errors should never block the extractor from running.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULTS: Dict[str, Any] = {
    "per_turn_timestamps": True,
    "gpt_metadata": True,
}


def _find_config_path(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Return the first existing config-file path in the search order, or None."""
    if explicit_path:
        p = Path(explicit_path).expanduser()
        return p if p.is_file() else None
    env = os.environ.get("CHATGPT_EXTRACTOR_CONFIG")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    for candidate in (
        Path.cwd() / "chatgpt_extractor.yaml",
        Path.home() / ".config" / "chatgpt_extractor" / "config.yaml",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_config(explicit_path: Optional[str] = None) -> Dict[str, Any]:
    """Return merged config (built-in defaults + first matching file, if any).

    A fresh dict is returned on each call so callers may mutate freely.
    """
    cfg: Dict[str, Any] = dict(DEFAULTS)
    path = _find_config_path(explicit_path)
    if path is None:
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        # Config file errors must not break the extractor; fall back silently.
        return cfg
    if isinstance(file_cfg, dict):
        cfg.update(file_cfg)
    return cfg
