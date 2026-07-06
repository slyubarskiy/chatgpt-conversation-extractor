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

- ``gpt_names_xlsx`` (str | None, default ``None``) — path to an xlsx
  sidecar mapping ``gizmo_id`` → human-readable name (produced by
  ``online_sync.gizmo_names_sync.sync_gizmos``). When set and the file is
  readable, frontmatter gains a ``gpt_name:`` field for Custom GPT
  conversations, and the per-turn ``gpt:<id>`` segment substitutes the
  human-readable name when known (falls back to the raw id otherwise).
  Missing file or unreadable workbook silently degrades to id-only output.

- ``web_urls`` (str | dict, default per-type map — see ``WEB_URLS_DEFAULT``)
  — per-source control over which URL-carrying metadata paths get
  extracted, and at what level of detail. Two YAML shapes accepted:

  1. Preset string — ``off | citations | rich``:
     - ``off``: skip all URL metadata (no ``**Citations:**``,
       ``**Sources:**`` or ``**Web Search URLs:**`` blocks).
     - ``citations``: only the existing ``**Citations:**`` block; all
       URL-only sources off. Leanest useful config for BM25/embedding
       indexers that want inline citation context but no URL bulk.
     - ``rich``: ``**Citations:**`` + a new ``**Sources:**`` block
       carrying title + snippet + attribution from
       ``search_result_groups`` and ``content_references``. URL-only
       sources off.
  2. Per-type map — explicit control:
     - ``citations``: ``off | minimal | rich`` — ``rich`` = existing
       Citations block behavior.
     - ``conv_safe_urls``: ``off | minimal`` — conv-level ``safe_urls``.
     - ``msg_safe_urls``: ``off | minimal`` — message-level ``safe_urls``.
     - ``search_result_groups``: ``off | minimal | rich``.
     - ``content_references``: ``off | minimal | rich``.

  Default preserves pre-PR-#17 behavior: citations rich, conv_safe_urls
  minimal, msg_safe_urls / search_result_groups / content_references off.
  ``supporting_websites`` is not a top-level config key — it only appears
  nested inside ``search_result_groups`` and ``content_references`` in
  real data and inherits its parent's level.

  Invalid preset names, unknown per-type keys, or invalid level values
  are logged and coerced back to the default for that key; the extractor
  never crashes on a bad config.

A malformed YAML file falls back silently to the built-in defaults — config
file errors should never block the extractor from running.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

logger = logging.getLogger(__name__)

# Level names accepted per-type. URL-only types silently downgrade "rich"
# to "minimal" at extraction time (there's no rich content to surface).
WEB_URLS_LEVELS = ("off", "minimal", "rich")

# Types that are URL-only in the data (no title/snippet available).
# Setting these to "rich" is not an error but degrades to "minimal".
WEB_URLS_URL_ONLY_TYPES = frozenset({"conv_safe_urls", "msg_safe_urls"})

# Rich-capable types — support the full off|minimal|rich range.
WEB_URLS_RICH_CAPABLE_TYPES = frozenset(
    {"citations", "search_result_groups", "content_references"}
)

# Complete set of valid top-level web_urls keys.
WEB_URLS_KEYS = WEB_URLS_URL_ONLY_TYPES | WEB_URLS_RICH_CAPABLE_TYPES

# Default per-type map, applied when the user sets no web_urls config.
# Matches pre-PR-#17 behavior byte-for-byte for existing rendered output:
# only citations rich (via the existing extract_citations path) and
# conv-level safe_urls minimal (via the existing conv_data.safe_urls path).
WEB_URLS_DEFAULT: Dict[str, str] = {
    "citations": "rich",
    "conv_safe_urls": "minimal",
    "msg_safe_urls": "off",
    "search_result_groups": "off",
    "content_references": "off",
}

# Preset shorthand strings, resolved to full per-type maps at load time.
# Users can write ``web_urls: rich`` in YAML instead of the explicit map.
WEB_URLS_PRESETS: Dict[str, Dict[str, str]] = {
    "off": {k: "off" for k in WEB_URLS_KEYS},
    "citations": {
        "citations": "rich",
        "conv_safe_urls": "off",
        "msg_safe_urls": "off",
        "search_result_groups": "off",
        "content_references": "off",
    },
    "rich": {
        "citations": "rich",
        "conv_safe_urls": "off",
        "msg_safe_urls": "off",
        "search_result_groups": "rich",
        "content_references": "rich",
    },
}

