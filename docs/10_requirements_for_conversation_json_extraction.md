# Requirements package: ChatGPT Conversation.json Extraction Implementation

## Project Overview
Implement a Python extractor for ChatGPT's conversation.json format that produces clean, linear conversation transcripts with specific filtering and formatting requirements.

## Input
- `conversation.json` file in the `data/raw` folder
- `00_conversation_json_technical_reference.md`: Technical Reference "ChatGPT Conversation.json Complete Technical Reference v4.0"
-  This file (`10_requirements_for_conversation_json_extraction.md`) - requirements for implementation
- `11_requirements_for_convesation_json_output_generation.md` - additional requirements for implementing the output formatting with one .md file per conversation to be stored in `data/output_md` folder.

## Output Requirements

Outputs include combined json file and also individual markdown files (one markdown file per conversations), following the specifications and guidelines outlined below.

### 1. Metadata Object
Extract these fields exactly (if present):
```python
REQUIRED_METADATA = [
    'id',
    'conversation_id', 
    'title',
    'create_time',
    'update_time',
    'conversation_template_id',
    'gizmo_id',
    'gizmo_type',
    'memory_scope',
    'is_archived',
    'is_starred',
    'is_study_mode'
]
```

### 2. Message Extraction Rules

#### Traversal Method
- **Use BACKWARD traversal** from `current_node` to root
- This automatically excludes edited messages and branches
- See Technical Reference Section 7 for algorithm

#### Message Filtering

**INCLUDE:**
- ✅ User messages (role="user")
- ✅ Assistant messages (role="assistant")
- ✅ First system message IF `metadata.is_user_system_message == True` OR `content_type == "user_editable_context"`

**EXCLUDE:**
- ❌ Tool messages (role="tool")
- ❌ System messages except first user system message
- ❌ Messages where `metadata.is_visually_hidden_from_conversation == True`
- ❌ Content with `content_type == "model_editable_context"`
- ❌ Content with `content_type == "thoughts"` or `"reasoning_recap"`

### 3. Content Processing Rules

#### Code Blocks
```python
# From content_type == "code"
if content.get('content_type') == 'code':
    language = content.get('language', 'python')
    code_text = content.get('text', '')
    output = f"```{language}\n{code_text}\n```"

# From execution_output
if content.get('content_type') == 'execution_output':
    output_text = content.get('text', '')
    output = f"```output\n{output_text}\n```"

# From parts array (multimodal_text)
# Look for code in parts but SKIP if it's in a thoughts section
```

#### Audio Transcriptions
```python
# In parts array, look for:
if part.get('content_type') == 'audio_transcription':
    transcription_text = part.get('text', '')
    # Include this text in the user message
```

#### Images and Audio Files
```python
# For images: DO NOT include placeholders
if part.get('content_type') == 'image_asset_pointer':
    # Skip entirely - don't add [Image] placeholder

# For audio files: DO NOT include
if part.get('content_type') == 'audio_asset_pointer':
    # Skip entirely
```

#### DALL-E Generated Images

```python
# When detecting DALL-E generation:
if msg.get('recipient') == 'dalle.text2im':
    # This is a generation request
    # Extract the prompt from the JSON in parts
    
# For image results in tool responses:
if part.get('content_type') == 'image_asset_pointer':
    if 'dalle' in part.get('metadata', {}):
        # Format as: [Generated image: {gen_id}]
        # Or include the file-service URL for reference
```

#### Web Search Detection

```python
# Detect search initiation:
if (content.get('content_type') == 'code' and 
    content.get('language') == 'unknown' and
    msg.get('recipient') == 'browser'):
    # This is a web search command
    # Extract search query from text field
```



