---
name: Question
about: Ask a question about usage, configuration, or troubleshooting
title: '[QUESTION] '
labels: ['question']
assignees: ''

---

## Question
What would you like to know?

## Context
Please provide context about what you're trying to accomplish:
- What is your goal or use case?
- What have you already tried?
- Where are you getting stuck?

## Environment Details
If relevant to your question:
- OS: [e.g. Windows 10, Ubuntu 20.04, macOS 12.0]
- Python version: [e.g. 3.9.0]
- Input data: [e.g. file size, number of conversations, export date]

## Current Behavior
If applicable, describe what's currently happening:
```
[Paste command output or describe current behavior]
```

## Expected or Desired Outcome
What are you hoping to achieve or what result are you looking for?

## Documentation Checked
Which documentation have you already reviewed?
- [ ] README.md
- [ ] User Guide (docs/USER_GUIDE.md)
- [ ] Technical Reference (docs/TECHNICAL_REFERENCE.md)
- [ ] Architecture docs (docs/ARCHITECTURE.md)
- [ ] Operations Guide (docs/OPERATIONS.md)

## Related Issues
Are there any existing issues or discussions related to your question?

## Additional Information
Any other details that might be helpful in answering your question?

---

## Common Questions

Before submitting, check if your question is answered here:

**Q: How do I get my ChatGPT conversation data?**
A: Go to ChatGPT Settings → Data controls → Export data, then download the conversations.json file.

**Q: The extraction is failing on some conversations. Is this normal?**
A: Yes, a small percentage of failures (typically <1%) is expected due to edge cases in conversation formats. Check the conversion_log.log for details.

**Q: Can I extract only specific conversations?**
A: Currently, the tool processes all conversations in the JSON file. You can manually edit the JSON file to include only desired conversations.

**Q: What's the difference between regular and project conversations?**
A: Project conversations are automatically grouped into separate folders based on their conversation_template_id (starting with 'g-p-').

**Q: How can I contribute to the project?**
A: See CONTRIBUTING.md for guidelines. Focus on bug reports and reliability improvements over new features.