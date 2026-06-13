# ChatGPT Conversation Extractor - Technical Reference

## Table of Contents
1. [API Reference](#api-reference)
2. [Data Structures](#data-structures)
3. [Content Type Registry](#content-type-registry)
4. [Configuration](#configuration)
5. [Extension Points](#extension-points)

## API Reference

### Main Module: `chatgpt_extractor`

#### Class: ConversationExtractorV2

```python
class ConversationExtractorV2:
    """Enhanced extractor with schema tracking, multi-format output, and
    per-message metadata enrichment."""

    def __init__(
        self,
        input_file: Optional[str] = None,
        output_dir: Optional[str] = None,        # required (Optional typing only for arg ordering)
        output_format: str = "markdown",          # 'markdown' | 'json' | 'both'
        json_format: str = "multiple",            # 'multiple' | 'single'
        markdown_dir: Optional[str] = None,       # override md/ subdir
        json_dir: Optional[str] = None,           # override json/ subdir
        json_file: Optional[str] = None,          # override single-JSON path
        preserve_timestamps: bool = True,
        per_turn_timestamps: Optional[bool] = None,   # None = read from config (default True)
        gpt_metadata: Optional[bool] = None,           # None = read from config (default True)
        gpt_names_xlsx: Optional[str] = None,          # None = read from config (default None)
        config_path: Optional[str] = None,
    )
        """
        Initialize the extractor.

        Args:
            input_file: Path to conversations.json. Optional — required
                only when `extract_all()` is called. Per-conversation
                methods (`process_conversation`, `generate_markdown`,
                `save_markdown_file`) operate on dicts already in memory
                and don't need a file on disk; this lets
                `online_sync.render.OnlineRenderer` wrap the extractor
                for live single-conversation rendering without writing
                a placeholder input file.
            output_dir: Directory for output files (required).
            output_format: Output format(s) to generate.
            json_format: 'single' (one consolidated file) or 'multiple'
                (one file per conversation).
            markdown_dir / json_dir / json_file: Path overrides that
                bypass the default `md/` / `json/` subdirectory creation.
            preserve_timestamps: Sync file mtimes to conversation
                metadata.
            per_turn_timestamps: Emit per-message ISO-8601 UTC italic
                line beneath each role heading in markdown, and the
                `timestamp` field in JSON. `None` reads the config layer
                (built-in default: `True`).
            gpt_metadata: Emit Custom GPT / per-turn model / plugin
                signals (`gizmo_id`, `gizmo_type`, `models_used` in
                frontmatter; per-turn `· model_slug`, `· plugin:<ns>`,
                `· gpt:<id-or-name>`; mirrored to JSON). `None` reads
                the config layer (built-in default: `True`).
            gpt_names_xlsx: Path to `GPT_Names.xlsx` sidecar mapping
                `gizmo_id → name`. When set and readable, frontmatter
                gains `gpt_name:` and the per-turn `gpt:` segment shows
                the resolved name. Missing / unreadable degrades to
                id-only output. `None` reads the config layer
                (built-in default: `None`, i.e. no resolution).
            config_path: Explicit path to a YAML config file. The
                layered loader falls back to
                `$CHATGPT_EXTRACTOR_CONFIG`,
                `./chatgpt_extractor.yaml`, and
                `~/.config/chatgpt_extractor/config.yaml`.

        Creates:
            - Output directories (md/, json/) as needed
            - Schema tracker instance
            - Message processor instance
            - Loads `_gpt_names` map from `gpt_names_xlsx` once
        """
    
    def extract_all(self) -> None
        """
        Main extraction method. Processes all conversations.
        
        Side Effects:
            - Creates markdown files in output_dir
            - Generates schema_evolution.log
            - Generates conversion_log.log (if failures)
            - Prints progress to stdout
        """
    
    def process_conversation(self, conv: Dict) -> None
        """
        Process a single conversation.
        
        Args:
            conv: Conversation dictionary from JSON
            
        Raises:
            Exception: On processing errors (logged, not fatal)
        """
    
    def extract_metadata(self, conv: Dict) -> Dict
        """
        Extract conversation metadata.
        
        Args:
            conv: Conversation dictionary
            
        Returns:
            Dictionary with normalized metadata fields:
            - id, title, create_time, update_time
            - project_id (if applicable)
            - model, chat_url, etc.
        """
    
    def backward_traverse(
        self, 
        mapping: Dict, 
        current_node: Optional[str], 
        conv_id: str
    ) -> List[Dict]
        """
        Traverse conversation graph backwards.
        
        Args:
            mapping: Node ID to node object mapping
            current_node: Starting node ID (may be None)
            conv_id: Conversation ID for tracking
            
        Returns:
            List of messages in chronological order
            
        Algorithm:
            1. Find current_node or highest-weight leaf
            2. Walk backwards to root via parent links
            3. Reverse for chronological order
            4. Add _graph_index for merging validation
        """
    
    def generate_json_data(self, metadata: Dict, messages: List[Dict]) -> Dict
        """
        Convert conversation data to exportable JSON structure.
        
        Args:
            metadata: Conversation metadata
            messages: Processed messages list
            
        Returns:
            Dictionary with metadata and messages for JSON export
        """
    
    def save_to_file(self, metadata: Dict, content: Union[str, Dict], 
                     format: str = 'markdown') -> None
        """
        Save content to file in specified format.
        
        Args:
            metadata: Conversation metadata (for filename/location)
            content: Markdown string or JSON dictionary
            format: 'markdown' or 'json'
            
        Side Effects:
            - Creates file with sanitized name
            - Creates project folder if needed
            - Sets file timestamps from metadata
            - Creates md/ or json/ subdirectory as needed
        """
```

#### Class: MessageProcessor

```python
class MessageProcessor:
    """Process and filter messages with enhanced content handling"""
    
    def __init__(self, tracker: SchemaEvolutionTracker)
        """Initialize with schema tracker reference"""
    
    def should_filter_message(self, msg: Dict) -> bool
        """
        Determine if message should be filtered out.
        
        Args:
            msg: Message dictionary
            
        Returns:
            True if should be excluded from output
            
        Filtering Rules:
            - Exclude if metadata.is_visually_hidden_from_conversation
            - Exclude tool messages (unless DALL-E images)
            - Exclude content_type in [model_editable_context, thoughts, reasoning_recap]
            - Exclude empty assistant placeholders
        """
    
    def extract_message_content(self, msg: Dict, conv_id: str) -> Optional[str]
        """
        Extract text content from message based on content_type.
        
        Args:
            msg: Message dictionary
            conv_id: For tracking unknown types
            
        Returns:
            Extracted text or None if empty
            
        Content Types Handled:
            - text: Extract from parts[]
            - code: Format with language
            - multimodal_text: Process parts[]
            - execution_output: Format as output block
            - user_editable_context: Extract custom instructions
            - tether_quote/sonic_webpage: Direct text
            - Unknown types: Attempt generic extraction
        """
    
    def extract_from_parts(self, parts: List, conv_id: str) -> Optional[str]
        """
        Process parts array to extract text.
        
        Args:
            parts: Array of message parts
            conv_id: For tracking
            
        Returns:
            Combined text or None
            
        Part Types:
            - str: Direct text
            - audio_transcription: Include with prefix
            - image_asset_pointer: Check for DALL-E
            - None: Skip gracefully
        """
    
    def extract_web_urls(self, msg: Dict, conv_data: Dict = None) -> List[str]
        """
        Extract ALL web URLs from message and conversation.
        
        Args:
            msg: Message dictionary
            conv_data: Full conversation (for safe_urls)
            
        Returns:
            Sorted list of unique URLs
            
        Sources (6+):
            1. message.metadata.citations[].metadata.url
            2. conversation.safe_urls[]
            3. content.url (tether_quote, sonic_webpage)
            4. content.domain (with https:// prefix)
            5. content.result (regex extraction)
            6. parts[] text (regex extraction)
        """
    
    def extract_citations(self, msg: Dict) -> List[Dict]
        """
        Extract citations from message.
        
        Args:
            msg: Message dictionary
            
        Returns:
            List of citation dictionaries:
            - type: Citation type
            - title: Citation title
            - url: Citation URL
            - quoted_text: If present
            - start_ix/end_ix: If present
        """
    
    def merge_continuations(self, messages: List[Dict]) -> List[Dict]
        """
        Merge consecutive assistant messages.
        
        Args:
            messages: List of processed messages
            
        Returns:
            List with continuations merged
            
        Merging Rules:
            - Only merge if both role='assistant'
            - Must be consecutive in graph (_graph_index)
            - Combine content with double newline
            - Merge citations and URLs
        """
```

#### Class: SchemaEvolutionTracker

```python
@dataclass
class SchemaEvolutionTracker:
    """Track unknown patterns and schema changes"""
    
    def track_content_type(self, content_type: str, conv_id: str)
        """Track and log unknown content types"""
    
    def track_author_role(self, role: str, conv_id: str)
        """Track unknown author roles"""
    
    def track_recipient(self, recipient: str, conv_id: str)
        """Track tool/recipient values"""
    
    def track_metadata_keys(self, metadata: Dict, conv_id: str)
        """Track new metadata field names"""
    
    def track_part_type(self, part_type: str, conv_id: str)
        """Track unknown part types in multimodal content"""
    
    def generate_report(self) -> str
        """Generate human-readable evolution report"""
```

#### Module: `chatgpt_extractor.gpt_metadata`

Pure functions for Custom GPT / per-turn model / plugin extraction, plus
the `GPT_Names.xlsx` sidecar reader. All functions are stateless except
`load_gpt_names_xlsx`, which does a single file read.

```python
def extract_conv_gpt_meta(conv: Dict[str, Any]) -> Dict[str, Any]
    """Return frontmatter additions: gizmo_id (Custom GPT only), gizmo_type,
    models_used (deduped set of per-message model_slug values).

    `snorlax` (project) conversations get `gizmo_type` but NOT `gizmo_id`
    (it would duplicate `project_id`)."""

def extract_msg_gpt_signals(api_msg: Dict[str, Any]) -> Dict[str, Optional[str]]
    """Per-message signal triple — model_slug, gizmo_id, plugin_namespace.
    Stashed on the per-message dict during process_messages so the renderer
    can emit the per-turn suffix without re-walking the raw API shape."""

def format_per_turn_suffix(
    msg: Dict[str, Any],
    conv_default_gizmo_id: Optional[str],
    names_map: Optional[Dict[str, str]] = None,
) -> str
    """Build the dot-separated per-turn metadata suffix:
    ` · <model_slug> · plugin:<ns> · gpt:<name-or-id>`. Returns empty when
    nothing per-turn-specific to emit. `gpt:<id>` is suppressed for
    project-id echoes (g-p-*) and replaced with the human-readable name
    when `names_map` resolves it."""

def load_gpt_names_xlsx(path: Optional[str | Path]) -> Dict[str, str]
    """Read a 2- or 3-column GPT_Names.xlsx → {gizmo_id: name}.
    Silent-by-default: missing path / file / openpyxl / malformed
    workbook all return {} with at most a single warning. Never raises."""
```

#### Module: `chatgpt_extractor.config`

```python
DEFAULTS: Dict[str, Any] = {
    "per_turn_timestamps": True,
    "gpt_metadata": True,
    "gpt_names_xlsx": None,
}

def load_config(explicit_path: Optional[str] = None) -> Dict[str, Any]
    """Merge built-in DEFAULTS with the first matching YAML file.
    Search order: explicit_path → $CHATGPT_EXTRACTOR_CONFIG →
    ./chatgpt_extractor.yaml → ~/.config/chatgpt_extractor/config.yaml.
    Malformed YAML falls back silently."""
```

#### Class: ProgressTracker

```python
@dataclass
class ProgressTracker:
    """Enhanced progress tracking with ETA"""
    
    total: int
    processed: int = 0
    failed: int = 0
    start_time: float = field(default_factory=time.time)
    
    def update(self, success: bool = True)
        """Update progress and show if milestone"""
    
    def show_progress(self)
        """Display progress with rate and ETA"""
```

## Data Structures

### Input: Conversation JSON

```typescript
interface Conversation {
    // Required
    id: string
    title: string
    create_time: number  // Unix timestamp
    update_time: number
    mapping: { [nodeId: string]: Node }
    
    // Optional
    current_node?: string
    conversation_template_id?: string  // Project ID if g-p-*
    default_model_slug?: string
    is_archived?: boolean
    is_starred?: boolean
    safe_urls?: string[]
    // ... many more fields
}

interface Node {
    id: string
    parent: string | null  // null = root
    children: string[]
    message?: Message | null  // null = root node
}

interface Message {
    id: string
    author: {
        role: 'system' | 'user' | 'assistant' | 'tool'
        name?: string  // Tool name
    }
    content: MessageContent
    create_time?: number | null
    update_time?: number | null
    status?: string
    end_turn?: boolean | null
    weight: number  // 1.0 = active, <1.0 = alternative
    recipient?: string  // 'all' or tool name
    metadata?: MessageMetadata
}

interface MessageContent {
    content_type: string  // See Content Type Registry
    parts?: Array<string | PartObject>  // Can be None!
    text?: string
    language?: string  // For code
    // Type-specific fields
}
```

### Output: Markdown Format

```markdown
---
# YAML Frontmatter
id: conversation-uuid
title: "Conversation Title"
created: "2026-01-01T12:00:00Z"
updated: "2026-01-02T15:30:00Z"
model: gpt-5-2                          # legacy default_model_slug field
gizmo_id: g-uefFoRnpX                   # Custom GPT only
gizmo_type: gpt                         # 'gpt' | 'snorlax' (project) | absent
gpt_name: "Summarizer 2: PDF Book…"     # resolved from GPT_Names.xlsx
models_used: [gpt-4o, gpt-5-2]          # deduped per-message slugs
project_id: g-p-uuid                    # only for snorlax convs
starred: false
archived: false
chat_url: "https://chatgpt.com/c/conversation-uuid"
---

# Conversation Title

## System
Custom instructions if any

## User
*2026-01-01T12:00:01.123456Z*
User message with [File: document.pdf] indicators

## Assistant
*2026-01-01T12:00:02.234567Z · gpt-4o · plugin:youtube_api_widenex_com · gpt:Unorthodox Humor XI*
Response with ```python
code blocks
```

**Citations:**
- [webpage] Title - https://url.com

**Web Search URLs:**
- https://search-result1.com
```

## Content Type Registry

### Text-Based Types

| Type | Has `parts` | Has `text` | Extraction Method |
|------|------------|------------|-------------------|
| `text` | Yes | No | Join parts array |
| `code` | No | Yes | Format with language |
| `execution_output` | No | Yes | Format as output block |
| `tether_quote` | No | Yes | Direct text + URL |
| `sonic_webpage` | No | Yes | Direct text + URL |

### Complex Types

| Type | Structure | Extraction Method |
|------|-----------|-------------------|
| `multimodal_text` | parts[] with mixed types | Process each part by type |
| `user_editable_context` | user_profile + user_instructions | Extract and clean wrappers |
| `tether_browsing_display` | result + summary | Parse for URLs and text |

### Part Types (in multimodal_text)

| Type | Action | Example |
|------|--------|---------|
| `string` | Include directly | Plain text |
| `audio_transcription` | Include with prefix | [Audio transcription] text |
| `image_asset_pointer` | Check for DALL-E | [DALL-E Image: prompt] |
| `audio_asset_pointer` | Skip | N/A |
| `real_time_user_audio_video_asset_pointer` | Skip | N/A |

### Filtered Types

These content types are always excluded:
- `model_editable_context`
- `thoughts`
- `reasoning_recap`

## Configuration

### Command Line Arguments

```bash
python -m chatgpt_extractor [input_file] [output_dir] [options]

# Format selection
--output-format {markdown,json,both}    # default: markdown
--json-format {single,multiple}          # default: multiple
--markdown-dir PATH                      # bypass md/ subdir
--json-dir PATH                          # bypass json/ subdir
--json-file PATH                         # override single-JSON path

# Per-message metadata
--per-turn-timestamps / --no-per-turn-timestamps   # default from config (True)
--gpt-metadata / --no-gpt-metadata                  # default from config (True)
--gpt-names-xlsx PATH                               # GPT_Names.xlsx sidecar path

# File timestamps + config + diagnostics
--preserve-timestamps {true,false}       # sync file mtimes (default: true)
--config PATH                            # explicit layered-config path
--analyze-failures                       # run failure analysis if errors
--debug                                  # enable debug logging
--help                                   # show help

# Defaults:
input_file: data/raw/conversations.json
output_dir: data/output
```

### Layered YAML Config

The extractor reads YAML config from the first existing of:

1. `--config <path>` CLI argument
2. `$CHATGPT_EXTRACTOR_CONFIG` env var
3. `./chatgpt_extractor.yaml`
4. `~/.config/chatgpt_extractor/config.yaml`

```yaml
# Recognised keys (built-in defaults shown)
per_turn_timestamps: true
gpt_metadata: true
gpt_names_xlsx: null          # set to a path string to enable name resolution
```

Malformed YAML falls back silently to built-in defaults — config errors
never block the extractor.

### Constants and Limits

```python
# Performance
PROGRESS_UPDATE_INTERVAL = 100  # conversations
PROGRESS_UPDATE_SECONDS = 5     # time-based update

# Content Processing
MAX_ERROR_MESSAGE = 500         # characters
MAX_FILENAME_LENGTH = 100       # characters
PROBLEMATIC_NODES_SAMPLE = 3    # in error logs

# Known Patterns (for schema evolution)
KNOWN_CONTENT_TYPES = {
    'text', 'code', 'multimodal_text', 'execution_output',
    'tether_quote', 'tether_browsing_display', 'user_editable_context',
    'model_editable_context', 'thoughts', 'reasoning_recap', 
    'sonic_webpage', 'system_error'
}

KNOWN_ROLES = {'system', 'user', 'assistant', 'tool'}

KNOWN_PART_TYPES = {
    'image_asset_pointer', 'audio_transcription', 
    'audio_asset_pointer', 'video_asset_pointer', 
    'code_interpreter_output'
}
```

### Output Files

| File | Purpose | Format |
|------|---------|--------|
| `md/*.md` | Conversation content | Markdown with YAML |
| `json/*.json` | Individual conversations | JSON structure |
| `all_conversations.json` | Consolidated output | JSON array |
| `schema_evolution.log` | Unknown patterns | Human-readable report |
| `conversion_log.log` | Failed conversions | Detailed diagnostics |
| `conversion_failures.json` | Machine-readable failures | JSON |

## Extension Points

### Adding New Content Types

```python
# In extract_message_content():
elif content_type == 'new_type':
    # Custom extraction logic
    return extracted_text
```

### Custom Output Formats

```python
# Override generate_markdown():
def generate_custom_format(self, metadata: Dict, messages: List[Dict]) -> str:
    # Custom formatting logic
    return formatted_content
```

### Additional Tracking

```python
# Extend SchemaEvolutionTracker:
def track_custom_pattern(self, pattern: str, conv_id: str):
    self.custom_patterns.add(pattern)
    # Log for analysis
```

### Pre/Post Processing Hooks

```python
# Add to process_conversation():
def pre_process_hook(self, conv: Dict):
    # Custom validation or transformation
    pass

def post_process_hook(self, conv: Dict, result: Any):
    # Custom actions after processing
    pass
```

## Error Handling Patterns

### Defensive Checks

```python
# ALWAYS check for None before 'in' operator:
if metadata and 'key' in metadata:
    value = metadata['key']

# ALWAYS check parts is a list:
if parts and isinstance(parts, list):
    for part in parts:
        if part is None:
            continue

# ALWAYS use .get() with defaults:
content_type = content.get('content_type', '')
```

### Error Categories

| Category | Pattern | Recovery |
|----------|---------|----------|
| `NoneType_Error` | `'in' operator on None` | Check None first |
| `Missing_Key` | KeyError | Use .get() |
| `Index_Error` | List index out of range | Check length |
| `Malformed_Content` | Unexpected structure | Generic extraction |

### Logging Patterns

```python
# Structured failure logging:
failure_record = {
    'conversation_id': str,
    'title': str,
    'category': str,  # Automatic categorization
    'error_message': str[:500],
    'statistics': {...},  # Structural analysis
    'metadata': {...},    # Context
    'problematic_nodes': [...],  # Samples
    'trace_snippet': str  # Debug info
}
```

## Utility Tools

### analyze_failures.py

Standalone diagnostic tool for analyzing extraction failures and identifying patterns.

#### Usage

```bash
# Analyze failures from a previous run
python analyze_failures.py

# Analyze with custom sample size (default: 20)
python analyze_failures.py
```

#### Core Function

```python
def analyze_failures(input_file: str, sample_size: int = 20) -> List[Dict]
    """
    Analyzes failed conversations to identify patterns.
    
    Args:
        input_file: Path to conversations.json
        sample_size: Number of failures to sample for detailed analysis
    
    Returns:
        List of sampled failure dictionaries with full context
    
    Outputs:
        - Console report with failure patterns and recommendations
        - failure_analysis_report.json with detailed statistics
    """
```

#### Failure Pattern Detection

```python
# Categorizes failures into:
- NoneType_error: Missing content/parts fields
- KeyError: Missing expected fields
- empty_result: Successful parse but no output
- index_error: List access issues
- other: Uncategorized errors
```

#### Structural Analysis

For each failed conversation, analyzes:
- None content count in messages
- None parts count in content
- Empty parts arrays
- Missing or invalid current_node
- Branch count (edited conversations)
- Total message count

#### Output Files

**failure_analysis_report.json**:
```json
{
  "total_conversations": 6885,
  "total_failures": 523,
  "failure_rate": 7.6,
  "failure_patterns": {
    "NoneType_error": 467,
    "empty_result": 56
  },
  "sample_failures": [...]
}
```

#### Integration with Main Script

While standalone, can be integrated for automatic analysis:

```bash
#!/bin/bash
# run_with_analysis.sh

# Run extraction
python -m chatgpt_extractor

# Check if failures occurred
if grep -q "Failed conversations:" data/output_md/conversion_log.log; then
    echo "Analyzing failures..."
    python analyze_failures.py
    echo "See failure_analysis_report.json for details"
fi
```

## Performance Optimization

### Techniques Used

1. **Backward Traversal**: O(n) instead of O(n²) for branches
2. **Set Operations**: For URL deduplication
3. **Early Returns**: Skip processing when possible
4. **Batch I/O**: Write files in batches
5. **Progress Throttling**: Update display strategically

### Benchmarks

| Operation | Time | Complexity |
|-----------|------|------------|
| Load 500MB JSON | ~1.2s | O(n) |
| Process 1 conversation | ~10ms | O(m) messages |
| Backward traversal | 0.077ms | O(depth) |
| Write 1 markdown | ~1ms | O(content) |
| Total for 6,885 | ~100s | O(n*m) |

### Memory Management

```python
# For very large files:
- Process in batches of 100-500 conversations
- Clear references after processing
- Use generators where possible
- Monitor memory usage
```