#### Citations
```python
# From message.metadata.citations
citations = message.get('metadata', {}).get('citations', [])
for citation in citations:
    # Extract and format:
    cite_type = citation.get('metadata', {}).get('type', 'unknown')
    cite_title = citation.get('metadata', {}).get('title', '')
    cite_url = citation.get('metadata', {}).get('url', '')
    
    # Format as: [Citation: {type}] {title} - {url}
    # Only include quoted text if it appears in the message body
```

#### Web Search URLs
```python
# Check multiple locations:
# 1. In citations (as above)
# 2. In content_type == "tether_quote": extract URL
# 3. In conversation.safe_urls array (if related to current message)
# 4. In content_type == "tether_browsing_display": check for URLs

# Compile unique list of URLs used for the response
```

#### File Upload Names
```python
# Look in message.metadata.attachments (if exists)
# Look in parts for asset_pointers with file references
# Extract filename only, format as: [File uploaded: filename.ext]

# DO NOT include file contents
# DO NOT fetch or process file data
```

### 4. Message Continuation Merging

```python
def should_merge(msg1, msg2):
    """Consecutive assistant messages should be merged"""
    return (
        msg1['author']['role'] == 'assistant' and
        msg2['author']['role'] == 'assistant' and
        msg1.get('recipient') == 'all' and
        msg2.get('recipient') == 'all' and
        # They are consecutive in the extracted list
    )

# When merging: concatenate content, preserve first message's metadata
```

## Implementation Algorithm

```python
def extract_conversation(conv_data):
    """Main extraction function"""
    
    # Step 1: Extract metadata
    metadata = extract_metadata(conv_data)
    
    # Step 2: Backward traversal
    messages = backward_traverse(
        conv_data['mapping'],
        conv_data.get('current_node')
    )
    
    # Step 3: Process messages
    processed = []
    system_prompt_added = False
    
    for msg in messages:
        # Skip if should be filtered
        if should_filter_message(msg):
            continue
            
        # Handle system prompt (once only)
        if msg['author']['role'] == 'system':
            if not system_prompt_added and is_user_system_prompt(msg):
                processed.append(format_system_prompt(msg))
                system_prompt_added = True
            continue
        
        # Process user/assistant messages
        if msg['author']['role'] in ['user', 'assistant']:
            content = extract_message_content(msg)
            if content:  # Only add if has content after filtering
                processed.append({
                    'role': msg['author']['role'],
                    'content': content,
                    'citations': extract_citations(msg),
                    'web_urls': extract_web_urls(msg),
                    'files': extract_file_names(msg)
                })
    
    # Step 4: Merge continuations
    final_messages = merge_continuations(processed)
    
    return {
        'metadata': metadata,
        'messages': final_messages
    }
```

## Key Decision Points

### 1. Backward Traversal Implementation
```python
def backward_traverse(mapping, current_node):
    """Reference: Technical Reference Section 7"""
    # If no current_node, find highest-weight leaf
    if not current_node or current_node not in mapping:
        leaves = [n for n in mapping.values() if not n.get('children')]
        if not leaves:
            return []
        current_node = max(leaves, key=lambda n: 
                          (n.get('message', {}).get('weight', 0),
                           n.get('message', {}).get('update_time', 0))).get('id')
    
    # Traverse backwards collecting messages
    messages = []
    node_id = current_node
    visited = set()
    
    while node_id and node_id not in visited:
        visited.add(node_id)
        node = mapping.get(node_id)
        if node and node.get('message'):
            messages.append(node['message'])
        node_id = node.get('parent') if node else None
    
    # Reverse to get chronological order
    return list(reversed(messages))
```

### 2. System Prompt Detection
```python
def is_user_system_prompt(message):
    """Determine if system message should be preserved"""
    # Check metadata flag
    if message.get('metadata', {}).get('is_user_system_message'):
        return True
    
    # Check content type
    content_type = message.get('content', {}).get('content_type')
    if content_type == 'user_editable_context':
        return True
    
    return False
```

