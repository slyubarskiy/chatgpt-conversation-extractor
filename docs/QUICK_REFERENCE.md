# ChatGPT Extractor - Quick Reference Card

## Command Line

```bash
# Basic usage (markdown only)
python -m chatgpt_extractor                              # uses data/raw/conversations.json -> data/output/
python -m chatgpt_extractor input.json output_dir/       # custom paths

# Output format
python -m chatgpt_extractor --output-format json         # JSON only (multiple files by default)
python -m chatgpt_extractor --output-format both         # markdown + JSON

# JSON shape
python -m chatgpt_extractor --output-format json --json-format multiple    # individual files in json/
python -m chatgpt_extractor --output-format json --json-format single      # one consolidated file
python -m chatgpt_extractor --output-format json --json-file all.json      # explicit consolidated path

# Directory overrides (bypass md/, json/ subdirs)
python -m chatgpt_extractor --markdown-dir custom/md/
python -m chatgpt_extractor --json-dir custom/json/

# Per-message metadata
python -m chatgpt_extractor --no-per-turn-timestamps     # legacy: no per-turn ISO line in markdown
python -m chatgpt_extractor --no-gpt-metadata            # legacy: no gizmo_id / models_used / · gpt:<id>
python -m chatgpt_extractor --gpt-names-xlsx <path>      # resolve gizmo_id -> human-readable name

# File timestamps + config + diagnostics
python -m chatgpt_extractor --preserve-timestamps false  # don't sync file mtimes to conv metadata
python -m chatgpt_extractor --config /path/cfg.yaml      # explicit layered-config path
python -m chatgpt_extractor --analyze-failures           # run failure analysis if errors occurred
python -m chatgpt_extractor --debug                      # enable debug logging
```

## File Structure

```
Input:  data/raw/conversations.json
Output: data/output/
        ├── md/                          # Markdown (default)
        │   ├── Loose Conversation.md
        │   └── g-p-<project-id>/        # Project subfolders
        │       └── Project Conv.md
        ├── json/                        # JSON (with --output-format json|both)
        │   ├── Loose Conversation.json
        │   └── g-p-<project-id>/
        │       └── Project Conv.json
        ├── all_conversations.json       # only with --json-format single
        └── logs/
            ├── schema_evolution.log     # tracker output (if enabled)
            └── conversion_log.log       # failure details (if any)
```

## Constructor

```python
from chatgpt_extractor.extractor import ConversationExtractorV2

extractor = ConversationExtractorV2(
    input_file="data/raw/conversations.json",   # optional — required only for extract_all()
    output_dir="data/output",                   # required
    output_format="markdown",                   # 'markdown' | 'json' | 'both'
    json_format="multiple",                     # 'multiple' | 'single'
    markdown_dir=None,                          # override md/ subdir
    json_dir=None,                              # override json/ subdir
    json_file=None,                             # override single-JSON path
    preserve_timestamps=True,                   # sync file mtimes to conv metadata
    per_turn_timestamps=None,                   # None = read config (default True)
    gpt_metadata=None,                          # None = read config (default True)
    gpt_names_xlsx=None,                        # None = read config (default None)
    config_path=None,                           # explicit YAML config path
)
extractor.extract_all()
```

## Key Methods

```python
# Per-conversation pipeline (used by both batch + live-sync)
extract_metadata(conv) -> Dict
backward_traverse(mapping, current_node, conv_id) -> List[Dict]
process_messages(messages, conv_id, conv_data) -> List[Dict]
merge_continuations(messages) -> List[Dict]
generate_markdown(metadata, messages) -> str
generate_json_data(metadata, messages) -> Dict
save_markdown_file(metadata, content) -> Path

# Message-level helpers (chatgpt_extractor.processors)
processor = MessageProcessor(schema_tracker)
processor.should_filter_message(msg) -> bool
processor.extract_message_content(msg, conv_id) -> Optional[str]
processor.extract_web_urls(msg, conv_data) -> List[str]
processor.extract_citations(msg) -> List[Dict]
```

## Output Formats

### Markdown

```markdown
---
id: 68c2d4c7-9cac-8332-b27d-1b666ebddb61
title: Conversation Title
created: "2026-05-31T14:50:24.319523Z"
updated: "2026-05-31T15:18:00.008868Z"
model: gpt-5-2                                # legacy default_model_slug
gizmo_id: g-uefFoRnpX                         # Custom GPT only (not projects)
gizmo_type: gpt                               # 'gpt' | 'snorlax' (project) | absent
gpt_name: "Summarizer 2: PDF Book Article…"   # resolved from GPT_Names.xlsx
models_used: [gpt-4o, gpt-5-2]                # deduped per-message slugs
project_id: g-p-685bb57d8cec8191985f702d…     # only for snorlax convs
total_messages: 4
chat_url: "https://chatgpt.com/c/<id>"
---

# Title

## User
*2026-05-31T13:50:22.864731Z*
Question text…

## Assistant
*2026-05-31T13:50:24.218536Z · gpt-4o · plugin:youtube_api_widenex_com · gpt:Unorthodox Humor XI*
Reply text…
```

