"""GPT / Custom GPT / plugin metadata extraction from ChatGPT exports.

ChatGPT's export records three signals the offline extractor previously
dropped: the Custom GPT identity (`gizmo_id`, `gizmo_type`), the per-turn
model used (`metadata.model_slug` — often diverges from the conversation-
level `default_model_slug`), and per-turn plugin invocations
(`metadata.invoked_plugin`). This module pulls all three out into a shape
the markdown/JSON renderer can emit cheaply.

Design constraints (validated against a corpus scan of 8,248 conversations
spanning 2023-2026):

- `gizmo_type` takes three values: ``'gpt'`` (Custom GPT — 1482 convs),
  ``'snorlax'`` (project conversation — 1300 convs), or ``None``
  (default ChatGPT — 5466 convs). The extractor already emits
  ``project_id`` for the snorlax case from ``conversation_template_id``,
  so we **suppress `gizmo_id` for snorlax** to avoid duplicating it in
  frontmatter.
- 2023-era conversations sometimes lack ``default_model_slug``;
  per-message ``model_slug`` is the reliable source.
- 68 conversations have per-message ``gizmo_id`` without a conversation-
  level one — the genuine @mention pattern. The per-turn formatter
  surfaces those by emitting ``gpt:<id>`` when the per-message gizmo
  differs from the conversation default.
- ``invoked_plugin`` is a per-message dict with ``namespace`` /
  ``plugin_id`` / status. Only the namespace is included per-turn (the
  human-meaningful piece).

The ``load_gpt_names_xlsx`` helper is the one exception to "pure functions
only" — it reads a 2- or 3-column ``GPT_Names.xlsx`` sidecar produced by
``online_sync.gizmo_names_sync`` to map ``gizmo_id`` → human-readable name.
The extractor calls it once at construct time, and the resulting map is
threaded into frontmatter (``gpt_name:``) and the per-turn suffix
(``gpt:<Pretty Name>`` substitution). A missing or malformed sidecar
silently degrades to "id only" — the extractor must never crash on a bad
sidecar file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_conv_gpt_meta(conv: Dict[str, Any]) -> Dict[str, Any]:
    """Pull conversation-level GPT signals out of a raw ChatGPT export entry.

    Returns a dict the caller can merge into the conversation's frontmatter
    metadata. Keys that would carry no information (or that duplicate
    existing frontmatter, like ``gizmo_id`` for project conversations) are
    omitted entirely — no ``None`` values reach the output.

    Args:
        conv: One conversation dict as it appears in ``conversations.json``
              (or as ``OnlineRenderer`` reshapes from the live API). Must
              have a ``mapping`` field for per-message ``model_slug``
              collection; missing or non-dict mapping is tolerated.

    Returns:
        Dict with any subset of ``gizmo_id``, ``gizmo_type``, ``models_used``.
        Empty dict if none of the signals are present (default ChatGPT
        conversation with no exotic per-turn models recorded).
    """
    out: Dict[str, Any] = {}

    gizmo_type = conv.get("gizmo_type")
    gizmo_id = conv.get("gizmo_id")

    # Emit gizmo_type for any non-None value (gpt or snorlax).
    if gizmo_type:
        out["gizmo_type"] = gizmo_type

    # Custom GPT identity. Suppressed for snorlax (project) since
    # extractor.extract_metadata already emits project_id from the same
    # underlying conversation_template_id field.
    if gizmo_id and gizmo_type == "gpt":
        out["gizmo_id"] = gizmo_id

    # Distinct per-message model_slugs across the whole mapping (sorted
    # for deterministic frontmatter — helpful for git diffs).
    mapping = conv.get("mapping") or {}
    models_seen: set[str] = set()
    if isinstance(mapping, dict):
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            msg = node.get("message")
            if not isinstance(msg, dict):
                continue
            meta = msg.get("metadata") or {}
            slug = meta.get("model_slug")
            if slug:
                models_seen.add(slug)
    if models_seen:
        out["models_used"] = sorted(models_seen)

    return out


def extract_msg_gpt_signals(api_msg: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Pull per-message GPT signals (``model_slug``, ``gizmo_id``, plugin namespace).

    Run during ``process_messages`` and stashed on the per-message dict
    so the renderer can emit the per-turn suffix without re-walking the
    raw API shape later.

    Args:
        api_msg: A raw message dict from ``mapping[*].message`` — the same
                 shape the extractor already reads ``create_time`` etc.
                 from.

    Returns:
        Dict with keys ``model_slug``, ``gizmo_id``, ``plugin_namespace``;
        any subset may be ``None`` when not present in metadata.
    """
    meta = (api_msg or {}).get("metadata") or {}

    out: Dict[str, Optional[str]] = {
        "model_slug": meta.get("model_slug") or None,
        "gizmo_id": meta.get("gizmo_id") or None,
        "plugin_namespace": None,
    }

    invoked = meta.get("invoked_plugin")
    if isinstance(invoked, dict):
        ns = invoked.get("namespace")
        if ns:
            out["plugin_namespace"] = ns

    return out


