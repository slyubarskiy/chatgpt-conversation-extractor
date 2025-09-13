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
- Custom GPTs: `gizmo_id` field present
- Both fields may exist simultaneously

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