DEFAULTS: Dict[str, Any] = {
    "per_turn_timestamps": True,
    "gpt_metadata": True,
    "gpt_names_xlsx": None,
    "web_urls": dict(WEB_URLS_DEFAULT),
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


def _merge_config_over_defaults(
    defaults: Dict[str, Any], incoming: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge ``incoming`` YAML values onto a copy of ``defaults``.

    For flat keys (``per_turn_timestamps``, ``gpt_metadata``,
    ``gpt_names_xlsx``): standard ``dict.update`` semantics — the incoming
    scalar replaces the default.

    For a key whose default is a dict (currently only ``web_urls``): if the
    incoming value is also a dict, do a **shallow per-subkey merge** so
    partial user config (``web_urls: {citations: rich}``) preserves the
    other DEFAULTS-provided subkeys instead of dropping them. If the
    incoming value is not a dict (e.g. a preset string ``web_urls: rich``),
    it replaces the default wholesale — the caller is expected to resolve
    the preset later via ``_resolve_web_urls``.

    Constrained on purpose: only recurses when BOTH sides are dicts. Any
    other shape falls through to the flat ``dict.update`` behavior. This
    preserves back-compat for existing flat keys and avoids surprising
    deep-merge semantics elsewhere.
    """
    merged = dict(defaults)
    for k, incoming_v in incoming.items():
        default_v = merged.get(k)
        if isinstance(default_v, dict) and isinstance(incoming_v, dict):
            sub = dict(default_v)
            sub.update(incoming_v)
            merged[k] = sub
        else:
            merged[k] = incoming_v
    return merged


def _resolve_web_urls(
    raw: Any, *, log: Optional[logging.Logger] = None
) -> Dict[str, str]:
    """Coerce a raw ``web_urls`` value into a normalized per-type map.

    Accepts:
    - ``None`` → returns the built-in default map.
    - preset string (``off``, ``citations``, ``rich``) → returns
      ``WEB_URLS_PRESETS[preset]``. Unknown preset names log a warning
      and fall back to defaults.
    - per-type dict → merges onto defaults. Unknown keys logged and
      ignored; invalid values (e.g. ``citations: yes`` which YAML parses
      as ``True``) logged and coerced back to the default for that key.

    Any other shape (list, scalar, etc.) logs a warning and returns
    defaults. The extractor never crashes on a bad web_urls config.
    """
    _log = log or logger
    if raw is None:
        return dict(WEB_URLS_DEFAULT)
    if isinstance(raw, str):
        preset = raw.strip().lower()
        if preset in WEB_URLS_PRESETS:
            return dict(WEB_URLS_PRESETS[preset])
        _log.warning(
            "web_urls: unknown preset %r; valid presets are %s. Falling back to defaults.",
            raw,
            sorted(WEB_URLS_PRESETS.keys()),
        )
        return dict(WEB_URLS_DEFAULT)
    if not isinstance(raw, dict):
        _log.warning(
            "web_urls: expected preset string or per-type dict, got %s. Falling back to defaults.",
            type(raw).__name__,
        )
        return dict(WEB_URLS_DEFAULT)
    resolved = dict(WEB_URLS_DEFAULT)
    for k, v in raw.items():
        if k not in WEB_URLS_KEYS:
            _log.warning(
                "web_urls: unknown per-type key %r; valid keys are %s. Ignoring.",
                k,
                sorted(WEB_URLS_KEYS),
            )
            continue
        # YAML 1.1 coerces ``off`` to ``False`` — accept it as equivalent
        # to ``"off"`` so users can write ``citations: off`` unquoted.
        # Bool ``True`` has no obvious level mapping (minimal vs rich),
        # so warn + fall back.
        if isinstance(v, bool):
            if v is False:
                resolved[k] = "off"
                continue
            _log.warning(
                "web_urls[%s]: got bool True; ambiguous — quote the level "
                "explicitly (e.g. \"minimal\" or \"rich\"). Falling back to "
                "default %r.",
                k,
                WEB_URLS_DEFAULT[k],
            )
            continue
        if not isinstance(v, str) or v.strip().lower() not in WEB_URLS_LEVELS:
            _log.warning(
                "web_urls[%s]: expected one of %s, got %r. Falling back to default %r.",
                k,
                list(WEB_URLS_LEVELS),
                v,
                WEB_URLS_DEFAULT[k],
            )
            continue
        resolved[k] = v.strip().lower()
    return resolved


def load_config(explicit_path: Optional[str] = None) -> Dict[str, Any]:
    """Return merged config (built-in defaults + first matching file, if any).

    A fresh dict is returned on each call so callers may mutate freely.
    ``web_urls`` values are returned in their raw shape (preset string or
    dict) — the extractor calls ``_resolve_web_urls`` at construct time
    to normalize into the per-type map used at extraction.
    """
    cfg: Dict[str, Any] = dict(DEFAULTS)
    # web_urls' default is a mutable dict — clone it so the caller can't
    # accidentally mutate the module-level WEB_URLS_DEFAULT via cfg["web_urls"].
    cfg["web_urls"] = dict(WEB_URLS_DEFAULT)
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
        cfg = _merge_config_over_defaults(cfg, file_cfg)
    return cfg
