# JSON Output Format Implementation Plan

## Overview
This document tracks the implementation of multi-format output support with subdirectory structure and timestamp synchronization for the ChatGPT conversation extractor (v3.1).

**Feature Branch**: `feature/json-output-format`  
**Worktree Location**: `../chatgpt_json_worktree`  
**Virtual Environment**: `.venv_json`

## Implementation Phases

### Phase 0: Environment Setup ✅
- [x] Create Git worktree at `../chatgpt_json_worktree`
- [x] Create feature branch `feature/json-output-format`
- [x] Set up independent virtual environment `.venv_json`
- [x] Install dependencies (pyyaml)
- [ ] Configure separate log directories
- [ ] Test simultaneous processing capability

### Phase 1: CLI Argument Enhancement
- [ ] Modify `src/chatgpt_extractor/__main__.py`
  - [ ] Add `--output-format {markdown,json,both}` (default: 'markdown')
  - [ ] Add `--json-format {single,multiple}` (default: 'multiple')
  - [ ] Add `--markdown-dir` override option
  - [ ] Add `--json-dir` override option
  - [ ] Add `--json-file` for single JSON path
  - [ ] Add `--preserve-timestamps` boolean (default: True)
  - [ ] Update help text with comprehensive examples
  - [ ] Change default output_dir from 'data/output_md' to 'data/output'
- [ ] Implement validation logic
  - [ ] Mutual exclusion: `--json-dir` vs `--json-file`
  - [ ] Conditional: `--json-format` only with JSON output
  - [ ] Path validation for writable directories
  - [ ] Backward compatibility checks

### Phase 2: Core Architecture Updates
- [ ] Update `ConversationExtractorV2.__init__`
  - [ ] Store output format configuration
  - [ ] Initialize path configuration
  - [ ] Add constants: `JSON_EXPORT_FILENAME_PATTERN`, `TIMESTAMP_FORMAT_ISO8601`
- [ ] Add new core methods
  - [ ] `determine_output_paths()` with quality comments
  - [ ] `generate_json_data()` with quality comments
  - [ ] `save_json_single()` with quality comments
  - [ ] `save_json_multiple()` with quality comments
  - [ ] `synchronize_file_timestamps()` with quality comments
  - [ ] `parse_iso_timestamp()` with quality comments
  - [ ] `_set_windows_creation_time()` with platform docs
  - [ ] `_set_macos_creation_time()` with platform docs
- [ ] Modify existing methods
  - [ ] Update `process_conversation()` return signature
  - [ ] Enhance `extract_all()` for dual-format processing
  - [ ] Rename `save_to_file()` to `save_markdown_file()`

### Phase 3: Directory Structure Implementation
- [ ] Path management
  - [ ] Create `md/` subdirectory logic
  - [ ] Create `json/` subdirectory logic
  - [ ] Preserve project subfolder structure
  - [ ] Handle file collision with numbered suffixes
- [ ] Error handling
  - [ ] Early directory creation with permission checks
  - [ ] Clear error messages for permission failures
  - [ ] Validate paths before processing starts

### Phase 4: JSON Output Implementation
- [ ] JSON structure
  - [ ] Single file with `export_metadata` wrapper
  - [ ] Multiple files with individual conversation objects
  - [ ] Handle all metadata types
  - [ ] ISO 8601 timestamp formatting
- [ ] Processing logic
  - [ ] Incremental JSON building for memory efficiency
  - [ ] Proper serialization of complex types
  - [ ] Track JSON-specific failures separately

### Phase 5: Timestamp Synchronization
- [ ] Core implementation
  - [ ] Parse ISO 8601 with fallback handling
  - [ ] Set creation/modification times per platform
  - [ ] Windows implementation with Win32 API
  - [ ] macOS implementation with xattr
  - [ ] Linux limitation documentation
- [ ] Error resilience
  - [ ] Log failures as warnings (non-blocking)
  - [ ] Handle pre-1970 dates gracefully
  - [ ] Cache parsed timestamps for efficiency

### Phase 6: Progress Reporting Enhancement
- [ ] Update `ProgressTracker` class
  - [ ] Add markdown_processed counter
  - [ ] Add json_processed counter
  - [ ] Track format-specific failures
  - [ ] Include timestamp_sync_failures count
  - [ ] Update display format for dual-format processing
