# ChatGPT Conversation JSON Extractor

Extracts and processes ChatGPT conversation exports into clean, readable markdown files with comprehensive metadata preservation and error tracking.

## Features

- Processes ChatGPT `conversations.json` export files
- Converts complex conversation graphs to linear transcripts
- Filters out system messages and hidden content
- Preserves code blocks, citations, and file references
- Groups conversations by project automatically
- Handles 6000+ conversations efficiently with detailed logging
- Visibility to schema evolution for transparency.

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

# Extract all conversations
python extract_conversations.py data/raw/conversations.json data/output_md

# Or specify custom paths
python extract_conversations.py /path/to/conversations.json /path/to/output
```

## Output Structure

```
data/output_md/
├── Regular Conversation 1.md
├── Regular Conversation 2.md
├── project_XXXXXXXX/           # Project folders
│   ├── Project Conv 1.md
│   └── Project Conv 2.md
├── schema_evolution.log        # Format tracking
└── conversion_log.log          # Failure details (if any)
```

## Markdown Format

Each markdown file includes:
- YAML frontmatter with metadata (ID, timestamps, model, project)
- Conversation title as header
- User and assistant messages with role indicators
- Code blocks with syntax highlighting
- Citations and web URLs
- File upload indicators (`[File: document.pdf]`)

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