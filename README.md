# ChatGPT Conversation JSON Extractor

Extracts and processes ChatGPT conversation exports into clean, readable markdown files with comprehensive metadata preservation and error tracking.

## About This Fork

This fork is maintained for the workflow described in
[Export ChatGPT Chats to Markdown for Desktop Search](https://weisser-zwerg.dev/posts/quick-tip-nugget-export-chatgpt-to-markdown-for-desktop-search).
The goal is to turn ChatGPT export data into local Markdown files that can be
indexed by desktop search tools such as Recoll or DocFetcher.

The most important fork-specific context is the appendix
[Privacy Portal flow and changed export format](https://weisser-zwerg.dev/posts/quick-tip-nugget-export-chatgpt-to-markdown-for-desktop-search/#privacy-portal-flow-and-changed-export-format).
Newer Privacy Portal exports may no longer contain a single top-level
`conversations.json`. The main export ZIP can contain nested ZIP files under
`User Online Activity/`; the chat data is inside
`Conversations__*-chatgpt-*.zip` and can be split across files such as
`conversations-000.json`, `conversations-001.json`, etc. This fork automates
running the extractor once for each split file while writing all results into
the same output directory.

It also preserves more source-link data from newer exports by reading
message-level metadata such as `safe_urls`, `search_result_groups`, and
`content_references`, not only the older conversation-level URL fields.

## Features

- Processes ChatGPT `conversations.json` export files
- Works with split export files such as `conversations-000.json`, `conversations-001.json`, etc. when newer exports are partitioned
- Converts complex conversation graphs to linear transcripts
- Filters out most system messages (keeps at most one user-system prompt) and hidden/tool messages, except when they contain meaningful content.
- Preserves code blocks, citations, and file references
- Extracts URLs from both older conversation-level metadata and newer message-level metadata such as `safe_urls`, `search_result_groups`, and `content_references`
- Groups conversations by project automatically
- Handles 6000+ conversations efficiently with detailed logging
- Visibility to schema evolution for transparency
- Filters certain hidden content and revision history
- Multiple output formats: Markdown, JSON, or both simultaneously
- Timestamp preservation: Maintains original creation/update times on files

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) for dependency management and command execution
- 2GB+ RAM for large exports (500MB+ JSON files)

## Getting Your ChatGPT Data

1. Log in to [ChatGPT](https://chat.openai.com)
2. Go to Settings → Data controls → Export data
3. Click "Export" and wait for the email (usually within 24 hours)
4. Download and extract the ZIP file

Note:

- Some newer exports, especially Privacy Portal exports, may put the actual chat export in a nested `Conversations__*-chatgpt-*.zip`.
- Extracting that nested conversations ZIP produces split files such as `conversations-000.json`, `conversations-001.json`, etc. instead of one top-level `conversations.json`.
- This tool can be run against each split file separately and write into the same output directory.
- See the blog appendix on the [Privacy Portal flow and changed export format](https://weisser-zwerg.dev/posts/quick-tip-nugget-export-chatgpt-to-markdown-for-desktop-search/#privacy-portal-flow-and-changed-export-format) for the rationale behind this fork and the split-file workflow.

## Privacy Portal Makefile Workflow

The included [Makefile](Makefile) automates the newer Privacy Portal layout.
It assumes this repository is cloned inside the `User Online Activity/`
directory.

After extracting the top-level Privacy Portal ZIP, `User Online Activity/`
may initially contain only nested ZIP files:

```
User Online Activity/
├── Ads__<export-id>-ads-0001.zip
├── Conversations__<export-id>-chatgpt-0001.zip
├── Files__<export-id>-files-0001.zip
└── chatgpt-conversation-extractor/
```

For Markdown conversation generation, this repository only needs the nested
`Conversations__*-chatgpt-*.zip`. The `Ads__...zip` and `Files__...zip`
archives are not required by the current extractor workflow.

Extract the nested conversations ZIP, then process the resulting shards:

```bash
make extract-conversations-zip
make list-inputs
make extract
```

`make extract-conversations-zip` runs `unzip -n` against the discovered
`../Conversations__*-chatgpt-*.zip`, creating files such as
`../conversations-000.json`, `../conversations-001.json`, etc. without
overwriting existing files. `make extract` installs the package with `uv`,
processes every discovered `../conversations.json` or
`../conversations-*.json` file, and writes all results into the same `output/`
tree. Markdown output lands in `output/md/`. File timestamp preservation is
enabled by default.

Useful overrides:

```bash
# Process a different Privacy Portal directory
make extract-conversations-zip INPUT_DIR="/path/to/User Online Activity"
make extract INPUT_DIR="/path/to/User Online Activity"

# Extract a specific nested conversations ZIP
make extract-conversations-zip CONVERSATIONS_ZIP="/path/to/Conversations__...-chatgpt-0001.zip"

# Process one explicit file
make extract INPUT=/path/to/conversations-000.json

# Generate both Markdown and JSON
make extract FORMAT=both OUTPUT=./output

# Resolve Custom GPT names with an optional sidecar file
make extract GPT_NAMES_XLSX=/path/to/GPT_Names.xlsx
```

## Quick Start

```bash
# Install dependencies into .venv using the repo-local .uv-cache
uv sync --group dev

# Default: extract to Markdown
uv run chatgpt-extractor data/raw/conversations.json data/output

# JSON only
uv run chatgpt-extractor --output-format json

or

uv run chatgpt-extractor data/raw/conversations.json data/output --output-format json

# Both Markdown and JSON
uv run chatgpt-extractor --output-format both

# JSON as a single consolidated file
uv run chatgpt-extractor --output-format json --json-format single --json-file all_conversations.json

# JSON as multiple files in custom directory
uv run chatgpt-extractor --output-format json --json-format multiple --json-dir custom/json/

# Markdown in a custom directory
uv run chatgpt-extractor --output-format markdown --markdown-dir custom/md/

# Disable timestamp syncing (use current system time for file timestamps)
uv run chatgpt-extractor --preserve-timestamps false

# Suppress Custom GPT / per-turn model / plugin metadata (revert to pre-feature output)
uv run chatgpt-extractor --no-gpt-metadata

# Resolve Custom GPT names via a sidecar xlsx (id -> human-readable name)
uv run chatgpt-extractor --gpt-names-xlsx /path/to/GPT_Names.xlsx

# Run failure analysis if conversion issues occurred
uv run chatgpt-extractor --analyze-failures

# Enable debug logging for troubleshooting
uv run chatgpt-extractor --debug

```

## Output Structure

```
data/output/
├── md/                         # Markdown output (if enabled)
│   ├── Regular Conversation 1.md
│   ├── Regular Conversation 2.md
│   └── g-p-XXXXXXXX/          # Project folders
│       ├── Project Conv 1.md
│       └── Project Conv 2.md
├── json/                       # # JSON output (if --output-format includes json & --json-format multiple, default: data/output/json/)
│   ├── Regular Conversation 1.json
│   ├── Regular Conversation 2.json
│   └── g-p-XXXXXXXX/
│       ├── Project Conv 1.json
│       └── Project Conv 2.json
├── all_conversations.json      # Single file (if --output-format json and --json-format single with --json-file specified)
├── schema_evolution.log        # Format tracking (only if enabled in extractor implementation)
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
- **URL extraction**: Reads citations, content URL fields, conversation-level `safe_urls`, and newer message metadata structures like `safe_urls`, `search_result_groups`, and `content_references`
- **Project detection**: Groups by `conversation_template_id` pattern
- **Error handling**: Comprehensive logging with recovery mechanisms

## Performance

- **Processed:** 7,000 conversations (500 MB JSON export)
- **Performance:** <5 minutes end-to-end processing
- **Success Rate:** 99.5%+ with comprehensive error logging
- **Output:** 135MB structured markdown across project folders
- **Architecture:** Memory-efficient graph traversal with defensive parsing

**Migration Note (v3.1):**  
 - Default output directory changed from `data/output_md` to `data/output`.  
 - Markdown files are now stored under `data/output/md/` by default.  
 - Use `--markdown-dir` to specify a custom location without the subdirectory.  

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
| Missing module 'yaml' | Run `uv sync --group dev` from the repository root |
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
