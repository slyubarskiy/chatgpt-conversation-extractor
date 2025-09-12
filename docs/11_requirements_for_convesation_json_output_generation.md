## Additional Requirements for Task Package

The below requirements complement `10_requirements_for_conversation_json_extraction.md`

### Output Format Requirements

1. **File Structure**
   ```
   output_folder/
   ├── Conversation Title 1.md
   ├── Conversation Title 2.md
   ├── Project Name/           # If projects detected
   │   ├── Project Conv 1.md
   │   └── Project Conv 2.md
   ```

2. **Markdown File Format**
   ```markdown
   ---
   # YAML Frontmatter
   id: conversation-uuid
   conversation_id: alternative-id
   title: "Sanitized Title"
   created: 2024-01-01T12:00:00Z
   updated: 2024-01-02T15:30:00Z
   model: gpt-4
   project_id: g-p-uuid         # If applicable
   gizmo_id: g-uuid            # If applicable
   memory_scope: global_enabled
   starred: false
   archived: false
   chat_url: https://chatgpt.com/c/conversation-uuid
   ---
   
   # Conversation Title
   
   ## System
   [Custom instructions if any]
   
   ## User
   Message content with [File: document.pdf] indicators
   
   ## Assistant
   Response with ```python
   code blocks
   ```
   
   **Citations:**
   - [webpage] Title - https://url.com
   
   **Web Search URLs:**
   - https://search-result1.com
   - https://search-result2.com
   ```

3. **Filename Requirements**
   - Use sanitized conversation title
   - Add `(n)` suffix for duplicates
   - Limit to 100 characters
   - Replace invalid chars with `-`

4. **File Metadata**
   - Set file creation time to `conversation.create_time`
   - Set file modification time to `conversation.update_time`
   - Preserve filesystem-compatible timestamps

5. **Project Organization**
   - Group by `conversation_template_id` if present
   - Create subfolders for projects
   - Include project metadata file in project folders

### Processing Requirements

6. **Batch Processing**
   ```python
   # Process multiple conversations efficiently
   for conversation in conversations:
       md_content = process_conversation(conversation)
       save_to_file(md_content, output_folder)
   ```

7. **Progress Reporting**
   ```python
   # Show progress for large exports
   print(f"Processing conversation {i+1}/{total}: {title[:50]}...")
   ```

8. **Error Handling**
   ```python
   # Continue processing even if one conversation fails
   try:
       process_conversation(conv)
   except Exception as e:
       log_error(f"Failed: {conv.get('title', 'Unknown')}: {e}")
       continue
   ```

### Format Adjustments

9. **Section Headers**
   - Use `## User` and `## Assistant` (not `# User`)
   - System prompt as `## System` (only if user-provided)
   - Clear visual separation between messages

10. **Code Block Formatting**
    - Language hint after triple backticks
    - Execution output as ` ```output`
    - Preserve indentation

11. **Special Content Markers**
    - `[File: filename.ext]` for uploads
    - `[Audio transcription]` prefix for audio inputs
    - Skip image placeholders entirely

12. **Citation Formatting**
    ```markdown
    **Citations:**
    - [{type}] {title} - {url}
    ```

13. **URL Lists**
    ```markdown
    **Web Search URLs:**
    - url1
    - url2
    ```

### Implementation Notes for Claude Code

14. **Title Handling**
    ```python
    def prepare_filename(title, occurrence_count):
        # 1. Sanitize title (remove invalid chars)
        # 2. Truncate to 100 chars
        # 3. Add occurrence suffix if needed
        # 4. Ensure doesn't end with period
    ```

15. **YAML Frontmatter Safety**
    ```python
    # Escape quotes in YAML values
    # Handle None values as empty strings
    # Format timestamps as ISO 8601
    ```

16. **Filesystem Compatibility**
    - Handle both Windows and Unix paths
    - Create directories if they don't exist
    - Handle permission errors gracefully

This specification extends the file `10_requirements_for_conversation_json_extraction.md` with markdown file output.