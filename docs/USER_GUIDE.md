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
# 1. Install Python dependency
pip install pyyaml

# 2. Export your ChatGPT conversations (see below)

# 3. Run the extractor (markdown output)
python -m chatgpt_extractor data/raw/conversations.json data/output

# 4. Find your files in data/output/md/

# Optional: Extract to JSON format as well
python -m chatgpt_extractor data/raw/conversations.json data/output --json-dir
```

## Installation

### System Requirements

- **Python**: 3.8 or higher
- **Memory**: 2GB RAM (for 500MB JSON files)
- **Disk Space**: 2x the size of your conversations.json
- **OS**: Windows, macOS, Linux

### Step 1: Clone or Download

```bash
# Option A: Clone repository
git clone https://github.com/your-repo/chatgpt-extractor.git
cd chatgpt-extractor

# Option B: Download files
# Download extract_conversations_v2.py to a folder
```

### Step 2: Install Dependencies

```bash
# Only one dependency required
pip install pyyaml

# Or with requirements file
pip install -r requirements.txt
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
9. Extract `conversations.json` from the ZIP

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
python -m chatgpt_extractor

# Default input: data/raw/conversations.json
# Default output: data/output/
```

### Custom Paths

```bash
# Specify custom input and output
python -m chatgpt_extractor /path/to/conversations.json /path/to/output

# Example:
python -m chatgpt_extractor ~/Downloads/conversations.json ~/Documents/ChatGPT
```

### Output Format Options

```bash
# Markdown only (default)
python -m chatgpt_extractor conversations.json output/

# Both markdown and JSON (individual files)
python -m chatgpt_extractor conversations.json output/ --json-dir

# Single consolidated JSON file
python -m chatgpt_extractor conversations.json output/ --json-file all_conversations.json

# JSON only, no markdown
python -m chatgpt_extractor conversations.json output/ --no-markdown --json-dir

# View help for all options
python -m chatgpt_extractor --help
```

### What to Expect

```
ChatGPT Conversation Extractor v2.0
Loading conversations from data/raw/conversations.json...
Found 6885 conversations to process
Output directory: data/output_md

  Progress: 500/6885 (7.3%) | Failed: 0 | Rate: 75.3/s | ETA: 1.4m
  Progress: 1000/6885 (14.5%) | Failed: 0 | Rate: 76.6/s | ETA: 1.3m
  ...
  Progress: 6885/6885 (100.0%) | Failed: 0 | Rate: 65.8/s | ETA: 0s

============================================================
EXTRACTION COMPLETE!
============================================================
  Total conversations: 6885
  Successfully processed: 6885
  Failed: 0
  Success rate: 100.0%
  Time elapsed: 104.7s
  Processing rate: 65.8 conv/s
  Output directory: data/output_md
```

## Advanced Usage

### Processing Large Files

For very large exports (>1GB):

```bash
# Monitor memory usage
python extract_conversations_v2.py large_export.json output/ 2>&1 | tee extraction.log
```

### Batch Processing

For multiple export files:

```bash
# Process multiple exports
for file in exports/*.json; do
    output_dir="output/$(basename $file .json)"
    python extract_conversations_v2.py "$file" "$output_dir"
done
```

### Filtering by Date

To extract only recent conversations (requires modification):

```python
# In process_conversation(), add:
if conv.get('update_time', 0) < cutoff_timestamp:
    return  # Skip old conversations
```

## Understanding the Output

### Directory Structure

```
data/output/
├── md/                           # Markdown output (default)
│   ├── Regular Conversation 1.md
│   ├── Regular Conversation 2.md
│   ├── Regular Conversation (2).md    # Duplicate titles numbered
│   └── project_a3e43bec/             # Project folders
│       ├── Project Conv 1.md
│       └── Project Conv 2.md
├── json/                         # JSON output (if --json-dir)
│   ├── Regular Conversation 1.json
│   ├── Regular Conversation 2.json
│   └── project_a3e43bec/
│       ├── Project Conv 1.json
│       └── Project Conv 2.json
├── all_conversations.json        # Single file (if --json-file)
├── schema_evolution.log          # Format tracking
└── conversion_log.log            # Only if failures
```

### Output File Formats

#### Markdown Format

Each conversation becomes a markdown file with:

```markdown
---
# Metadata in YAML format
id: 68c2d4c7-9cac-8332-b27d-1b666ebddb61
title: "Conversation Title"
created: 2024-01-15T10:30:00Z
updated: 2024-01-15T11:45:00Z
model: gpt-4
starred: false
archived: false
chat_url: https://chatgpt.com/c/68c2d4c7-9cac-8332-b27d-1b666ebddb61
---

# Conversation Title

## System
Your custom instructions appear here

## User
User's message with any [File: document.pdf] attachments noted

## Assistant
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

#### JSON Format

Each JSON file contains:

```json
{
  "metadata": {
    "id": "68c2d4c7-9cac-8332-b27d-1b666ebddb61",
    "title": "Conversation Title",
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T11:45:00Z",
    "model": "gpt-4",
    "total_messages": 5,
    "code_messages": 2,
    "starred": false,
    "archived": false
  },
  "messages": [
    {
      "role": "system",
      "content": "Your custom instructions",
      "timestamp": "2024-01-15T10:30:00Z"
    },
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
      "citations": [...],
      "urls": [...]
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
# Install the required module
pip install pyyaml
```

#### 2. "Input file not found"
```bash
# Check file location
ls -la data/raw/conversations.json

# Or specify full path
python extract_conversations_v2.py /full/path/to/conversations.json output/
```

#### 3. Memory Error with Large Files
```bash
# Monitor memory
python -u extract_conversations_v2.py 2>&1 | tee extraction.log

# Consider splitting large exports or increasing system memory
```

#### 4. Permission Denied
```bash
# Ensure write permissions
chmod +w data/output_md
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

### v2.0 (Current)
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