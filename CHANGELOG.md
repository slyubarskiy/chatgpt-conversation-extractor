# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-12

### Added
- Complete modular architecture with separate components
- Schema evolution tracking for unknown patterns
- Real-time progress indication with ETA
- Comprehensive error logging and failure analysis
- Project folder organization for conversations
- Web URL extraction from 6+ sources
- Citation validation and deduplication
- Graph index tracking for proper message merging
- Support for 11 content types
- Backward traversal algorithm (O(n) complexity)
- YAML frontmatter in markdown output
- Automatic branch exclusion in conversations
- Support for multimodal content (images, audio, video)
- Custom instructions extraction
- DALL-E image prompt preservation

### Changed
- Refactored into modular package structure
- Improved message continuation merging with validation
- Enhanced URL extraction with multiple sources
- Better handling of None values throughout
- Optimized performance to 65-100 conversations/second

### Fixed
- NoneType error in DALL-E metadata checking (10% of failures)
- Python 're' module scoping issue (89% of failures)
- Message merging validation using graph indices
- Custom instructions extraction from multiple wrapper formats
- Empty parts array handling in multimodal content

### Performance
- Success rate: 99-100%
- Processing speed: 65-100 conversations/second
- Memory usage: <2GB for 500MB input files
- Tested with 6,885 conversations

## [1.0.0] - 2025-01-01

### Added
- Initial release
- Basic extraction functionality
- Simple markdown output
- 92% success rate before fixes

---

For detailed release notes, see the [GitHub Releases](https://github.com/yourusername/chatgpt-conversation-extractor/releases) page.