- [ ] Final summary updates
  - [ ] Show format-specific success rates
  - [ ] Display timestamp sync statistics
  - [ ] Enhanced failure categorization

### Phase 7: Comprehensive Testing
- [ ] Unit tests
  - [ ] Create `test_json_output.py`
  - [ ] Create `test_timestamp_sync.py`
  - [ ] Create `test_cli_validation.py`
  - [ ] Create `test_directory_structure.py`
  - [ ] Achieve >70% code coverage
  - [ ] Test execution <30 seconds
- [ ] Integration tests
  - [ ] Test all format combinations
  - [ ] Test directory override scenarios
  - [ ] Test project subfolder preservation
  - [ ] Test empty conversations handling
  - [ ] Test permission error scenarios
  - [ ] Test file collision resolution
  - [ ] Test platform-specific timestamp behavior

### Phase 8: Documentation Updates
- [ ] User-facing documentation
  - [ ] Update README.md with JSON features
  - [ ] Update USER_GUIDE.md with examples
  - [ ] Update QUICK_REFERENCE.md with new arguments
  - [ ] Update OPERATIONS.md with troubleshooting
- [ ] Technical documentation
  - [ ] Update TECHNICAL_REFERENCE.md with JSON spec
  - [ ] Update ARCHITECTURE.md with pipeline changes
  - [ ] Create RELEASE_NOTES_3.1.md
- [ ] In-code documentation
  - [ ] Update --help text with examples
  - [ ] Add platform-specific comments
  - [ ] Document assumptions

### Phase 9: Code Comment Quality Review
- [ ] Review all new/modified code
  - [ ] Replace box-ticking comments
  - [ ] Document WHY decisions
  - [ ] Explain platform workarounds
  - [ ] Document error strategies
  - [ ] Explain performance trade-offs
- [ ] Comment audit checklist
  - [ ] No redundant docstrings
  - [ ] Complex algorithms explained
  - [ ] Platform limitations documented
  - [ ] Integration points explained
  - [ ] Resource management justified
  - [ ] Edge cases documented

### Phase 10: Final Validation
- [ ] Complete validation checklist verification
- [ ] Performance validation with 6885 conversations
- [ ] Code coverage verification
- [ ] Comment quality verification

## Validation Checklist

### CLI Argument Parsing
- [ ] All new arguments properly defined in argparse
- [ ] Default values correctly set and documented in help text
- [ ] Mutually exclusive validation: `--json-dir` and `--json-file`
- [ ] Conditional validation: `--json-format` only valid with JSON output
- [ ] Backward compatibility: existing positional arguments work unchanged

### Directory Structure Implementation
- [ ] `md/` subdirectory created when markdown output enabled
- [ ] `json/` subdirectory created when JSON multiple format enabled
- [ ] Project subfolders preserved in both `md/` and `json/` directories
- [ ] Override arguments bypass automatic subdirectory creation
- [ ] Directory creation includes proper error handling

### JSON Output Functionality
- [ ] `generate_json_data()` produces valid JSON structure
- [ ] Single JSON export includes `export_metadata` with all fields
- [ ] Multiple JSON files contain individual conversation data
- [ ] JSON serialization handles all metadata types
- [ ] Default filename pattern: `conversations_export_YYYYMMDD_HHMMSS.json`

### Timestamp Synchronization
- [ ] `synchronize_file_timestamps()` implemented with cross-platform support
- [ ] ISO 8601 timestamp parsing with error handling
- [ ] File creation time set to `metadata['created']`
- [ ] File modification time set to `metadata['updated']`
- [ ] Platform-specific creation time handling documented
- [ ] Single JSON file preserves processing timestamps
- [ ] Timestamp sync failures logged as warnings

### Error Handling & Resilience
- [ ] JSON serialization failures tracked in `conversion_failures`
- [ ] Partial success scenarios handled gracefully
- [ ] Directory permission errors provide clear messages
- [ ] Invalid timestamp formats handled with fallbacks
- [ ] File collision handling for both formats
- [ ] Progress tracking includes format-specific counts

