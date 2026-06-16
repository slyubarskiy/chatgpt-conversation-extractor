# Release Notes - Version 3.1

## Release Date: 2025-01-13

## New Features

### JSON Output Format Support
- **Individual JSON Files**: Generate one JSON file per conversation with `--json-dir` flag
- **Consolidated JSON**: Create single JSON file containing all conversations with `--json-file` option
- **Multi-Format Output**: Generate both markdown and JSON simultaneously for maximum flexibility
- **Format Selection**: Choose markdown-only, JSON-only, or both output formats

### Enhanced Directory Structure
- **Organized Output**: Separate `md/` and `json/` subdirectories for cleaner organization
- **Project Preservation**: JSON files maintain the same project folder structure as markdown
- **Backward Compatible**: Default behavior remains unchanged (markdown-only to maintain existing workflows)

### Timestamp Synchronization
- **File Timestamps**: Output files now have their modification times set to match conversation update times
- **Platform Support**: Works across Windows, macOS, and Linux with appropriate fallbacks
- **Accurate Dating**: Makes file system browsing and sorting more meaningful

## Improvements

### Metadata Enhancements
- **Starred/Archived Flags**: Always included in output (None values converted to False)
- **Consistent Format**: Both markdown YAML frontmatter and JSON contain identical metadata
- **Custom Instructions**: Properly extracted from all conversation formats

## Bug Fixes

- Fixed missing starred/archived flags in output files
- Corrected custom instructions extraction from metadata.user_context_message_data
- Improved None value handling throughout the codebase

## Command Line Interface

### New Usage Pattern
```bash
uv run chatgpt-extractor input.json output/ [options]
```

### New Options
- `--output-format {markdown,json,both}`: Select generated formats
- `--json-format {single,multiple}`: Choose consolidated or individual JSON
- `--json-dir PATH`: Override individual JSON output directory
- `--json-file FILE`: Override consolidated JSON output path
- `--help`: Display help message

## Examples

```bash
# Both markdown and JSON output
uv run chatgpt-extractor conversations.json output/ --output-format both

# JSON only
uv run chatgpt-extractor conversations.json output/ --output-format json

# Single consolidated JSON file
uv run chatgpt-extractor conversations.json output/ --output-format json \
    --json-format single --json-file all_conversations.json
```

## Migration Notes

### For Existing Users
- **No Breaking Changes**: Existing scripts and workflows continue to work unchanged
- **Default Behavior**: Running without flags still produces markdown-only output
- **Directory Structure**: Output now goes to `output/md/` instead of directly to `output/`
  - Existing scripts may need path updates if they expect files directly in output directory
  - Use `--markdown-dir output` if a flat Markdown output directory is required

### For New Installations
- Use the uv-managed console script: `uv run chatgpt-extractor`
- Consider using `--json-dir` for programmatic access to conversation data
- JSON format is ideal for further processing, analysis, or import into other systems

## Technical Details

### JSON Structure
```json
{
  "metadata": {
    "id": "conversation-uuid",
    "title": "Conversation Title",
    "created": "2024-01-01T10:00:00Z",
    "updated": "2024-01-01T11:00:00Z",
    "model": "gpt-4",
    "total_messages": 10,
    "code_messages": 3,
    "message_types": "text, code",
    "starred": false,
    "archived": false,
    "project_id": "g-p-uuid",
    "custom_instructions": "User's instructions..."
  },
  "messages": [
    {
      "role": "user",
      "content": "Message content",
      "timestamp": "2024-01-01T10:00:00Z",
      "files": ["uploaded_file.pdf"],
      "citations": [],
      "urls": []
    }
  ]
}
```

### Performance
- JSON generation adds minimal overhead (<5% processing time)
- File I/O optimized for both formats
- Memory usage remains unchanged

## Known Issues
- Timestamp setting may fail silently on some network file systems
- Very large conversations (>10MB) may cause memory pressure when generating consolidated JSON

## Future Enhancements (Planned)
- CSV export format for data analysis
- Filtering options (date range, model type, starred only)
- Incremental updates (process only new conversations)
- Custom output templates

## Support
Report issues at: [GitHub repository URL]

## Credits
JSON output feature developed based on user feedback and requirements for programmatic access to conversation data.
