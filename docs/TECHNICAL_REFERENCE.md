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
    """Enhanced extractor with schema tracking and multi-format output"""
    
    def __init__(self, input_file: str, output_dir: str,
                 markdown: bool = True,
                 json_dir: bool = False,
                 json_file: Optional[str] = None)
        """
        Initialize the extractor.
        
        Args:
            input_file: Path to conversations.json
            output_dir: Directory for output files
            markdown: Generate markdown output (default: True)
            json_dir: Generate individual JSON files (default: False)
            json_file: Generate single JSON file with given name (default: None)
            
        Creates:
            - Output directories (md/, json/) as needed
            - Schema tracker instance
            - Message processor instance
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
created: 2024-01-01T12:00:00Z
updated: 2024-01-02T15:30:00Z
model: gpt-4
project_id: g-p-uuid  # If applicable
starred: false
archived: false
chat_url: https://chatgpt.com/c/conversation-uuid
---

# Conversation Title

## System
Custom instructions if any

## User
User message with [File: document.pdf] indicators

## Assistant
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

# Options:
--json-dir             Generate individual JSON files
--json-file FILE       Generate single JSON file
--no-markdown          Skip markdown generation
--help                 Show help message

# Defaults:
input_file: data/raw/conversations.json
output_dir: data/output
```

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