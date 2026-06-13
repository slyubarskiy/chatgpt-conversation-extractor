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

Pure functions only — no I/O, no state. The extractor wires the offline
batch path; ``online_sync/render.py`` wraps ``ConversationExtractorV2``
so the live sync inherits the same behaviour without importing this
module directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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
) -> str:
    """Build the dot-separated per-turn metadata suffix.

    Layout (each segment appended only when its source field is present;
    leading separator is included by the caller — this function returns
    an empty string when there's nothing to append)::

        " · <model_slug> · plugin:<namespace> · gpt:<id>"

    The ``gpt:<id>`` segment fires only when the per-message ``gizmo_id``
    differs from the conversation default — the @mention case. Suppressing
    it when they match prevents noisy repetition on every turn of a
    Custom-GPT conversation.

    Args:
        msg: The per-message dict assembled by ``process_messages``,
             expected to carry ``model_slug``, ``gizmo_id``, and
             ``plugin_namespace`` keys (any of which may be ``None``).
        conv_default_gizmo_id: The conversation-level ``gizmo_id`` (or
             ``None`` for default ChatGPT conversations).

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
        parts.append(f"gpt:{msg_gizmo}")

    if not parts:
        return ""
    return " · " + " · ".join(parts)