### 3. Content Extraction by Type
```python
def extract_message_content(message):
    """Extract text based on content_type"""
    content = message.get('content', {})
    content_type = content.get('content_type')
    
    if content_type == 'text':
        return extract_from_parts(content.get('parts', []))
    elif content_type == 'code':
        # Format as code block
        lang = content.get('language', 'python')
        code = content.get('text', '')
        return f"```{lang}\n{code}\n```"
    elif content_type == 'multimodal_text':
        return extract_from_parts(content.get('parts', []))
    elif content_type == 'execution_output':
        output = content.get('text', '')
        return f"```output\n{output}\n```"
    elif content_type in ['tether_quote', 'sonic_webpage']:
        # Extract text content only
        return content.get('text', '')
    elif content_type == 'user_editable_context':
        # For system prompt
        profile = content.get('user_profile', '')
        instructions = content.get('user_instructions', '')
        return f"{profile}\n{instructions}".strip()
    else:
        return None  # Skip other types

def extract_from_parts(parts):
    """Process parts array"""
    text_parts = []
    for part in parts:
        if isinstance(part, str):
            text_parts.append(part)
        elif isinstance(part, dict):
            ct = part.get('content_type', '')
            if ct == 'audio_transcription':
                # Include transcription
                text_parts.append(part.get('text', ''))
            # Skip images, audio files
            # Skip other non-text content
    return ''.join(text_parts)
```

## Testing Checklist

- [ ] Backward traversal excludes edited messages
- [ ] System prompt appears once (if user-provided)
- [ ] Code blocks formatted with triple backticks
- [ ] Audio transcriptions included as text
- [ ] No image placeholders appear
- [ ] Citations extracted with metadata
- [ ] Assistant continuations merged
- [ ] Web URLs collected when available
- [ ] File names shown without content
- [ ] No reasoning/thoughts included
- [ ] All specified metadata fields preserved
- [ ] Empty assistant messages filtered out
- [ ] DALL-E images detected and formatted
- [ ] Web searches identified correctly
- [ ] Tool messages with weight 0.0 excluded
- [ ] Interrupted messages handled gracefully
- [ ] Multiple system branches handled (rare case)

## Edge Cases to Handle

1. **Missing current_node**: Find highest-weight leaf
2. **No user system prompt**: No system message in output
3. **Empty parts array**: Skip message
4. **Null timestamps**: Use 0 or omit from metadata
5. **No citations**: Empty citations array
6. **Split code blocks**: Merge if continuation pattern detected
7. **Empty assistant placeholders**: Skip messages with empty parts
8. **DALL-E image references**: Convert to markdown-friendly format
9. **Interrupted tool messages**: Check finish_details.type
10. **Web search commands**: Extract search query from code content
11. **Custom instruction wrapper text**: Strip "The user provided..." wrapper


## Expected JSON Output Format

```json
{
  "metadata": {
    "id": "conversation-uuid",
    "title": "Conversation Title",
    "create_time": 1234567890,
    "update_time": 1234567899,
    // ... other metadata fields
  },
  "messages": [
    {
      "role": "system",
      "content": "Custom instructions if any"
    },
    {
      "role": "user",
      "content": "User message text",
      "files": ["document.pdf", "image.jpg"]
    },
    {
      "role": "assistant",
      "content": "Response with ```python\ncode\n``` blocks",
      "citations": [
        {"type": "webpage", "title": "Title", "url": "https://..."}
      ],
      "web_urls": ["https://url1.com", "https://url2.com"]
    }
  ]
}
```

## Expected Markdown output format

Refer to the file `11_requirements_for_convesation_json_output_generation.md` (in the same folder) for the final output formatting in markdown.


## Implementation Notes

1. **Use the Technical Reference v4.0** for all field locations and structures
2. **Backward traversal is non-negotiable** - it provides exactly what's needed
3. **Be strict about filtering** - when in doubt, exclude
4. **Test with branched conversations** to ensure edits are excluded
5. **Preserve formatting** in code blocks and structured content

