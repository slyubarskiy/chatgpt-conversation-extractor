## Additional requirements: Schema Evolution Handling

Implement defensive extraction with logging:

1. **Detection**: Log all unknown fields, content types, and structures
2. **Continuation**: Never fail entire extraction due to unknown elements
3. **Fallback**: Use generic extraction for unknown content types
4. **Reporting**: Generate schema_evolution.log with statistics
5. **Samples**: Include conversation IDs for investigation

Priority order:
- Extract known content successfully (highest)
- Log unknown patterns for future updates (high)
- Attempt generic extraction of unknown content (medium)
- Skip only if extraction would corrupt data (low)

Output both:
- markdown files in data/output_md/ folder
- schema_evolution.log (unknown patterns and statistics)


**Critical Areas to Monitor**:

```python
SCHEMA_EVOLUTION_MONITORS = {
    'content_types': set(),  # Track all seen
    'author_roles': set(),   # Beyond system/user/assistant/tool
    'recipient_values': set(),  # New tools
    'metadata_keys': set(),  # New metadata fields
    'part_types': set(),     # In multimodal content
    'finish_types': set(),   # New completion types
}
```

These requirements complement 
- `10_requirements_for_conversation_json_extraction.md`
- `11_requirements_for_convesation_json_output_generation.md`