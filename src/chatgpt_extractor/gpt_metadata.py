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

import json as _json
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
        Dict with any subset of ``gizmo_id``, ``gizmo_type``,
        ``models_used``, ``conversation_origin``. Empty dict if none of
        the signals are present (default ChatGPT conversation with no
        exotic per-turn models recorded).
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

    # Provenance: where the conversation was created. Observed values so
    # far are ``"tpp"`` (third-party platform — the desktop app, which
    # runs "Work Mode" with local processing) and ``None`` for browser
    # conversations. Emitted verbatim as an opaque string rather than
    # validated against an enum: OpenAI adds values without notice, and
    # an unknown value is still more useful than a silently dropped one.
    #
    # Worth capturing because it is the ONLY reliable discriminator for
    # locally-processed conversations. The per-message ``model_slug``
    # ``-wm`` suffix correlates today (8/8 in the 2026-08-26 batch) but
    # is a naming convention, not a contract.
    #
    # Lives here, under the ``gpt_metadata`` flag, rather than as a
    # fourth config knob: its demonstrated use is Work Mode
    # identification, read together with ``models_used``, and
    # ``--no-gpt-metadata`` keeps its promise of pre-feature output.
    origin = conv.get("conversation_origin")
    if origin:
        out["conversation_origin"] = origin

    return out


_DEEP_RESEARCH_PINEAPPLE_URI = "connectors://connector_openai_deep_research"
_DEEP_RESEARCH_ATTRIBUTION_ID = "connector_openai_deep_research"


def extract_dr_report_message(api_msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """For a ``tool`` message, parse Deep Research widget state and return
    the embedded report message (the actual answer the user sees) or None.

    ChatGPT renders the Deep Research artifact on a *tool* message at
    ``metadata.chatgpt_sdk.widget_state``, which is a JSON-stringified
    dict whose ``report_message`` field carries the substantive
    markdown answer at ``content.parts[0]``. Empirically verified
    against the example conversation ``6a1cd528`` whose 37 KB
    *"# Detectability of VLESS Vision TCP Raw REALITY Under Chinese TLS
    Policing"* artifact lives nowhere else in the conversation document.

    The function is defensive: any of the following shapes returns
    ``None`` silently (a bad widget_state must not break the extractor):

    - ``api_msg`` is not a tool-role message
    - ``metadata.chatgpt_sdk.widget_state`` missing or not a string
    - ``widget_state`` not parseable as JSON
    - parsed dict missing ``report_message`` or with empty parts

    Returns the ``report_message`` dict on success — already shaped like
    a regular ChatGPT message (``author``, ``content``, ``create_time``,
    ``metadata``), ready for the extractor's standard processing pipeline
    to treat as an assistant turn.
    """
    if not isinstance(api_msg, dict):
        return None
    if (api_msg.get("author") or {}).get("role") != "tool":
        return None
    meta = api_msg.get("metadata") or {}
    sdk = meta.get("chatgpt_sdk") or {}
    ws_str = sdk.get("widget_state")
    if not isinstance(ws_str, str) or not ws_str:
        return None
    try:
        ws = _json.loads(ws_str)
    except (ValueError, TypeError):
        return None
    if not isinstance(ws, dict):
        return None
    report_msg = ws.get("report_message")
    if not isinstance(report_msg, dict):
        return None
    parts = ((report_msg.get("content") or {}).get("parts")) or []
    has_text = any(isinstance(p, str) and p for p in parts)
    if not has_text:
        return None
    return report_msg


def extract_conv_deep_research_meta(conv: Dict[str, Any]) -> Dict[str, Any]:
    """Detect whether a conversation invoked OpenAI's Deep Research connector.

    Deep Research turns have several per-message metadata markers — none
    of which reach the conversation-level fields — and the substantive
    artifact (the rendered research document) is deliberately suppressed
    from the conversation document via
    ``metadata.chatgpt_sdk_suppressed_response``. This makes Deep Research
    convs visually indistinguishable from short thinking-model chats in
    the extracted output: same ``model_slug``, same `models_used`, an
    assistant turn with empty ``parts``, no signal that the user actually
    spent compute on a substantial research task.

    Detection scans the mapping for any of the four markers (any one is
    sufficient):

    - ``metadata.deep_research_version`` — the explicit DR version flag,
      usually present on the user message that started the research.
    - ``metadata.chatgpt_sdk_suppressed_response == True`` — the "this
      body is not in the conversation document" flag on the final
      assistant turn.
    - ``metadata.chatgpt_sdk.resolved_pineapple_uri == "connectors://...
      connector_openai_deep_research"`` — the connector URI.
    - ``metadata.chatgpt_sdk.attribution_id == "connector_openai_deep_research"``
      — the explicit attribution string.

    Args:
        conv: One conversation dict (same shape as ``extract_conv_gpt_meta``
              consumes).

    Returns:
        ``{"deep_research": True, "deep_research_version": <int>}`` when
        detected; ``deep_research_version`` is omitted when the value
        wasn't found (some legacy DR convs lack the version field).
        Empty dict when the conversation is not Deep Research.
    """
    mapping = conv.get("mapping") or {}
    if not isinstance(mapping, dict):
        return {}

    detected = False
    version: Optional[Any] = None

    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        meta = msg.get("metadata") or {}

        v = meta.get("deep_research_version")
        if v is not None:
            detected = True
            # Use the first non-null value seen; in practice it's on the
            # initiating user message and consistent across the exchange.
            if version is None:
                version = v

        if meta.get("chatgpt_sdk_suppressed_response") is True:
            detected = True

        sdk = meta.get("chatgpt_sdk")
        if isinstance(sdk, dict):
            if sdk.get("resolved_pineapple_uri") == _DEEP_RESEARCH_PINEAPPLE_URI:
                detected = True
            if sdk.get("attribution_id") == _DEEP_RESEARCH_ATTRIBUTION_ID:
                detected = True

    if not detected:
        return {}

    out: Dict[str, Any] = {"deep_research": True}
    if version is not None:
        out["deep_research_version"] = version
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
    # Per-message metadata stores the conversation's gizmo context, which
    # for a project conversation is the *project* id (g-p-*). That belongs
    # in ``project_id`` frontmatter, not as a ``gpt:`` per-turn segment —
    # skipping those keeps the per-turn line about actual Custom GPT
    # @mentions only. Real @mentions carry a Custom GPT id (g-XXXX) and
    # are still emitted.
    if (
        msg_gizmo
        and msg_gizmo != conv_default_gizmo_id
        and not msg_gizmo.startswith("g-p-")
    ):
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
