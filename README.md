# ChatGPT Conversation Extractor

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)](setup.py)

Extract and convert ChatGPT conversation exports from JSON to organized Markdown files with comprehensive metadata preservation and error tracking.

# ChatGPT Conversation Extractor

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]

A Python tool that reliably extracts ChatGPT conversations from JSON exports into searchable Markdown files, built after finding existing solutions outdated or incomplete.

## Why This Tool Exists

After accumulating thousands of ChatGPT conversations, I needed a reliable way to extract and organize them. I tested numerous existing tools (both open-source and commercial) and found common issues:
- Many haven't been updated for ChatGPT's current export format
- Silent omission of messages due to incorrect graph traversal
- Limited or missing metadata preservation
- Incomplete handling of content types (code, files, web searches, etc.)

This tool prioritizes **completeness and transparency** - you control what gets extracted versus filtered, with detailed logging of any skipped content.

## What Gets Extracted

### Included ✓
- All user messages
- All assistant responses
- Custom instructions (system prompts)
- Code blocks with syntax highlighting
- File attachment references
- Web search queries and results
- Citations with URLs
- DALL-E image generation prompts
- Message timestamps and model versions
- Project organization (for ChatGPT Projects)

### Filtered Out ✗
- Tool/plugin internal messages (except DALL-E)
- Hidden system messages
- Internal reasoning traces
- Model's thinking process
- Empty placeholder messages
- Alternative message branches (only active branch extracted)

Every filtered item is logged in `schema_evolution.log` for transparency.

## Key Features

- **Complete extraction**: Properly traverses the conversation graph to capture all active messages
- **Robust parsing**: Handles 15+ content types with defensive error handling
- **Detailed metadata**: Preserves timestamps, models, URLs, citations
- **Project organisation**: Automatically groups ChatGPT Project conversations
- **Transparent filtering**: Logs what's excluded and why

## Performance tested

Tested on personal export: c. 7k conversations (c.500MB JSON)
- Processing time: ~100 seconds
- Success rate: 100% (failures logged with details)
- Output: c. 7k Markdown files organized by project

## Planned Enhancements

Features contemplated but not yet implemented:

- Intelligent project naming: Analyze conversations to generate meaningful folder names (currently uses project IDs)
- Incremental updates: Process only new conversations since last extraction
- Streaming mode: Process large exports without loading entire file into memory
- Custom filtering: Configure what content types to include/exclude
- Export formats: HTML, PDF, or database output options
- Conversation search: Built-in search across extracted content

**Contributions welcome** - see **CONTRIBUTING.md** for guidelines.


## Technical Details

The extractor handles several complexities in ChatGPT's export format:
1. **Graph traversal**: Conversations aren't simple arrays but directed graphs with branches. The tool uses backward traversal from the current node to reconstruct the active conversation path.
2. **Content type handling**: 15+ different content structures, each requiring specific parsing logic.
3. **Defensive parsing**: Comprehensive null checks and error handling after analyzing failure patterns across thousands of conversations.
4. **URL extraction**: Captures URLs from 6+ different locations in the data structure (citations, safe_urls, content fields, etc.)

See [Architecture Documentation](docs/ARCHITECTURE.md) for implementation details.

## Comparison with Other Tools

| Feature | This Tool | Others Tested |
|---------|-----------|---------------|
| Current format support | ✓ Full | Partial/Outdated |
| Graph traversal | ✓ Complete | Often incomplete |
| Metadata preservation | ✓ Comprehensive | Limited |
| Error handling | ✓ Detailed logging | Silent failures |
| Project organization | ✓ Automatic | Usually missing |
| Filtered content transparency | ✓ Logged | Hidden |


## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run extraction
python extract.py conversations.json output_folder/

