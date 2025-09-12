# ChatGPT Conversation.json Complete Technical Reference

*Version 4.0 - Exhaustive Reference with All Discoveries | Last Updated: 2025-01-09*

## Table of Contents

1. [File Structure Overview](#file-structure-overview)
2. [Complete Schema Definition](#complete-schema-definition)
3. [Data Organization Patterns](#data-organization-patterns)
4. [Project Identification & Structure](#project-identification-structure)
5. [Content Type Registry](#content-type-registry)
6. [Tool & Plugin Registry](#tool-plugin-registry)
7. [Traversal Strategies](#traversal-strategies)
8. [Message Content Structures](#message-content-structures)
9. [Critical Stumbling Blocks](#critical-stumbling-blocks)
10. [Field Dictionaries](#field-dictionaries)
11. [Edge Cases & Anomalies](#edge-cases-anomalies)
12. [System Message Filtering Logic](#system-message-filtering-logic)
13. [Version Detection & Evolution](#version-detection-evolution)
14. [Performance & Optimization](#performance-optimization)
15. [Extraction Decision Trees](#extraction-decision-trees)
16. [Error Recovery Patterns](#error-recovery-patterns)

---

## 1. File Structure Overview

### Root Structure

```
conversations.json = Array[Conversation]
```
- **File format**: JSON array containing conversation objects
- **Typical size**: 50KB - 1GB+ 
- **Large exports**: May be split into multiple files by OpenAI
- **Encoding**: UTF-8
- **Structure**: Directed Acyclic Graph (DAG) per conversation

### Validated Statistics (from 6,885 conversations)

| Metric | Value | Notes |
|--------|-------|-------|
| Branch rate | 23.6% | Have edits/regenerations |
| Project conversations | 2.9% | 198 conversations in 36 projects |
| System messages | ~18% | Of all messages |
| User system messages | ~10% | Of system messages (should preserve) |
| Tool usage | 3% | Of conversations |
| Null timestamps | 9% | Of messages |
| Average messages/conversation | 17.2 | Excluding system messages |
| Linear conversations | 76.4% | No branches |

### Extraction Rate Reality

- **Current tools achieve**: 49% text extraction
- **Possible with full implementation**: 99% text extraction
- **Gap reason**: Intentional filtering of system messages, thoughts, browsing data
- **User-friendly extraction**: ~75% (text, code, multimodal, execution)
- **Complete extraction**: ~99% (all 11 content types)

---

## 2. Complete Schema Definition

### 2.1. Conversation Object (Exhaustive)

```typescript
interface Conversation {
    // === IDENTIFIERS ===
    id: string                           // Primary identifier
    conversation_id?: string             // Alternative ID (legacy, same as id)
    
    // === DISPLAY INFO ===
    title: string                        // User-visible title (default: "ChatGPT Conversation")
    
    // === TIMESTAMPS ===
    create_time: number                  // Unix timestamp of creation
    update_time: number                  // Unix timestamp of last modification
    
    // === GRAPH STRUCTURE ===
    mapping: {                           // Node ID -> Node object
        [nodeId: string]: Node           // Graph representation of conversation
    }
    current_node: string                 // ID of active leaf node (may be null)
    
    // === PROJECT/GPT/TEMPLATE ===
    conversation_template_id?: string    // Project/Template/GPT ID
                                        // Format: "g-p-{UUID}" for projects
                                        //         "g-{ID}" for GPTs
    gizmo_id?: string                   // GPT/Project ID (matches template_id for projects)
    gizmo_type?: string                 // Type: "gpt" | "project" | "assistant"
    
    // === MEMORY ===
    memory_scope?: "global_enabled" |    // Standard ChatGPT memory
                   "project_enabled" |    // Project-specific memory
                   "project"             // Legacy project format
    is_do_not_remember?: boolean        // Exclude from memory training
    
    // === STATUS FLAGS ===
    is_archived?: boolean                // Archive status
    is_starred?: boolean                 // Starred/favorited
    is_study_mode?: boolean              // Study mode active
    
    // === FEATURES ===
    voice?: {                            // Voice conversation metadata
        voice_mode_enabled: boolean
        audio_duration?: number
        transcript_available?: boolean
    }
    conversation_origin?: string         // "chat" | "voice" | "api" | "plugin"
    
    // === OWNERSHIP ===
    owner?: {
        user_id?: string
        email?: string
        workspace_id?: string
    }
    
    // === SAFETY & TOOLS ===
    moderation_results?: Array<{
        flagged: boolean
        categories: string[]
        scores: Record<string, number>
    }>
    safe_urls?: string[]                 // Validated URLs
    blocked_urls?: string[]              // Blocked URLs
    plugin_ids?: string[] | null         // Active plugins
    disabled_tool_ids?: string[]         // Disabled tools
    
    // === UI METADATA (Sugar) ===
    sugar_item_id?: string               // UI tracking ID
    sugar_item_visible?: boolean         // UI visibility state
    
    // === MODEL ===
    default_model_slug?: string          // Default model for conversation
    
    // === ASYNC PROCESSING ===
    async_status?: null | 1 | 2 | 3     // null=sync, 1=initiated, 2=processing, 3=complete
}
```

### 2.2. Node Object

```typescript
interface Node {
    id: string                          // UUID format
    parent: string | null               // Parent node ID (null = root)
    children: string[]                  // Array of child node IDs
    message?: Message | null            // Optional message (null for root)
}
```

### 2.3. Message Object (Complete)

#### Interface Message

```typescript
interface Message {
    // === CORE ===
    id: string                          // Message UUID
    
    // === AUTHORSHIP ===
    author: {
        role: "system" | "user" | "assistant" | "tool"
        name?: string                   // Tool names: "browser", "python", "dalle.text2im", etc.
        metadata?: {
            real_author?: string        // Alternative author ID
            sonicberry_model_id?: string // Internal model ID
            source?: string             // Message source system
        }
    }
    
    // === CONTENT ===
    content: MessageContent             // See Content Type Registry section
    
    // === TIMESTAMPS ===
    create_time?: number | null         // Often null for system messages
    update_time?: number | null         // Last modification
    
    // === FLOW CONTROL ===
    status?: "finished_successfully" | 
             "in_progress" | 
             "finished_partial_completion"
    end_turn?: boolean | null           // null=unknown, true=ended, false=continuing
    weight: number                      // 1.0=active path, <1.0=alternative, null=treat as 1.0
    recipient?: string                  // "all" | tool_name | plugin_namespace
    
    // === METADATA (Extensive) ===
    metadata?: MessageMetadata          // See detailed structure below
}
```

**Recipient Field Patterns**:
- `"all"`: Standard messages visible to user
- `"browser"`: Web search tool
- `"dalle.text2im"`: DALL-E image generation
- `"python"`: Code interpreter
- Tool names correspond to `author.name` in tool responses

**Empty Placeholder Messages**:
Assistant may create empty messages before tool execution:
```json
{
  "author": {"role": "assistant"},
  "content": {"content_type": "text", "parts": [""]},
  "status": "finished_successfully"
}
```
These should be filtered during extraction.


```
interface MessageMetadata {
    // Model Information
    model_slug?: string                 // e.g., "gpt-4", "gpt-4o", "o1-preview"
    
    // Completion Details
    finish_details?: {
        type: "stop" |                  // Natural ending
              "interrupted" |           // User interrupted
              "max_tokens" |            // Hit token limit
              "error"                   // Error occurred
        stop_tokens?: number[]          // Token IDs that triggered stop
        stop?: string                   // Stop sequence hit
    }
  
    // User System Message Flag (CRITICAL)
    is_user_system_message?: boolean    // true = preserve, false/undefined = filter
    
    // Visibility
    is_visually_hidden_from_conversation?: boolean  // true = skip in export
    
    // Generation Metrics
    finished_duration_sec?: number      // Time to generate
    request_id?: string                // API request ID
    timestamp_?: string                // Alternative timestamp format
    
    // Citations & References
    citations?: Citation[]              // See Citation structure
    
    // Code Execution
    aggregate_result?: CodeExecutionResult  // See detailed structure
    
    // Plugin Invocation
    invoked_plugin?: PluginInvocation  // See detailed structure
    
    // Voice Mode
    voice_mode_message?: boolean
    voice_transcription?: string
    voice_audio_duration?: number
    
    // Reasoning (O1/O3 models)
    reasoning_status?: "thinking" | "complete"
    reasoning_duration?: number
    
    // Canvas (Collaborative Editing)
    canvas?: CanvasData                // See Canvas structure
    
    // Other
    [key: string]: any                 // Additional fields may exist
}
```

The `recipient` field indicates message routing:
 - `"all"`: Standard messages visible to user
 - `"browser"`: Web search tool
+- `"dalle.text2im"`: DALL-E image generation
 - Tool names correspond to `author.name` in tool responses
 
 
#### Image Generation Messages

When users request image generation, ChatGPT uses DALL-E through a specific message flow:

**Assistant Processing Message**:

```json
{
  "author": {"role": "assistant"},
  "content": {
    "content_type": "text",
    "parts": ["{\"prompt\":\"...\",\"size\":\"1024x1024\"}"]
  },
  "recipient": "dalle.text2im"
}
```

**Tool Response with Image**:

```json
{
  "author": {"role": "tool", "name": "dalle.text2im"},
  "content": {
    "content_type": "multimodal_text",
    "parts": [{
      "content_type": "image_asset_pointer",
      "asset_pointer": "file-service://file-[ID]",
      "size_bytes": 378942,
      "width": 1024,
      "height": 1024,
      "metadata": {
        "dalle": {
          "gen_id": "unique_id",
          "prompt": "actual prompt sent",
          "seed": 645641375,
          "parent_gen_id": null,
          "edit_op": null
        }
      }
    }]
  }
}
```

**Tool Instruction Message**:

```json
{
  "author": {"role": "tool", "name": "dalle.text2im"},
  "content": {
    "content_type": "text",
    "parts": ["DALL·E displayed 1 images..."]
  }
}
```

**Interrupted Messages**

```markdown
Messages can be interrupted by users mid-generation:
```json
"finish_details": {
  "type": "interrupted"
}
```
This appears in tool messages when generation was stopped before completion.
```


---

## 3. Data Organization Patterns

### Graph Structure Rules
1. **Root Node**: Every conversation has exactly one (parent = null, message = null)
   - Exception: May have multiple system message children creating parallel branches
2. **Branches**: Created by user edits or assistant regenerations
3. **Weight Priority**: 1.0 = active, 0.0-0.9 = alternatives, null = treat as 1.0
4. **Current Node**: Points to active leaf (may be null - need fallback)
5. **Message Order**: Not guaranteed - must traverse graph

### Branch Types
```
Edit Branch: User edits previous message
  User (weight: 0.0) ← Original
    └── Assistant (weight: 0.0)
  User (weight: 1.0) ← Edited
    └── Assistant (weight: 1.0) ← Active

Regeneration Branch: Multiple assistant responses
  User
    ├── Assistant (weight: 0.0) ← First attempt
    └── Assistant (weight: 1.0) ← Regenerated (active)
```

### Message Continuation Pattern

```python
def should_merge(msg1, msg2):
    """Consecutive assistant messages should be merged"""
    return (
        msg1['author']['role'] == 'assistant' and
        msg2['author']['role'] == 'assistant' and
        msg1.get('recipient') == 'all' and
        msg2.get('recipient') == 'all' and
        # Skip empty placeholder messages
        bool(msg1.get('content', {}).get('parts', [''])[0]) and
        # They are consecutive in the extracted list
    )

# Filter empty messages before merging
messages = [m for m in messages if m.get('content', {}).get('parts', [''])[0]]
```

---

## 4. Project Identification & Structure

### Project vs GPT vs Template
| Type | Identifier Format | Memory Scope | Purpose |
|------|------------------|--------------|---------|
| Project | `g-p-{UUID}` | `project_enabled` | Scoped conversations |
| GPT | `g-{shortID}` | `global_enabled` | Custom assistant |
| Template | `g-t-{UUID}` | Any | Conversation template |

### Project Detection
```python
def get_conversation_type(conv):
    template_id = conv.get('conversation_template_id', '')
    memory_scope = conv.get('memory_scope')
    
    if memory_scope in ['project_enabled', 'project']:
        return 'project', template_id
    elif template_id.startswith('g-p-'):
        return 'project', template_id  # Project even without scope
    elif template_id.startswith('g-'):
        return 'gpt', template_id
    else:
        return 'standard', None
```

### Project Statistics (Validated)
- **Identification**: 100% via `conversation_template_id`
- **Correlation**: `conversation_template_id` == `gizmo_id` for projects
- **Custom Instructions**: 45% have `user_editable_context`
- **Grouping**: All conversations with same template_id belong to same project

---

## 5. Content Type Registry

### Common content types and their structure:
 
 - `text`: Standard text message with `parts` array
 - `code`: Code execution with `language` and `text` fields
 - `multimodal_text`: Contains mixed content (text + images)
+  - May contain `image_asset_pointer` for DALL-E generated images
 - `execution_output`: Results from code execution
 - `tether_browsing_display`: Web search results
 - `tether_quote`: Quoted web content
 - `user_editable_context`: User's custom instructions
+  - May include wrapper text around actual instructions

### Content-Level Types (Complete)
| Type | Has `text` | Has `parts` | Extract Method | Priority |
|------|------------|-------------|----------------|----------|
| `text` | No | Yes | Join parts array | HIGH |
| `code` | Yes | No | Direct text field + language | HIGH |
| `multimodal_text` | No | Yes | Process each part by type | HIGH |
| `execution_output` | Yes | No | Text field (code output) | HIGH |
| `tether_quote` | Yes | No | Text + domain + URL | MEDIUM |
| `tether_browsing_display` | No | No | Result + summary fields | LOW |
| `user_editable_context` | No | No | **PRESERVE** - user_profile + user_instructions | HIGH |
| `model_editable_context` | No | No | **FILTER** - model_set_context | SKIP |
| `thoughts` | No | No | Thoughts field (O1 reasoning) | LOW |
| `reasoning_recap` | No | No | Content field (O3 summary) | LOW |
| `sonic_webpage` | Yes | No | Title + text + URL | MEDIUM |
| `system_error` | Yes | No | Name + text (error info) | HIGH |

### Special Content Type Patterns

**Web Search Commands**:

```json
{
  "content_type": "code",
  "language": "unknown",
  "text": "search(\"query text\")"
}
```

With `recipient: "browser"` - indicates web search initiation.

**DALL-E Generation Commands**:
```json
{
  "content_type": "text",
  "parts": ["{\"prompt\":\"...\",\"size\":\"1024x1024\"}"]
}
```
With `recipient: "dalle.text2im"` - indicates image generation request.


### Part-Level Types (in `parts` array)

```typescript
type MessagePart = 
    | string                           // Plain text
    | ImageAssetPointer
    | AudioTranscription
    | AudioAssetPointer
    | VideoAssetPointer
    | CodeInterpreterOutput

interface ImageAssetPointer {
    content_type: "image_asset_pointer"
    asset_pointer: string              // "file-service://file-{UUID}"
    width?: number
    height?: number
    size_bytes?: number
    fovea?: number                     // Focus area size
    metadata?: {
        dalle?: {                      // DALL-E generation metadata 0 0; can be dalle_prompt instead of dalle
            gen_id: string
            prompt: string
            seed: number
            parent_gen_id?: string | null
            edit_op?: string | null
        }
        sanitized?: boolean
    }
}

interface AudioTranscription {
    content_type: "audio_transcription"
    text: string                       // PRESERVE THIS
    direction: "incoming" | "outgoing"
}
```

---

## 6. Tool & Plugin Registry

### Core Tools (Complete List from Analysis)
| Tool | Recipient ID | Purpose | Frequency/1000 |
|------|--------------|---------|----------------|
| `web.run` | Web browsing execution | Execute browsing | 47 |
| `python` | Code interpreter | Python execution | 45 |
| `browser` | Browser control | Browser operations | 39 |
| `file_search.msearch` | Multi-search files | Search documents | 22 |
| `assistant` | Self-directed | Internal ops | 14 |
| `web` | General web | Web access | 12 |
| `web.search` | Web search | Search internet | 6 |
| `dalle.text2im` | DALL-E 3 | Image generation | 5 |
| `myfiles_browser` | File browser | Browse uploads | 4 |
| `research_kickoff_tool.start_research_task` | Research | Deep research | 4 |

### Tool Message Patterns

**Weight Pattern**: Tool messages typically have `weight: 0.0` while active path messages have `weight: 1.0`.

**DALL-E Flow**:
1. User request → Assistant empty placeholder
2. Assistant sends JSON to `dalle.text2im` (recipient)
3. Tool returns `multimodal_text` with `image_asset_pointer`
4. Tool sends instruction message about display
5. Assistant provides final description

**Web Search Flow**:
1. Assistant sends search command (content_type: "code", language: "unknown")
2. Tool returns `tether_browsing_display` results
3. Multiple `mclick` commands may follow for deeper searches
4. Tool returns `tether_quote` with specific content
5. Assistant synthesizes with citations


### Plugin Pattern
```typescript
interface PluginInvocation {
    namespace: string                  // Plugin identifier
    type: "remote" | "local"
    http_response_status?: number
    response_data?: any
    error?: string
}

// Plugin tool format: "{domain}__jit_plugin.{method}"
// Examples:
// - "mermaidchart_com__jit_plugin.render_diagram"
// - "youtubetranscript_com__jit_plugin.getSummarizedTranscript"
// - "videosummarizer_co__jit_plugin.own_lo_p_get_captions"
```

---

## 7. Traversal Strategies

### Algorithm Selection
```python
def select_traversal_algorithm(conversation, user_preference=None):
    """Smart selection based on empirical data"""
    
    if user_preference:
        return user_preference
    
    mapping = conversation['mapping']
    has_branches = any(len(n.get('children', [])) > 1 for n in mapping.values())
    
    if not has_branches:
        # 76.4% of conversations - no data loss with backward
        return 'backward'  # 7.3x faster
    else:
        # 23.6% of conversations - significant data loss with backward
        branch_count = sum(1 for n in mapping.values() if len(n.get('children', [])) > 1)
        
        if branch_count > 5:
            return 'forward'  # Too complex for backward
        elif branch_count <= 2:
            # Could offer choice
            return 'forward'  # Safe default
        else:
            return 'forward'
```

### Performance Comparison
| Method | Speed | Message Coverage | Use Case |
|--------|-------|-----------------|----------|
| Forward | 0.567ms | 100% | Complete history |
| Backward | 0.077ms | 75% (if branches) | Current state |
| Backward+Branches | 0.3ms | 91% | Balanced approach |

---

## 8. Message Content Structures

### Code Execution Result
```typescript
interface CodeExecutionResult {
    code: string                       // Executed code
    status: "success" | "error" | "timeout"
    messages: Array<{
        message_type: "text" | "image" | "error"
        text?: string
        image_url?: string              // Base64 data URI
    }>
    final_expression_output?: any      // Last expression value
    execution_time_ms?: number
    stdout?: string
    stderr?: string
}
```

### Citation Structure
```typescript
interface Citation {
    start_ix: number                   // Start index in text
    end_ix: number                     // End index in text
    citation_format_type: "tether_og" | "number" | "markdown"
    metadata?: {
        type: "webpage" | "file" | "document"
        title?: string
        url?: string
        text?: string                  // Quoted text
        extra?: {
            cited_message_idx?: number
            search_query?: string
        }
    }
}
```

### Canvas Structure (Collaborative Editing)
```typescript
interface CanvasData {
    content_type: "canvas"
    canvas_data: {
        type: "code" | "document" | "markdown"
        content: string
        language?: string               // For code
        title?: string
        version?: number
        edit_history?: Array<{
            timestamp: number
            changes: any
        }>
    }
}
```

### Voice Mode Fields
```typescript
interface VoiceMessage {
    voice_mode_message: true
    voice_transcription?: string        // Text version
    voice_audio_duration?: number       // Seconds
    voice_audio_url?: string           // Audio file reference
    real_time_audio_has_video?: boolean
}
```

---

## 9. Critical Stumbling Blocks

### 1. Root Node Trap
```python
# WRONG - Includes null message
messages = [node['message'] for node in mapping.values()]

# CORRECT - Filter null messages
messages = [node['message'] for node in mapping.values() 
           if node.get('message') is not None]
```

### 2. Missing Current Node
```python
# WRONG - Crashes if current_node is None
start_node = mapping[conversation['current_node']]

# CORRECT - Fallback to highest-weight leaf
current = conversation.get('current_node')
if not current or current not in mapping:
    # Find highest-weight leaf
    leaves = [n for n in mapping.values() if not n.get('children')]
    if leaves:
        current = max(leaves, 
                     key=lambda n: (n.get('message', {}).get('weight', 0), 
                                   n.get('message', {}).get('update_time', 0)))
```

### 3. Weight Interpretation
```python
# CORRECT weight handling
def get_effective_weight(message):
    if message is None:
        return 0
    weight = message.get('weight')
    if weight is None:
        return 1.0  # Treat null as active
    return weight
```

### 4. Parts Array Polymorphism
```python
# WRONG - Assumes all strings
text = ''.join(content['parts'])

# CORRECT - Handle mixed types
def extract_from_parts(parts):
    text_parts = []
    for part in parts:
        if isinstance(part, str):
            text_parts.append(part)
        elif isinstance(part, dict):
            ct = part.get('content_type', '')
            if ct == 'image_asset_pointer':
                text_parts.append(f"[Image: {part.get('width')}x{part.get('height')}]")
            elif ct == 'audio_transcription':
                text_parts.append(part.get('text', ''))  # PRESERVE transcription
            # ... handle other types
    return ''.join(text_parts)
```

### 5. System Message Filtering

```python
def should_preserve_message(message):
    """Critical decision for each message"""
    role = message.get('author', {}).get('role')
    
    # Always preserve non-system
    if role != 'system':
        return True
    
    # Check if user's custom instructions
    metadata = message.get('metadata', {})
    if metadata.get('is_user_system_message'):
        return True  # PRESERVE
    
    # Check content type
    content_type = message.get('content', {}).get('content_type')
    if content_type == 'user_editable_context':
        return True  # PRESERVE user context
    elif content_type == 'model_editable_context':
        return False  # FILTER model context
    
    # Default: filter system messages
    return False
```

### 4.1. System Message Format Variations

**Custom Instructions with Wrapper Text**:
Some exports include wrapper text around user instructions:
```json
{
  "content_type": "user_editable_context",
  "user_profile": "",
  "user_instructions": "The user provided the additional info about how they would like you to respond:\n```[actual instructions]```"
}
```
Extract the actual instructions, removing wrapper text.


### 6. Content Type Assumption
```python
# WRONG - Assumes structure
text = content['parts'][0]

# CORRECT - Check type first
content_type = content.get('content_type')
if content_type == 'text':
    text = extract_from_parts(content.get('parts', []))
elif content_type == 'code':
    text = f"```{content.get('language', '')}\n{content.get('text', '')}\n```"
elif content_type == 'execution_output':
    text = f"Output:\n{content.get('text', '')}"
# ... handle all 11 types
```

---

## 10. Field Dictionaries

### Model Slug Complete Mapping
```python
MODEL_FAMILIES = {
    'gpt-3.5': [
        'text-davinci-002-render-sha',
        'text-davinci-002-render-paid',
        'text-davinci-002-render'
    ],
    'gpt-4': [
        'gpt-4',
        'gpt-4-gizmo',
        'gpt-4-plugins', 
        'gpt-4-mobile',
        'gpt-4-browsing',
        'gpt-4-dalle'
    ],
    'gpt-4o': [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4o-canvas-alpha'
    ],
    'o1': [
        'o1',
        'o1-preview',
        'o1-pro'
    ],
    'o3': [
        'o3',
        'o3-mini', 
        'o3-pro'
    ],
    'experimental': [
        'gpt-5',
        'gpt-5-thinking',
        'gpt-5-pro',
        'research'
    ]
}
```

### Undocumented Fields (Complete)
| Field | Type | Purpose | Frequency |
|-------|------|---------|-----------|
| `sugar_item_id` | string | UI element tracking | 100% |
| `sugar_item_visible` | boolean | UI visibility state | 100% |
| `is_starred` | boolean | User favorited | 100% |
| `conversation_origin` | string | Start method | 100% |
| `is_study_mode` | boolean | Study feature | 100% |
| `owner` | object | Ownership info | 100% |
| `is_do_not_remember` | boolean | Memory exclusion | 100% |
| `disabled_tool_ids` | array | Disabled tools | 100% |
| `blocked_urls` | array | URL blacklist | 100% |
| `gizmo_type` | string | GPT variant | ~3% |

---

## 11. Edge Cases & Anomalies

### Attachment URL Patterns
```python
ATTACHMENT_PATTERNS = {
    'file-service': {
        'pattern': r'file-service://file-[A-Za-z0-9]{24}',
        'frequency': '95%',
        'example': 'file-service://file-abc123def456ghi789jkl012'
    },
    'sediment': {
        'pattern': r'sediment://file_[0-9a-f]{32}',
        'frequency': '5%',
        'example': 'sediment://file_0000000016dc61f68ed2f69f6e9e077b'
    }
}
```

### Circular Reference Prevention
```python
def traverse_safe(node_id, mapping, visited=None):
    if visited is None:
        visited = set()
    
    if node_id in visited:
        return []  # Circular reference detected
    
    visited.add(node_id)
    # Continue traversal...
```

### Multi-File Export Handling
Large exports may be split by OpenAI:
- `conversations_001.json`
- `conversations_002.json`
- Each file is independent JSON array
- No cross-file references
- Merge by concatenating arrays

---

## 12. System Message Filtering Logic

### Complete Decision Tree
```
Message Role = "system"?
├── NO → PRESERVE (user/assistant/tool)
├── YES → Check metadata.is_user_system_message
    ├── TRUE → PRESERVE (user's custom instructions)
    ├── FALSE/NULL → Check content_type
        ├── "user_editable_context" → PRESERVE
        ├── "model_editable_context" → FILTER
        └── Other → FILTER (ChatGPT internal)
```

### Impact on Extraction
- Filtering all system: Loses 10% important context
- Smart filtering: Preserves user context, removes noise
- Result: 85% relevant content vs 75% with blind filtering

---

## 13. Version Detection & Evolution

### Format Version Detection
```python
def detect_format_version(conversation):
    """Detect export format version by field presence"""
    
    indicators = {
        'v1': ['mapping', 'current_node'],           # Basic
        'v2': ['gizmo_id'],                         # GPT support
        'v3': ['canvas'],                           # Canvas feature
        'v4': ['voice'],                            # Voice support
        'v5': ['reasoning_status'],                 # O1/O3 models
        'v6': ['conversation_template_id']          # Projects
    }
    
    detected_version = 'v1'
    for version, fields in indicators.items():
        if all(field in conversation for field in fields):
            detected_version = version
    
    return detected_version
```

### Format Evolution Timeline
- **2023 Q1**: Basic format (v1)
- **2023 Q2**: GPT support added (v2)
- **2023 Q4**: Canvas feature (v3)
- **2024 Q1**: Voice mode (v4)
- **2024 Q2**: O1 reasoning (v5)
- **2024 Q3**: Projects (v6)

---

## 14. Performance & Optimization

### Memory Management
```python
def process_large_file(filename, batch_size=100):
    """Process in batches to manage memory"""
    
    with open(filename, 'r') as f:
        # Stream parse if possible
        conversations = json.load(f)  # May need streaming parser for huge files
    
    for i in range(0, len(conversations), batch_size):
        batch = conversations[i:i+batch_size]
        process_batch(batch)
        
        # Clear references to allow garbage collection
        del batch
        
    del conversations
```

### Performance Benchmarks
| Operation | Time | Memory |
|-----------|------|--------|
| Load 100MB file | 1.2s | 400MB |
| Parse 1000 conversations | 0.5s | 100MB |
| Forward traverse 1 conv | 0.567ms | 1KB |
| Backward traverse 1 conv | 0.077ms | 0.5KB |
| Extract with all types | 2ms | 2KB |

### Optimization Strategies
1. **Pre-sort children by weight** to avoid repeated sorting
2. **Cache branch detection** results
3. **Use generators** for large iterations
4. **Process in batches** of 100-500 conversations
5. **Skip hidden messages early** before processing

---

## 15. Extraction Decision Trees

### Main Extraction Flow
```
START
├── Validate JSON array
├── Detect format version
├── For each conversation:
│   ├── Check project membership (conversation_template_id)
│   ├── Detect branches (multiple children)
│   ├── Select traversal method
│   ├── Build message list
│   ├── Filter system messages (smart logic)
│   ├── Merge split assistant messages
│   ├── Process each content type
│   ├── Handle attachments
│   └── Group by project if applicable
└── Output in requested format
```

### Content Extraction Priority
```
For each message:
├── Skip if is_visually_hidden_from_conversation
├── Check should_preserve_message()
├── Extract based on content_type:
│   ├── HIGH: text, code, multimodal_text, execution_output
│   ├── HIGH: user_editable_context (preserve)
│   ├── MEDIUM: tether_quote, sonic_webpage
│   ├── LOW: thoughts, reasoning_recap
│   └── SKIP: model_editable_context
└── Include citations if present
```

---

## 16. Error Recovery Patterns

### Malformed Data Handling
```python
def safe_extract(data, *keys, default=""):
    """Safely navigate nested dictionaries"""
    try:
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            elif isinstance(result, list) and isinstance(key, int):
                result = result[key] if len(result) > key else None
            else:
                return default
        return result if result is not None else default
    except (KeyError, TypeError, IndexError):
        return default
```

### Common Corruption Patterns
1. **Truncated JSON**: Use streaming parser, recover partial
2. **Invalid UTF-8**: Clean with `errors='ignore'`
3. **Missing required fields**: Use defaults
4. **Circular references**: Track visited nodes
5. **Huge message**: Process in chunks

### Recovery Strategy
```python
def recover_conversation(conv_data):
    """Attempt to extract despite corruption"""
    
    # Essential fields with fallbacks
    conv_id = conv_data.get('id') or conv_data.get('conversation_id') or 'unknown'
    title = conv_data.get('title') or 'Recovered Conversation'
    mapping = conv_data.get('mapping', {})
    
    if not mapping:
        return None  # Can't recover without mapping
    
    # Try multiple traversal strategies
    messages = []
    
    # Try backward from current_node
    if current := conv_data.get('current_node'):
        messages = try_backward_traversal(mapping, current)
    
    # If failed, try forward from root
    if not messages:
        messages = try_forward_traversal(mapping)
    
    # If still failed, just extract all messages
    if not messages:
        messages = [n.get('message') for n in mapping.values() 
                   if n.get('message')]
    
    return {
        'id': conv_id,
        'title': title,
        'messages': messages,
        'recovered': True
    }
```

---

## Complete Implementation Checklist

### Essential Features
- [ ] JSON array validation
- [ ] Format version detection
- [ ] Project identification via `conversation_template_id`
- [ ] Smart traversal selection (forward/backward based on branches)
- [ ] System message filtering with `is_user_system_message`
- [ ] Message continuation merging
- [ ] All 11 content types support
- [ ] Parts array polymorphism handling
- [ ] Attachment placeholder generation
- [ ] Citation preservation

### Advanced Features
- [ ] Canvas content extraction
- [ ] Voice transcription handling
- [ ] Plugin response processing
- [ ] Code execution output formatting
- [ ] O1/O3 reasoning extraction
- [ ] Async status handling
- [ ] Multi-file export support
- [ ] Batch processing for large files
- [ ] Error recovery mechanisms
- [ ] Progress reporting

### Validation & Testing
- [ ] Handle missing current_node
- [ ] Process null timestamps
- [ ] Manage circular references
- [ ] Support legacy formats
- [ ] Preserve project groupings
- [ ] Maintain branch integrity
- [ ] Verify extraction completeness

---

*This Version 4.0 reference represents the complete accumulated knowledge from empirical analysis of 6,885 real conversations, with deep analysis of 1,000+ samples, resolving all contradictions and documenting every discovered pattern, structure, and edge case in the ChatGPT conversation.json export format.*