### JSON

```json
{
  "id": "uuid",
  "title": "Title",
  "model": "gpt-5-2",
  "gizmo_id": "g-uefFoRnpX",
  "gizmo_type": "gpt",
  "gpt_name": "Summarizer 2: PDF Book…",
  "models_used": ["gpt-4o"],
  "messages": [
    {"role": "user", "content": "...", "timestamp": "2026-05-31T…Z"},
    {"role": "assistant", "content": "...", "timestamp": "…",
     "model_slug": "gpt-4o", "gizmo_id": "g-uefFoRnpX",
     "plugin_namespace": "youtube_api_widenex_com"}
  ]
}
```

## Config File

Layered: built-in defaults → file → CLI (each wins over the prior).
Search order: `--config <path>` → `$CHATGPT_EXTRACTOR_CONFIG` → `./chatgpt_extractor.yaml` → `~/.config/chatgpt_extractor/config.yaml`.

```yaml
per_turn_timestamps: true       # default true — emit *<ISO>* italic lines
gpt_metadata: true              # default true — emit gizmo_id/type/models_used + per-turn suffix
gpt_names_xlsx: /path/to/GPT_Names.xlsx   # default null — no name resolution
```

## Content Types

| Type | Extract Method | Filter? |
|------|----------------|---------|
| `text` | Join parts[] | No |
| `code` | Format with lang | No |
| `multimodal_text` | Process parts[] | No |
| `execution_output` | Format as output | No |
| `user_editable_context` | Extract instructions | No |
| `tether_quote` | Format as blockquote | No |
| `tether_browsing_display` | Extract from result | No |
| `system_error` | Include error message | No |
| `model_editable_context` | — | Yes |
| `thoughts` | — | Yes |
| `reasoning_recap` | — | Yes |

## URL Extraction Sources

1. `message.metadata.citations[].metadata.url`
2. `conversation.safe_urls[]`
3. `content.url` (tether_quote, sonic_webpage)
4. `content.domain` (with https:// prefix)
5. `content.result` (regex extraction)
6. `parts[]` text (regex extraction)
7. `metadata.attachments`
8. `metadata.aggregate_result`

## Defensive Checks

```python
# Check None before 'in'
if metadata and 'key' in metadata:

# Check parts is a list
if parts and isinstance(parts, list):

# Handle None parts
if part is None:
    continue

# .get() with defaults
value = dict.get('key', default)
```

## Progress Indicators

```
Normal:  Progress: 3000/6885 (43.6%) | Failed: 0 | Rate: 83.9/s | ETA: 46s
Warning: Failed: >10 | Rate: <30/s | ETA: increasing
```

## Quick Debugging

```bash
# Recent failures
grep "Failed:" log.txt | tail -1

# Failure categories
grep "FAILURE CATEGORIES" data/output/logs/conversion_log.log -A 10

# Unknown schema patterns
grep "Unknown" data/output/logs/schema_evolution.log

# Output file counts
ls data/output/md/*.md | wc -l
find data/output/md/g-p-* -name "*.md" | wc -l

# Validate input JSON
python -c "import json; json.load(open('data/raw/conversations.json'))"
```

## Filtering Rules

**Include:**
- User messages
- Assistant messages
- One user system prompt per conv (custom-instructions)
- Tool messages that carry DALL-E images

**Exclude:**
- Tool messages without DALL-E content
- `metadata.is_visually_hidden_from_conversation == true`
- `content_type` in `{model_editable_context, thoughts, reasoning_recap}`
- Empty assistant placeholders

## Performance Targets

- **Success Rate**: >99%
- **Speed**: 65-100 conv/s (UTF-8 markdown, ~80 conv/s typical)
- **Memory**: ~1GB peak for 500MB input
- **Time**: ~100s for 6,000 conversations

## Log Files

```
data/output/logs/
├── schema_evolution.log        # unknown content_types / roles / parts
├── conversion_log.log          # categorised failures + diagnostics
└── conversion_failures.json    # machine-readable failure dump
```

## Pro Tips

1. **SSD > HDD** for 2-3x speed (lots of small writes).
2. **`gpt_names_xlsx`** populated by `online-sync gpt-names` (live-sync repo); the extractor reads it silently.
3. **`--config`** is a single source of truth across runs — set the xlsx path there once.
4. **Project subfolders** are named by raw `g-p-*` id; the live-sync layer renames them post-extract.
5. **`--no-gpt-metadata`** reverts to pre-2026 output if you depend on the older shape.
6. **Per-turn timestamps** are emitted in true UTC; the conversation-level `updated:` field in frontmatter uses local-wall-time-mislabeled-Z (legacy quirk).

---
*v3.2-dev | Python 3.9+ | PyYAML required | openpyxl optional (for GPT_Names.xlsx)*