def format_per_turn_suffix(
    msg: Dict[str, Any],
    conv_default_gizmo_id: Optional[str],
    names_map: Optional[Dict[str, str]] = None,
) -> str:
    """Build the dot-separated per-turn metadata suffix.

    Layout (each segment appended only when its source field is present;
    leading separator is included by the caller — this function returns
    an empty string when there's nothing to append)::

        " · <model_slug> · plugin:<namespace> · gpt:<name-or-id>"

    The ``gpt:`` segment fires only when the per-message ``gizmo_id``
    differs from the conversation default — the @mention case. Suppressing
    it when they match prevents noisy repetition on every turn of a
    Custom-GPT conversation.

    When ``names_map`` resolves the per-message ``gizmo_id`` to a human-
    readable name (e.g. "Trip Planner"), that name is substituted into the
    suffix in place of the opaque id. Unresolved ids fall back to the raw
    ``g-XXXX`` form so the signal is never lost.

    Args:
        msg: The per-message dict assembled by ``process_messages``,
             expected to carry ``model_slug``, ``gizmo_id``, and
             ``plugin_namespace`` keys (any of which may be ``None``).
        conv_default_gizmo_id: The conversation-level ``gizmo_id`` (or
             ``None`` for default ChatGPT conversations).
        names_map: Optional ``{gizmo_id: name}`` lookup table, typically
             ``ConversationExtractorV2._gpt_names`` loaded from
             ``GPT_Names.xlsx`` via ``load_gpt_names_xlsx``. ``None`` or
             an empty dict means "id-only", matching pre-feature output.

    Returns:
        The suffix string starting with `` · ``, or empty if there's
        nothing per-turn-specific to emit.
    """
    parts: List[str] = []

    model_slug = msg.get("model_slug")
    if model_slug:
        parts.append(model_slug)

    plugin_ns = msg.get("plugin_namespace")
    if plugin_ns:
        parts.append(f"plugin:{plugin_ns}")

    msg_gizmo = msg.get("gizmo_id")
    if msg_gizmo and msg_gizmo != conv_default_gizmo_id:
        # Substitute the human-readable name when available; fall back to
        # the raw id so the @mention signal is preserved even when the
        # sidecar hasn't been populated yet.
        label = (names_map or {}).get(msg_gizmo, msg_gizmo)
        parts.append(f"gpt:{label}")

    if not parts:
        return ""
    return " · " + " · ".join(parts)


def load_gpt_names_xlsx(path: Optional[str | Path]) -> Dict[str, str]:
    """Load ``GPT_Names.xlsx`` and return ``{gizmo_id: name}``.

    Accepts the same xlsx format ``online_sync.gizmo_names_sync.sync_gizmos``
    writes: header row in row 1, ``Gizmo ID`` in column 1, ``GPT Name``
    in column 2, optional ``Previous Name (review)`` in column 3 (ignored
    here). Whitespace is stripped from both columns.

    Designed to **never raise** — the extractor must keep running on a
    bad sidecar. Possible failure modes all degrade to "no name
    resolution available" with a single WARNING log entry:

    - ``path`` is ``None`` or the file does not exist → empty dict, no log.
    - File exists but ``openpyxl`` is not installed → empty dict, debug log
      (openpyxl is a transitive dep via the writer side; without it the
      reader simply skips name resolution).
    - File is corrupt / not an xlsx / has unexpected shape → empty dict,
      WARNING log.

    Args:
        path: Path to the xlsx file, or ``None``.

    Returns:
        ``{gizmo_id: name}``. Empty when the sidecar is missing,
        unreadable, or contains no usable rows.
    """
    if path is None:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        # Lazy import — openpyxl is not a hard runtime requirement when
        # the user opts out of name resolution by not providing a path.
        import openpyxl
    except ImportError:
        logger.debug("openpyxl not installed; skipping GPT name resolution from %s", p)
        return {}
    try:
        wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
        ws = wb.active
        names: Dict[str, str] = {}
        # Skip the header row; tolerate trailing blank rows that openpyxl
        # may emit in read_only mode.
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            gid = str(row[0]).strip() if row[0] is not None else ""
            name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            if gid and name:
                names[gid] = name
        wb.close()
    except Exception as exc:  # noqa: BLE001 — sidecar must never break extractor
        logger.warning(
            "GPT_Names.xlsx at %s could not be read (%s); proceeding without "
            "name resolution",
            p,
            exc,
        )
        return {}
    return names
