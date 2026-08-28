# ChatGPT Export Schema Notes

## Important Schema Discoveries

This document captures important discoveries about the ChatGPT export format that differ from initial assumptions or documentation.

## Custom Instructions Storage (Discovered: 2025-01-13)

### Expected Location ❌
```json
{
  "content": {
    "content_type": "user_editable_context",
    "text": "The user provided the following information..."  // Expected here
  }
}
```

### Actual Location ✅
```json
{
  "content": {
    "content_type": "user_editable_context", 
    "text": ""  // Empty or "None"
  },
  "metadata": {
    "user_context_message_data": {  // Actually stored here!
      "about_user_message": "...",
      "about_model_message": "..."
    }
  }
}
```

**Impact**: 85%+ of conversations store custom instructions in metadata, not content field.

## Content Type Variations

### Newly Discovered Types (2025-01)
- `real_time_user_audio_video_asset_pointer` - Voice conversation with video
- `sonic_webpage` - Web reader content (includes URL and text)
- `tether_quote` - Web search citations
- `system_error` - System error messages

### Metadata-Only Content Types
Some content types have meaningful data only in metadata:
- `user_editable_context` - Custom instructions in metadata.user_context_message_data
- `model_editable_context` - Model context in metadata

## File Attachment Patterns

### Multiple Storage Locations
File references can appear in:
1. `message.metadata.attachments[]` - Primary location
2. `message.content.parts[].asset_pointer` - File upload references
3. `message.content.parts[].metadata.file_name` - Inline file metadata

## DALL-E Image Metadata

### Nested Structure Variation
DALL-E prompts can be in:
1. `metadata.dalle.prompt` - Nested dictionary format
2. `metadata.dalle_prompt` - Direct string format
3. Both may be None even when dalle-related fields exist

## Project Identification

### Conversation Template ID Pattern
- Project conversations: `conversation_template_id` starts with `g-p-`
- Custom GPTs: `gizmo_id` field present *(see 2026-06 schema change below)*
- Both fields may exist simultaneously

## 2026-06 Bulk Export Schema Change (Discovered: 2026-06-15)

### Bulk export bundle vs. live API have diverged

OpenAI updated the **bulk export** generator (Settings → Data controls →
Export data) between Feb 2026 and June 2026. The **per-conversation
live API** (`/backend-api/conversation/{id}`) was NOT updated and
continues to emit the older shape.

Concretely, the same conversation looks like this from the two sources:

| Field | Old single-file export (Feb 2026) | New 92-file export (Jun 2026) | Live API (Jun 2026) |
| --- | --- | --- | --- |
| `gizmo_id` (conv-level) | present, equals Custom GPT id | **absent** | present |
| `gizmo_type` | present | present | present |
| `conversation_template_id` | equals `gizmo_id` for Custom GPT convs | equals old `gizmo_id` | present |
| `metadata.gizmo_id` (per-msg) | present | present | present |
| `metadata.model_slug` (per-msg) | present | present | present |
| `blocked_urls`, `is_read_only`, `is_study_mode`, `owner`, `pinned_time`, `plugin_ids`, `safe_urls`, `sugar_item_id`, `sugar_item_visible` | present | **absent** | present |
| `mapping` (graph) | full | pre-trimmed: drops `role='system'` nodes with `is_visually_hidden_from_conversation=True` (already filtered downstream) | full |

The new export is a **strict subset** of the old shape — no new keys
appear. Both `gizmo_type` and `conversation_template_id` are retained
100% in the new bulk export (verified across all 9,134 conversations).

### Multi-file bundle layout

The 2026-06 Privacy Portal export first unpacks to nested ZIP files under
`User Online Activity/`, including `Conversations__*-chatgpt-*.zip`,
`Files__...zip`, and `Ads__...zip`. The conversation JSON shards are inside
the nested `Conversations__*-chatgpt-*.zip`; the Ads and Files archives are
not needed by the current Markdown extraction workflow.

After extracting the nested conversations ZIP, the bundle contains files named
`conversations-000.json` … `conversations-091.json` instead of one
`conversations.json`. Each file is a top-level JSON array. Files are
sharded by conversation id (clean disjoint, zero duplicate ids), not
chronologically — files 000 and 091 both span the user's full activity
date range. Every file holds 100 convs except the last (which holds the
remainder).

### Recovery for the missing `gizmo_id`

For Custom GPT conversations in the new export,
`conversation_template_id` carries the value that the old
`gizmo_id` had. Confirmed byte-identical across 5 cross-format spot
checks on two different gizmos (`g-F36RMaEje`, `g-dZUgwxUeJ`).

Recommended fallback for any code reading the bulk export:

```python
gizmo_id = conv.get("gizmo_id") or (
    conv.get("conversation_template_id")
    if conv.get("gizmo_type") == "gpt" else None
)
```

