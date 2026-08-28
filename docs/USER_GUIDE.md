# ChatGPT Conversation Extractor - User Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Getting Your ChatGPT Data](#getting-your-chatgpt-data)
4. [Basic Usage](#basic-usage)
5. [Advanced Usage](#advanced-usage)
6. [Understanding the Output](#understanding-the-output)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

## Quick Start

```bash
# 1. Install project dependencies
uv sync --group dev

# 2. Export your ChatGPT conversations (see below)

# 3. Run the extractor (markdown output)
uv run chatgpt-extractor data/raw/conversations.json data/output

# 4. Find your files in data/output/md/

# Optional: Extract to JSON format as well
uv run chatgpt-extractor data/raw/conversations.json data/output --output-format both
```

## Installation

### System Requirements

- **Python**: 3.9 or higher (3.9 / 3.10 / 3.11 / 3.12 all tested in CI)
- **uv**: required for the documented local workflow
- **Memory**: 2GB RAM (for 500MB JSON files)
- **Disk Space**: 2x the size of your conversations.json
- **OS**: Windows, macOS, Linux

### Step 1: Clone Repository

```bash
git clone https://github.com/cs224/chatgpt-conversation-extractor.git
cd chatgpt-conversation-extractor
```

### Step 2: Install Dependencies

```bash
uv sync --group dev
```

### Step 3: Create Directory Structure

```bash
# Create input/output directories
mkdir -p data/raw
mkdir -p data/output
```

## Getting Your ChatGPT Data

### Export from ChatGPT

1. **Log in** to [ChatGPT](https://chat.openai.com)
2. Click your **profile icon** (bottom left)
3. Select **Settings**
4. Go to **Data controls**
5. Click **Export data**
6. Click **Export** button
7. Wait for email (usually within 24 hours)
8. Download the ZIP file from the email link
9. For classic exports, extract `conversations.json` from the ZIP

Privacy Portal exports can be one level more indirect: after extracting the
top-level export ZIP, `User Online Activity/` may contain
`Conversations__*-chatgpt-*.zip`, `Files__...zip`, and `Ads__...zip`. For
Markdown conversation generation, extract only the `Conversations__...zip`;
the current extractor does not require the Ads or Files archives.

### File Location

Place your `conversations.json` in the `data/raw/` directory:

```
chatgpt-extractor/
├── src/
│   └── chatgpt_extractor/
│       ├── __init__.py
│       ├── __main__.py
│       └── extractor.py
├── data/
│   ├── raw/
│   │   └── conversations.json  # ← Place here
│   └── output/                 # Output will go here
│       ├── md/                 # Markdown files
│       └── json/               # JSON files (if enabled)
```

## Basic Usage

### Default Extraction

```bash
# Uses default paths (markdown only)
uv run chatgpt-extractor

# Default input: data/raw/conversations.json
# Default output: data/output/
```

### Custom Paths

```bash
# Specify custom input and output
uv run chatgpt-extractor /path/to/conversations.json /path/to/output

# Example:
uv run chatgpt-extractor ~/Downloads/conversations.json ~/Documents/ChatGPT
```

### Output Format Options

```bash
# Markdown only (default)
uv run chatgpt-extractor conversations.json output/

# Both markdown and JSON (individual files)
uv run chatgpt-extractor conversations.json output/ --output-format both

# Single consolidated JSON file
uv run chatgpt-extractor conversations.json output/ --output-format json \
    --json-format single --json-file all_conversations.json

# JSON only (multiple files)
uv run chatgpt-extractor conversations.json output/ --output-format json

# Suppress per-message Custom GPT / model / plugin signals (legacy shape)
uv run chatgpt-extractor conversations.json output/ --no-gpt-metadata

# Resolve gizmo_id -> human-readable name via a sidecar xlsx
uv run chatgpt-extractor conversations.json output/ --gpt-names-xlsx /path/GPT_Names.xlsx

# View help for all options
uv run chatgpt-extractor --help
```

### What to Expect

```
Starting ChatGPT Conversation Extractor v3.1
Loading conversations from data/raw/conversations.json
Found 8248 conversations to process
Output directory: data/output
Markdown output: data/output/md

  Progress: 500/8248 (6.1%) | Failed: 0 | Rate: 75.3/s | ETA: 1.7m
  Progress: 1000/8248 (12.1%) | Failed: 0 | Rate: 76.6/s | ETA: 1.6m
  ...
  Progress: 8248/8248 (100.0%) | Failed: 0 | Rate: 65.8/s | ETA: 0s

============================================================
EXTRACTION COMPLETE!
============================================================
  Total conversations: 8248
  Successfully processed: 8248
  Failed: 0
  Success rate: 100.0%
  Markdown files created: 8248
  Time elapsed: 125.3s
  Processing rate: 65.8 conv/s
  Output directory: data/output
```

## Advanced Usage

### Processing Large Files

For very large exports (>1GB):

```bash
# Monitor memory usage
uv run chatgpt-extractor large_export.json output/ 2>&1 | tee extraction.log
```

### Batch Processing

For Privacy Portal exports, prefer the repository Makefile. If the split
`conversations-*.json` files are still inside the nested
`Conversations__*-chatgpt-*.zip`, extract that archive first:

```bash
make extract-conversations-zip
make list-inputs
make extract
```

For custom batch layouts:

```bash
for file in exports/*.json; do
    output_dir="output/$(basename $file .json)"
    uv run chatgpt-extractor "$file" "$output_dir"
done
```

### Custom GPT name resolution

The extractor itself doesn't fetch names from the ChatGPT API. Names are
populated by the live-sync companion (`online-sync gpt-names
--backfill-from-conversations-json …`) into a `GPT_Names.xlsx` sidecar
which the extractor reads. Point at the sidecar via:

```bash
uv run chatgpt-extractor conversations.json output/ \
    --gpt-names-xlsx /mnt/c/chatgpt_history/GPT_Names.xlsx
```

Missing / unreadable sidecar silently degrades to id-only output —
the extractor will never crash on a bad sidecar.

### Configuration file

Defaults can be set persistently in a YAML config. Search order:

1. `--config <path>` CLI argument
2. `$CHATGPT_EXTRACTOR_CONFIG` environment variable
3. `./chatgpt_extractor.yaml` in the current working directory
4. `~/.config/chatgpt_extractor/config.yaml`

```yaml
# ~/.config/chatgpt_extractor/config.yaml
per_turn_timestamps: true
gpt_metadata: true
gpt_names_xlsx: /mnt/c/chatgpt_history/GPT_Names.xlsx

# Web URL extraction control — preset string or per-type map.
# Preset shortcuts:
#   web_urls: off        — no URL blocks at all
#   web_urls: citations  — only the **Citations:** block (leanest useful)
#   web_urls: rich       — Citations + Sources blocks (title + snippet
#                          from search_result_groups + content_references)
# Or explicit per-type map:
web_urls:
  citations: rich              # off | minimal | rich  — rich = Citations block
  conv_safe_urls: off          # off | minimal          — conv.safe_urls[]
  msg_safe_urls: off           # off | minimal          — metadata.safe_urls[]
  search_result_groups: rich   # off | minimal | rich   — rich = Sources block
  content_references: rich     # off | minimal | rich   — rich = Sources block
```

### Choosing a `web_urls` level

This fork defaults to the rich source profile because its main workflow
is indexing rendered markdown into desktop search tools such as Recoll
or DocFetcher. The default drops URL-only bulk from `safe_urls` sources
(low semantic signal) while surfacing titles + snippets from the modern
web-search structures (high semantic signal) as a new `**Sources:**`
block. If you don't want any URL blocks at all — indexing prose only —
use `web_urls: off`. If you want the leanest source context, use
`web_urls: citations`.

## Understanding the Output

### Directory Structure

```
data/output/
├── md/                                 # Markdown output (default)
│   ├── Regular Conversation 1.md
│   ├── Regular Conversation 2.md
│   ├── Regular Conversation (2).md     # duplicate titles get numbered
│   └── g-p-<project-id>/               # project subfolders (raw id form)
│       ├── Project Conv 1.md
│       └── Project Conv 2.md
├── json/                               # JSON output (with --output-format json|both)
│   ├── Regular Conversation 1.json
│   ├── Regular Conversation 2.json
│   └── g-p-<project-id>/
│       ├── Project Conv 1.json
│       └── Project Conv 2.json
├── all_conversations.json              # only with --json-format single
└── logs/
    ├── schema_evolution.log            # format tracking (if enabled)
    └── conversion_log.log              # only if failures
```

### Output File Formats

#### Markdown Format

Each conversation becomes a markdown file with:

```markdown
---
# YAML frontmatter
id: 68c2d4c7-9cac-8332-b27d-1b666ebddb61
title: "Conversation Title"
created: "2024-01-15T10:30:00Z"
updated: "2024-01-15T11:45:00Z"
model: gpt-5-2                                # conv-level default_model_slug
gizmo_id: g-uefFoRnpX                         # Custom GPT only (Custom GPT convs)
gizmo_type: gpt                               # 'gpt' (Custom GPT) | 'snorlax' (project)
gpt_name: "Summarizer 2: PDF Book…"           # if resolved from GPT_Names.xlsx
models_used: [gpt-4o, gpt-5-2]                # deduped per-message model_slug
project_id: g-p-685bb57d8cec8191985f702d…     # only for project (snorlax) convs
starred: false
archived: false
chat_url: "https://chatgpt.com/c/68c2d4c7-9cac-8332-b27d-1b666ebddb61"
---

# Conversation Title

## System
Your custom instructions appear here

## User
*2024-01-15T10:30:15.123456Z*
User's message with any [File: document.pdf] attachments noted

## Assistant
*2024-01-15T10:30:16.234567Z · gpt-4o*
ChatGPT's response with:
- Formatted text
- ```python
  code blocks with syntax highlighting
  ```
- Lists and formatting preserved

**Citations:**
- [webpage] Article Title - https://source.com

**Web Search URLs:**
- https://searched-site1.com
- https://searched-site2.com
```

Notes on the per-turn italic line:
- Always emitted for non-system messages when the source carries
  `create_time` (the conversation export always does for messages from
  ChatGPT). Suppress with `--no-per-turn-timestamps`.
- Appends `· model_slug` when the assistant turn recorded one.
- Appends `· plugin:<namespace>` for tool invocations.
- Appends `· gpt:<id>` (or `gpt:<Pretty Name>` when `GPT_Names.xlsx`
  has a row) only when the per-message gizmo differs from the
  conversation default — the @mention pattern.

#### JSON Format

Each JSON file is a single conversation object at the top level (not
nested under a "metadata" key — historical):

```json
{
  "id": "68c2d4c7-9cac-8332-b27d-1b666ebddb61",
  "title": "Conversation Title",
  "created": "2024-01-15T10:30:00Z",
  "updated": "2024-01-15T11:45:00Z",
  "model": "gpt-5-2",
  "gizmo_id": "g-uefFoRnpX",
  "gizmo_type": "gpt",
  "gpt_name": "Summarizer 2: PDF Book…",
  "models_used": ["gpt-4o", "gpt-5-2"],
  "project_id": null,
  "total_messages": 5,
  "code_messages": 2,
  "starred": false,
  "archived": false,
  "chat_url": "https://chatgpt.com/c/<id>",
  "messages": [
    {
      "role": "user",
      "content": "User message",
      "timestamp": "2024-01-15T10:31:00Z",
      "files": ["document.pdf"]
    },
    {
      "role": "assistant",
      "content": "Assistant response",
      "timestamp": "2024-01-15T10:32:00Z",
      "model_slug": "gpt-4o",
      "gizmo_id": "g-uefFoRnpX",
      "plugin_namespace": "youtube_api_widenex_com",
      "citations": [...],
      "web_urls": [...]
    }
  ]
}
```

### Special Indicators

| Indicator | Meaning |
|-----------|---------|
| `[File: name.pdf]` | File was uploaded |
| `[Audio transcription]` | Voice input transcribed |
| `[DALL-E Image: prompt]` | AI-generated image |
| `[Web Search: query]` | Web search performed |
| ````output` | Code execution output |

### Log Files

#### schema_evolution.log
Tracks unknown patterns for future updates:
- New content types discovered
- Unknown author roles
- New tools/plugins used
- Unrecognized metadata fields

#### conversion_log.log
Details of any failed conversions:
- Error category and message
- Conversation structure analysis
- Problematic nodes identified
- Debug information for investigation

## Troubleshooting

### Common Issues

#### 1. "No module named 'yaml'"
```bash
# Sync project dependencies from pyproject.toml
uv sync --group dev
```

#### 2. "Input file not found"
```bash
# Check file location
ls -la data/raw/conversations.json

# Or specify full path
uv run chatgpt-extractor /full/path/to/conversations.json output/
```

#### 3. Memory Error with Large Files
```bash
# Monitor memory
uv run python -u -m chatgpt_extractor 2>&1 | tee extraction.log

# Consider splitting large exports or increasing system memory
```

#### 4. Permission Denied
```bash
# Ensure write permissions on the output dir
chmod -R u+w data/output
# Or run with appropriate permissions
```

#### 5. Some Conversations Failed
Check `conversion_log.log` for details:
- Usually due to malformed data in export
- Script continues processing remaining conversations
- 99%+ success rate is normal

### Performance Tips

1. **SSD vs HDD**: Use SSD for 2-3x faster processing
2. **Close other apps**: Free up memory for large files
3. **Don't interrupt**: Let it complete for best results
4. **Check logs**: Review schema_evolution.log for insights

## FAQ

### Q: How long does extraction take?
**A:** Typically 60-120 seconds for 6,000+ conversations (~100 conv/sec)

### Q: Why are some conversations in folders?
**A:** Conversations from ChatGPT Projects are grouped in project folders

### Q: Can I re-run the extraction?
**A:** Yes, it will overwrite existing files. Back up if needed.

### Q: What about edited messages?
**A:** The extractor uses the final version, excluding edit history

### Q: Are images included?
**A:** Image references are noted but actual images aren't extracted

### Q: What's the success rate?
**A:** Typically 99%+ with proper handling of edge cases

### Q: Can I extract specific conversations?
**A:** Currently extracts all. Modify code for filtering.

### Q: Is my data safe?
**A:** All processing is local. No data leaves your computer.

### Q: What about non-English conversations?
**A:** Fully supported, UTF-8 encoding preserved

### Q: Can I customize the output format?
**A:** Yes, modify the `generate_markdown()` method

## Support

### Getting Help

1. **Check logs**: Review error messages in conversion_log.log
2. **Documentation**: See TECHNICAL_REFERENCE.md for details
3. **Issues**: Report bugs with error details and log excerpts

### Providing Feedback

When reporting issues, include:
- Python version: `python --version`
- Error messages from console
- Relevant lines from conversion_log.log
- Sample of problematic conversation (if possible)

## Privacy & Security

- **Local Processing**: All extraction happens on your computer
- **No Network Calls**: Script doesn't connect to internet
- **No Data Collection**: Your conversations remain private
- **Sanitized Filenames**: Special characters removed for safety

## Version History

### v3.1 (Current)
- Default output directory: `data/output` (markdown → `data/output/md/`)
- Multi-format output (`--output-format markdown|json|both`)
- JSON format selection (`--json-format single|multiple`)
- Per-message timestamps in output (`--per-turn-timestamps`, default on)
- Custom GPT / per-turn model / plugin signals
  (`--gpt-metadata`, default on; companion `--gpt-names-xlsx` sidecar
  resolves opaque `gizmo_id` to human-readable name)
- Layered YAML config (`--config`, plus search order based on env +
  cwd + home)

### v2.0
- Schema evolution tracking
- Comprehensive error logging
- 100% success rate with fixes
- Progress indication with ETA
- Project folder organization

### Future Enhancements
- HTML/PDF output options
- Incremental extraction
- Search functionality
- Web UI interface
