# Contributing to ChatGPT Conversation Extractor

## Project Context

This tool was created to solve a personal need for extracting ChatGPT conversations reliably. While I'm making it available to help others with the same challenge, please understand that this is **not my full-time project** - I work full-time at Accenture and maintain this in my limited spare time.

## How You Can Help

### Most Valuable Contributions

**Bug Reports & Edge Cases**
- Test with your own conversation exports
- Report specific failures with anonymized examples
- Share new content types or format changes you discover

**Code Improvements**
- Fix bugs you encounter
- Add missing content type handlers
- Improve error handling and logging
- Performance optimizations

**Documentation**
- Fix typos or unclear instructions
- Add examples for new use cases
- Improve installation guides for different platforms

### Less Priority (But Welcome)

**Feature Additions**
- While new features are appreciated, focus on reliability first
- Consider if the feature benefits most users or just specific cases
- Keep backward compatibility in mind

## Contribution Guidelines

### Before Contributing

**Check Existing Issues**
- Search for similar bugs or feature requests
- Comment on existing issues rather than creating duplicates

**Test Your Changes**
- Run the tool on real conversation exports
- Verify your changes don't break existing functionality
- Include test data if possible (anonymized)

### Making Changes

**Pull Request Process**

1. **Fork and Branch**
   ```bash
   git fork https://github.com/yourusername/chatgpt-conversation-extractor
   git checkout -b fix/description-of-fix
   ```

2. **Make Focused Changes**
   - One issue per pull request
   - Keep changes minimal and focused
   - Follow existing code style

3. **Test Thoroughly**
   ```bash
   # Test with your own data
   python extract.py your_conversations.json test_output/
   
   # Run any existing tests
   pytest tests/ (if available)
   ```

4. **Document Your Changes**
   - Clear commit messages
   - Update relevant documentation
   - Explain why the change is needed

### Code Style

**Follow Existing Patterns**
- Use same naming conventions
- Match indentation and formatting
- Add logging for new functionality
- Include error handling

**Defensive Programming**
- Check for None values before accessing
- Use `.get()` with defaults for dictionaries
- Handle unexpected data structures gracefully

### What to Include in Pull Requests

**Required Information**
- What problem does this solve?
- How did you test the change?
- Any new dependencies or requirements?
- Screenshots/logs if relevant

**Bug Fix Example**
```markdown
## Problem
Tool crashes when processing conversations with missing current_node field.

## Solution
Added fallback to find highest-weight leaf node when current_node is None.

## Testing
Tested on export with 47 conversations missing current_node - all now process successfully.

## Files Changed
- extractor.py: Added fallback logic in backward_traverse()
- Added null check in extract_metadata()
```

**Feature Addition Example**
```markdown
## Feature
Add support for new 'canvas' content type found in latest exports.

## Implementation
- Added canvas content type to processor.py
- Extracts collaborative editing content
- Preserves version history in metadata

## Testing
Tested on 3 conversations with canvas content - all extract properly.
```

## Response Expectations

### Timeline
- **Bug fixes**: I'll try to review within 1-2 weeks
- **Features**: May take longer, depending on complexity
- **Documentation**: Usually faster turnaround

### Feedback Style
- Direct and honest feedback focused on code quality
- Suggestions for improvement rather than demands
- May ask for changes or additional testing

## Types of Help Needed

### High Priority
1. **Format Evolution Tracking**
   - Report new content types in schema_evolution.log
   - Share examples of failed extractions
   - Test with latest ChatGPT exports

2. **Cross-Platform Testing**
   - Windows path handling
   - macOS specific issues
   - Different Python versions

3. **Performance Issues**
   - Memory usage with very large files
   - Processing speed bottlenecks
   - Streaming implementation (mentioned in README)

### Medium Priority
1. **Error Handling Improvements**
   - Better recovery from corrupted data
   - More informative error messages
   - Graceful degradation strategies

2. **Documentation**
   - Installation troubleshooting
   - Platform-specific guides
   - FAQ from real user questions

### Lower Priority
1. **New Output Formats**
   - HTML export
   - PDF generation
   - Database integration

2. **UI Improvements**
   - Progress bars
   - Configuration files
   - Interactive selection

## What I Won't Accept

**Scope Creep**
- Features that fundamentally change the tool's purpose
- Complex UI or web interfaces
- Features requiring significant ongoing maintenance

**Poor Quality**
- Code without error handling
- Changes that break existing functionality
- Undocumented or untested modifications

## Getting Started

### First-Time Contributors

1. **Start Small**
   - Fix a typo in documentation
   - Add better error message for common failure
   - Test tool on your own data and report results

2. **Understand the Codebase**
   - Read the architecture documentation
   - Look at existing content type handlers
   - Understand the graph traversal logic

3. **Join the Community**
   - Comment on existing issues
   - Share your use cases
   - Help other users with problems

### For Experienced Developers

**High-Impact Areas**
- Streaming JSON parser implementation
- Memory optimization for large files
- Better project name inference
- Content type auto-detection improvements

## Recognition

**Contributors will be acknowledged in:**
- README.md contributor section
- Release notes for significant contributions
- Documentation for major features

## Questions?

**Before asking:**
- Check existing documentation
- Search closed issues
- Test with minimal example

**How to ask:**
- Include specific error messages
- Share relevant log excerpts (anonymized)
- Describe what you expected vs. what happened
- Include your environment (OS, Python version, file size)

## Final Notes

This project exists because existing tools weren't reliable enough for my needs. The goal is keeping it simple, robust, and maintainable rather than feature-rich. Quality contributions that improve reliability and compatibility are much more valuable than complex new features.

Your time and effort in contributing are genuinely appreciated, especially given this is a spare-time project for all involved.

### Project Leadership Transition

If you're interested in taking a more substantial leadership role or transitioning this project to active maintenance, I'm open to discussing:

**Collaboration Opportunities**
- Co-maintainer status for consistent contributors
- Taking ownership of specific feature areas
- Leading development of major enhancements

**Full Ownership Transfer**
- Complete repository transfer for the right person/team
- Handover documentation and context
- Continued collaboration or clean transition

**What I'm Looking For**
- Demonstrated understanding of the codebase and architecture
- Track record of quality contributions
- Sustainable time commitment for ongoing maintenance
- Vision aligned with reliability and user needs

**Discussion Process**
- Start with consistent contributions over 2-3 months
- Open an issue titled "Project Leadership Discussion"
- We can discuss privately via email after establishing working relationship

This ensures continuity for users while allowing the project to grow beyond my time constraints.