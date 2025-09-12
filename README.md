# ChatGPT Conversation Extractor

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)](setup.py)

Extract and convert ChatGPT conversation exports from JSON to organized Markdown files with comprehensive metadata preservation and error tracking.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run extraction
python extract.py conversations.json output_folder/

# Or use as a module
python -m chatgpt_extractor conversations.json output_folder/
```

## ✨ Features

- **100% Success Rate** - Robust error handling for all edge cases
- **High Performance** - Processes 65-100 conversations/second
- **Schema Evolution** - Tracks format changes automatically
- **Progress Tracking** - Real-time progress with ETA
- **Project Organization** - Auto-groups conversations by project
- **Comprehensive Logging** - Detailed failure analysis

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

### Using pip (when published)

```bash
pip install chatgpt-conversation-extractor
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

**Built with Python** | **Processes 6,000+ conversations in ~100 seconds**