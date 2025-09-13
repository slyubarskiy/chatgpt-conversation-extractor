# Custom Instructions Extraction Documentation

## Overview

This document describes how custom instructions (user personalization settings) are extracted from ChatGPT conversation exports and included in the generated markdown files.

## Schema Discovery

Through analysis of ChatGPT export data, we discovered that custom instructions are stored differently than initially expected:

### Location in Export Structure

Custom instructions appear in messages with `content_type: "user_editable_context"` but the actual text is NOT in the `content.text` field as one might expect.

```json
{
  "message": {
    "author": {"role": "system"},
    "content": {
      "content_type": "user_editable_context",
      "text": ""  // <-- Usually empty or "None"
    },
    "metadata": {
      "is_visually_hidden_from_conversation": true,
      "is_user_system_message": true,
      "user_context_message_data": {  // <-- Actual custom instructions here
        "about_user_message": "User's personal context...",
        "about_model_message": "Instructions for model behavior..."
      }
    }
  }
}
```

## Data Formats

### Current Format (85%+ of conversations)
- **Location**: `message.metadata.user_context_message_data`
- **Structure**: Dictionary with two keys:
  - `about_user_message`: User's personal information, preferences, context
  - `about_model_message`: Instructions for how the model should respond

### Legacy Format (older exports)
- **Location**: `message.content.text`
- **Structure**: Plain text with markers:
  ```
  The user provided the following information about themselves: [user info]
  The user provided the additional info about how they would like you to respond: [model instructions]
  ```

## Implementation

### Extraction Logic

The extractor checks both locations for maximum compatibility:

```python
def collect_message_statistics(self, messages, conv_id):
    # ... other statistics collection ...
    
    if content_type == 'user_editable_context':
        # 1. First check metadata (current format)
        metadata = msg.get('metadata', {})
        user_context_data = metadata.get('user_context_message_data')
        if user_context_data and isinstance(user_context_data, dict):
            instructions = {}
            if about_user := user_context_data.get('about_user_message'):
                instructions['about_user_message'] = about_user
            if about_model := user_context_data.get('about_model_message'):
                instructions['about_model_message'] = about_model
            if instructions:
                stats['custom_instructions'] = instructions
        
        # 2. Fall back to content.text (legacy format)
        elif text := content.get('text', ''):
            # Parse text format with markers
            # ... parsing logic ...
```

### Output Format

Custom instructions are included in the YAML frontmatter of generated markdown files:

```yaml
---
id: conversation-id
title: Conversation Title
created: "2025-09-10T19:46:48.557260Z"
updated: "2025-09-10T20:32:18.640054Z"
model: gpt-5
chat_url: "https://chatgpt.com/c/conversation-id"
total_messages: 18
code_messages: 2
message_types: code, text, user_editable_context
custom_instructions: |
  about_user_message: "User's personal context and preferences..."
  about_model_message: "Instructions for model behavior..."
---
```

## Metadata Fields

### Standard Metadata
- `id`: Conversation unique identifier
- `title`: Conversation title
- `created`: Creation timestamp (ISO format)
- `updated`: Last update timestamp (ISO format)
- `model`: Model used (e.g., gpt-4, gpt-5)
- `chat_url`: Direct link to conversation on ChatGPT

### Enhanced Metadata (Added in v2.1)
- `total_messages`: Count of messages after filtering and merging
- `code_messages`: Count of messages containing code
- `message_types`: Comma-separated list of content types
- `custom_instructions`: User's ChatGPT personalization settings

## Statistics

Based on analysis of real ChatGPT exports:
- **85%** of conversations with `user_editable_context` have custom instructions in metadata
- **0%** had custom instructions in `content.text` field in recent exports
- Custom instructions are typically **200-1000 characters** for each section

## Common Custom Instructions Patterns

### About User Message
Common elements include:
- Preferred name
- Professional role/title
- Areas of expertise
- Communication preferences
- Specific constraints (e.g., "Do not search online unless explicitly asked")

### About Model Message
Common elements include:
- Response structure preferences (bullets, headings)
- Tone and style (concise, thorough, technical)
- Formatting requirements
- Specific behaviors (e.g., "Always provide code examples")

## Troubleshooting

### Custom Instructions Not Appearing

1. **Check if conversation has custom instructions**:
   - Look for `user_editable_context` in `message_types` field
   - If present but `custom_instructions` is missing, the data may be empty

2. **Verify data location**:
   - Most exports store in `metadata.user_context_message_data`
   - Older exports may use `content.text` format

3. **Empty custom instructions**:
   - Some conversations have the structure but no actual content
   - This typically means custom instructions weren't set when conversation occurred

### Validation

To verify custom instructions are being extracted:

```bash
# Check a specific conversation
grep -A 10 "custom_instructions:" output/conversation.md

# Count conversations with custom instructions
grep -l "custom_instructions:" output/*.md | wc -l

# Find conversations with user_editable_context but no custom instructions
grep -l "message_types:.*user_editable_context" output/*.md | \
  xargs grep -L "custom_instructions:"
```

## Version History

- **v2.0**: Initial metadata enhancement with basic fields
- **v2.1**: Added custom instructions extraction from content.text
- **v2.1.1**: Fixed extraction to check metadata.user_context_message_data (current fix)

## Related Documentation

- [Technical Reference](00_conversation_json_technical_reference.md) - Complete JSON structure documentation
- [User Guide](USER_GUIDE.md) - General usage instructions
- [Architecture](ARCHITECTURE.md) - System design details