# Or use as a module
python -m chatgpt_extractor conversations.json output_folder/
```

## Output Structure 

### Output Folders and files 

output/
├── Regular_Conversation.md          # Standard conversations
├── Technical_Discussion.md
├── project_g-p-abc123/              # ChatGPT Projects
│   ├── Project_Analysis.md
│   └── Project_Planning.md
├── schema_evolution.log             # Unknown patterns found
└── conversion_log.log               # Extraction failures (if any)

### Each Markdown file contains 

#### Metadata
---
id: unique-conversation-id
title: "Conversation Title"
created: 2024-01-15T10:30:00Z
updated: 2024-01-15T11:45:00Z
model: gpt-4
project_id: g-p-abc123  # If part of a project
chat_url: https://chatgpt.com/c/unique-conversation-id
---

#### # Conversation Title

#### ## System
[Your custom instructions appear here]

#### ## User
Your message with [File: document.pdf] references

#### ## Assistant
Response with preserved formatting...


## 📦 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/chatgpt-conversation-extractor.git
cd chatgpt-conversation-extractor

# Install dependencies
pip install -r requirements.txt

# Install in development mode (optional)
pip install -e .
```


## 📖 Usage

### Basic Usage

```bash
# Use default paths (data/raw/conversations.json -> data/output_md/)
python extract.py

# Specify custom paths
python extract.py /path/to/conversations.json /path/to/output/

# Run with failure analysis
python extract.py --analyze-failures
```

### As a Python Module

```python
from chatgpt_extractor import ConversationExtractorV2

# Initialize extractor
extractor = ConversationExtractorV2(
    input_file='conversations.json',
    output_dir='output_md/'
)

# Run extraction
extractor.extract_all()
```

### Getting Your ChatGPT Data

1. Log in to [ChatGPT](https://chat.openai.com)
2. Go to Settings → Data controls → Export data
3. Click "Export" and wait for the email
4. Download and extract `conversations.json` from the ZIP

## 📂 Output Structure

```
output_md/
├── Regular Conversation.md           # Standard conversations
├── Another Conversation.md
├── g-p-xxxxx/                        # Project conversations
│   ├── Project Conv 1.md
│   └── Project Conv 2.md
├── schema_evolution.log              # Format tracking
└── conversion_log.log                # Failure details (if any)
```

### Markdown Format

Each conversation is saved with:
- YAML frontmatter (metadata)
- Formatted messages with roles
- Code blocks with syntax highlighting
- Citations and web URLs
- File attachment indicators

## 🔧 Development

### Project Structure

```
chatgpt-conversation-extractor/
├── src/chatgpt_extractor/     # Main package
│   ├── extractor.py           # Core extractor class
│   ├── processors.py          # Message processing
│   └── trackers.py            # Progress & schema tracking
├── docs/                      # Documentation
├── tests/                     # Test suite
└── extract.py                 # CLI wrapper
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=chatgpt_extractor
```

### Code Style

```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/
```

## 📊 Performance

- **Success Rate**: 99-100%
- **Processing Speed**: 65-100 conversations/second
- **Memory Usage**: ~1GB for 500MB input
- **Large File Support**: Tested with 6,000+ conversations

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Missing module 'yaml' | `pip install pyyaml` |
| File not found | Check path exists |
| Memory error | Increase available RAM |
| Some conversations fail | Check `conversion_log.log` |

### Getting Help

1. Check the [documentation](docs/)
2. Review [USER_GUIDE.md](docs/USER_GUIDE.md)
3. See [OPERATIONS.md](docs/OPERATIONS.md) for troubleshooting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- OpenAI for ChatGPT and the export format
- Community feedback for edge case discovery
- All contributors to this project

## 📚 Documentation

- [User Guide](docs/USER_GUIDE.md) - Installation and usage
- [Architecture](docs/ARCHITECTURE.md) - System design
- [Technical Reference](docs/TECHNICAL_REFERENCE.md) - API documentation
- [Operations](docs/OPERATIONS.md) - Troubleshooting guide

---

## About

Built by Sergey Lyubarskiy, I specialise in Data & AI transformations. I and needed a reliable tool to manage my ChatGPT conversation. I work at Accenture, opinions are my own.
