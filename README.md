# ChatGPT Conversation JSON Extractor

Extracts and processes ChatGPT conversation exports into clean, readable markdown files with comprehensive metadata preservation and error tracking.

## Features

- Processes ChatGPT `conversations.json` export files
- Converts complex conversation graphs to linear transcripts
- Filters out system messages and hidden content
- Preserves code blocks, citations, and file references
- Groups conversations by project automatically
- Handles 6000+ conversations efficiently with detailed logging
- Visibility to schema evolution for transparency
- **Multiple output formats**: Markdown, JSON, or both simultaneously
- **Timestamp preservation**: Maintains original creation/update times on files

## Requirements

- Python 3.8+
- PyYAML (`pip install pyyaml`)
- 2GB+ RAM for large exports (500MB+ JSON files)

## Getting Your ChatGPT Data

1. Log in to [ChatGPT](https://chat.openai.com)
2. Go to Settings → Data controls → Export data
3. Click "Export" and wait for the email (usually within 24 hours)
4. Download and extract `conversations.json` from the ZIP file

## Quick Start

```bash
# Install dependencies
pip install pyyaml

# Default: extract to Markdown
python -m chatgpt_extractor data/raw/conversations.json data/output

# JSON only
python -m chatgpt_extractor --output-format json

or

python -m chatgpt_extractor data/raw/conversations.json data/output --output-format json

# Both Markdown and JSON
python -m chatgpt_extractor --output-format both

# JSON as a single consolidated file
python -m chatgpt_extractor --output-format json --json-format single --json-file all_conversations.json

# JSON as multiple files in custom directory
python -m chatgpt_extractor --output-format json --json-format multiple --json-dir custom/json/

# Markdown in a custom directory
python -m chatgpt_extractor --output-format markdown --markdown-dir custom/md/

# Disable timestamp syncing (use current system time for file timestamps)
python -m chatgpt_extractor --preserve-timestamps false

# Run failure analysis if conversion issues occurred
python -m chatgpt_extractor --analyze-failures

# Enable debug logging for troubleshooting
python -m chatgpt_extractor --debug

```

## Output Structure

```
data/output/
├── md/                         # Markdown output (if enabled)
│   ├── Regular Conversation 1.md
│   ├── Regular Conversation 2.md
│   └── project_XXXXXXXX/      # Project folders
│       ├── Project Conv 1.md
│       └── Project Conv 2.md
├── json/                       # JSON output (if --json-dir)
│   ├── Regular Conversation 1.json
│   ├── Regular Conversation 2.json
│   └── project_XXXXXXXX/
│       ├── Project Conv 1.json
│       └── Project Conv 2.json
├── all_conversations.json      # Single file (if --json-file)
├── schema_evolution.log        # Format tracking
└── conversion_log.log          # Failure details (if any)
```

## Output Formats

### Markdown Format
Each markdown file includes:
- YAML frontmatter with enhanced metadata:
  - Basic: ID, timestamps, model, chat URL, project
  - Statistics: Total messages, code messages count
  - Content types: List of message types in conversation
  - Custom instructions: User's ChatGPT personalization settings
  - Flags: starred, archived status
- Conversation title as header
- User and assistant messages with role indicators
- Code blocks with syntax highlighting
- Citations and web URLs
- File upload indicators (`[File: document.pdf]`)

### JSON Format
Structured data with:
- Complete metadata object
- Messages array with role, content, and timestamps
- Citations and URLs preserved
- Custom instructions included
- Suitable for programmatic processing

## Implementation Details

- **Graph traversal**: Uses backward traversal to reconstruct active conversation path
- **Content filtering**: Removes tool messages, thoughts, and hidden system content
- **Message merging**: Combines consecutive assistant messages
- **Project detection**: Groups by `conversation_template_id` pattern
- **Error handling**: Comprehensive logging with recovery mechanisms

## Performance

- **Processed:** 7,000 conversations (50-MB JSON export)
- **Performance:** <5 minutes end-to-end processing
- **Success Rate:** 99.5%+ with comprehensive error logging
- **Output:** 135MB structured markdown across project folders
- **Architecture:** Memory-efficient graph traversal with defensive parsing

## Best For

- **Knowledge Management:** Converting AI conversation history into searchable documentation
- **AI Workflow Integration:** Preprocessing ChatGPT data for enterprise knowledge systems
- **Research and Analysis:** Clean dataset creation from conversational AI interactions
- **Documentation Generation:** Automated conversation transcript creation for projects

## Not Designed For

- Complete conversation data preservation
- Edit history analysis
- Tool/plugin interaction debugging
- Multi-modal content extraction
- Forensic conversation reconstruction

## Documentation

- [User Guide](docs/USER_GUIDE.md) - Complete installation and usage instructions
- [Architecture](docs/ARCHITECTURE.md) - System design and technical details
- [Technical Reference](docs/TECHNICAL_REFERENCE.md) - API documentation and data structures
- [Operations Guide](docs/OPERATIONS.md) - Troubleshooting and maintenance
- [Quick Reference](docs/QUICK_REFERENCE.md) - Command cheat sheet
- [Custom Instructions](docs/CUSTOM_INSTRUCTIONS_EXTRACTION.md) - How personalization settings are extracted
- [Schema Notes](docs/SCHEMA_NOTES.md) - Important discoveries about export format

## Architecture

- **Graph Processing:** Backward traversal algorithm for directed acyclic conversation graphs  
- **Content Pipeline:** Multi-stage filtering and transformation with 15+ content type handlers
- **Error Recovery:** Comprehensive defensive parsing with detailed failure analysis
- **Scalability:** Memory-efficient processing of large exports with batch capabilities
- **Data Integrity:** Structured logging and validation throughout extraction pipeline

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing module 'yaml' | `pip install pyyaml` |
| File not found | Check path to conversations.json |
| Memory error | Increase available RAM |
| Some conversations fail | Check `conversion_log.log` for details |

See [Operations Guide](docs/OPERATIONS.md) for comprehensive troubleshooting.

## Related Projects

This tool builds on insights from the ChatGPT extraction community:

- [chatgpt-exporter](https://github.com/pionxzh/chatgpt-exporter) - Browser extension approach
- [chatgpt-history-export-to-md](https://github.com/mohamed-chs/chatgpt-history-export-to-md) - Python extraction tool
- [openai-conversations](https://github.com/sanand0/openai-conversations/) - Analysis framework
- [chatgpt_search](https://github.com/Capitalmind/chatgpt_search) - Search-focused extraction
- [Chat-History-To-Project](https://github.com/Akilaydin/Chat-History-To-Project) - Project organization tool

This tool focuses specifically on complete graph traversal and comprehensive content type handling for the current ChatGPT export format.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Focus on bug reports and reliability improvements over feature additions.