The condition `gizmo_type == 'gpt'` is what keeps `g-p-*` (project)
template ids from leaking into `gizmo_id`.

### Live-sync implications

Because the live API kept the old shape, `online_sync.fetch.fetch_full`
→ `OnlineRenderer` → `ConversationExtractorV2` works unchanged. The
fallback rule above is needed only when the extractor's input is a
fresh bulk export bundle.

### Nested conversation asset packaging

The nested `Conversations__*-chatgpt-*.zip` can contain more than
`chat.html`, `conversation_asset_file_names.json`, and the
`conversations-*.json` shards. It can also include conversation-side asset
payloads associated with uploaded or generated files.

Observed packaging variants:

- Older Privacy Portal bundles may store these assets with their apparent
  extensions, such as `.png`, `.jpg`, `.jpeg`, or `.md`.
- Newer Privacy Portal bundles may store many of these assets as `.dat` files.
  The `.dat` extension is opaque packaging, not a single file format. Magic
  bytes still identify ordinary payloads such as PNG, JPEG, PDF, ZIP-like, or
  text/Markdown data.
- `conversation_asset_file_names.json` can map opaque asset names back to
  user-visible filenames.

Do not infer asset type from the filename extension alone. Prefer signature
detection when tooling needs to classify these files.

Archive size is not a reliable proxy for conversation count. In observed
Privacy Portal exports, newer bundles with more conversations can be smaller
because the conversation-side asset payload is smaller. This appears to be
driven by packaging and deduplication changes, not by ZIP compression alone:
some assets that were duplicated inside both `Conversations__*.zip` and
`Files__*.zip` in older exports may only appear in one place in newer exports.
Likewise, duplicate identical assets inside the conversations archive may be
reduced.

For Markdown conversation extraction, the extractor primarily needs the
`conversations-*.json` shards. The asset files are ancillary unless a workflow
explicitly needs to restore or inspect referenced attachments.

### Internal web tool invocation traces

Older Privacy Portal conversation exports may include internal tool invocation
nodes in the active conversation graph. Web-search turns can appear as
assistant messages with `content_type: "code"` and a tool recipient such as
`web.run`; their content is JSON-like command data for operations such as
search, open, or find. Separate tool-result nodes may also be present.

Newer Privacy Portal exports may omit these internal invocation and tool-result
nodes from the conversation graph while retaining the final assistant answer
and derived source metadata, such as:

- citation markers in the rendered assistant text
- `metadata.safe_urls`
- `metadata.search_result_groups`
- `metadata.content_references`

In observed exports, the omitted web-tool command payloads were not recoverable
from other files in the full Privacy Portal archive. They appeared to be
removed rather than relocated.

This affects extracted Markdown in two ways:

- Older exports can expose internal web-tool command JSON as fenced code blocks
  if the extractor treats all assistant `content_type: "code"` messages as
  user-visible code.
- Raw message statistics such as `code_messages` can differ between exports of
  the same conversation because older exports count these internal tool-call
  nodes and newer exports may not contain them.

Extractor logic should treat assistant code messages with tool recipients
separately from user-visible code examples when the goal is a clean transcript.

## Message Continuations

### Graph Structure Indicators
- Consecutive assistant messages may be continuations
- `_graph_index` field (when present) validates true adjacency
- Merging required for complete responses

## Schema Evolution Tracking

The extractor includes `SchemaEvolutionTracker` to automatically detect:
- Unknown content types
- New author roles
- Unexpected metadata keys
- Novel part types in multimodal content

Output: `schema_evolution.log` in extraction directory

## Defensive Programming Requirements

### Common None/Null Patterns
Fields that frequently require None checking:
- `metadata` - Can be None entirely
- `metadata.dalle` - Can be None even with dalle in key name
- `content.parts` - Can be None, not just empty array
- `node.message` - Root nodes have None message
- `current_node` - May be missing, requiring fallback logic

## Recommendations for Future Development

1. **Always check metadata**: Many content types store primary data in metadata
2. **Defensive None handling**: Never assume nested fields exist
3. **Track schema evolution**: New content types appear regularly
4. **Test with real data**: Mock data often misses these nuances
5. **Log unknown patterns**: Helps identify schema changes early

## Version Compatibility

- Export format version: Not explicitly versioned by OpenAI
- Observed changes: Gradual schema evolution without breaking changes
- Backward compatibility: Code should check multiple locations for data

## Related Documentation

- [Custom Instructions Extraction](CUSTOM_INSTRUCTIONS_EXTRACTION.md) - Detailed implementation
- [Technical Reference](00_conversation_json_technical_reference.md) - Complete format specification
- [Implementation Learnings](20_implementation_learnings_and_documentation_gaps.md) - Additional discoveries