### Backward Compatibility
- [ ] Existing CLI usage patterns work unchanged
- [ ] Markdown-only output behavior preserved
- [ ] All existing metadata fields preserved
- [ ] Project subfolder structure maintained
- [ ] Default output directory change documented

### Testing Coverage
- [ ] All new public methods have test cases
- [ ] Critical failure scenarios covered
- [ ] Code coverage exceeds 70%
- [ ] Platform-specific code paths tested/mocked
- [ ] Backward compatibility verified
- [ ] Test execution time under 30 seconds

### Code Quality & Production Readiness

#### Code Architecture & Patterns
- [ ] New methods follow snake_case naming convention
- [ ] Method length under 50 lines
- [ ] Single responsibility principle maintained
- [ ] Dependency injection preserved
- [ ] No circular imports introduced
- [ ] Constants defined at module level

#### Type Hints & Documentation
- [ ] All methods include comprehensive type hints
- [ ] Docstrings follow existing format
- [ ] Complex type unions documented
- [ ] Return type `None` explicitly specified
- [ ] Generic types properly parameterized

#### Defensive Programming
- [ ] Null checking follows existing patterns
- [ ] List/dict access includes bounds checking
- [ ] External data validated before use
- [ ] Graceful degradation for non-critical failures
- [ ] Input sanitization for user-provided paths

#### Error Handling Consistency
- [ ] Exception handling follows `log_exception()` pattern
- [ ] Non-critical failures use `logger.warning()`
- [ ] Critical failures bubble up to halt processing
- [ ] Exception context strings actionable
- [ ] Try-except blocks scoped to specific operations

#### Logging Integration
- [ ] New functionality uses `get_logger(__name__)`
- [ ] Log levels appropriate (DEBUG/INFO/WARNING/ERROR)
- [ ] Progress reporting includes new metrics
- [ ] Schema tracker extended for JSON processing
- [ ] Failure categorization enhanced

#### Cross-Platform Considerations
- [ ] File path handling uses `pathlib.Path`
- [ ] Platform-specific code isolated in methods
- [ ] Fallback behavior documented
- [ ] No hardcoded path separators
- [ ] Platform imports wrapped in try-except

#### Performance & Resource Management
- [ ] Large JSON structures processed incrementally
- [ ] File handles closed with context managers
- [ ] No unnecessary data copying in loops
- [ ] Timestamp parsing cached when reused
- [ ] Progress updates throttled (5-second interval)

#### Comment Quality Standards
- [ ] Comments explain WHY not WHAT
- [ ] Context over syntax in documentation
- [ ] Edge case documentation included
- [ ] Integration complexity documented
- [ ] Performance trade-offs explained
- [ ] Platform workarounds with issue context
- [ ] No redundant docstrings
- [ ] Complex algorithms have breakdowns
- [ ] Critical assumptions documented
- [ ] TODO comments include issue numbers
- [ ] Business logic rationale provided

#### Production Deployment Readiness
- [ ] New CLI arguments backward compatible
- [ ] Default behavior unchanged for existing patterns
- [ ] Failure modes degrade gracefully
- [ ] Resource cleanup handled properly
- [ ] Version compatibility maintained
- [ ] Migration path documented

### Documentation
- [ ] README.md updated incrementally
- [ ] TECHNICAL_REFERENCE.md updated
- [ ] QUICK_REFERENCE.md updated
- [ ] OPERATIONS.md updated
- [ ] USER_GUIDE.md updated with examples
- [ ] RELEASE_NOTES_3.1.md created
- [ ] Help text includes comprehensive examples

## Progress Log

### 2025-09-13
- ✅ Created Git worktree at `../chatgpt_json_worktree`
- ✅ Set up feature branch `feature/json-output-format`
- ✅ Created independent virtual environment `.venv_json`
- ✅ Created this implementation plan document

## Notes

- Platform-specific timestamp code requires optional dependencies (pywin32 for Windows)
- Linux creation time setting not supported by filesystem - document limitation
- Single JSON file intentionally uses processing timestamps for consolidation timing
- Directory structure change (data/output_md → data/output) is minor breaking change

## Next Steps

1. Configure separate log directories for worktree
2. Test simultaneous processing capability
3. Begin Phase 1: CLI argument implementation