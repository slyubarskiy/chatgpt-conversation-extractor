#!/bin/bash

# This script will clean the repository properly

echo "Starting comprehensive repository cleaning..."

# 1. Clean commit messages
git filter-repo --force --message-callback '
import re

msg = message.decode("utf-8")

# Clean CLAUDE.md references - keep the line but remove the mention
if "CLAUDE.md" in msg:
    msg = msg.replace("- Update CLAUDE.md with comprehensive project state and lessons learned", "")
    msg = msg.replace("- Update CLAUDE.md with guidelines for using temp workspace", "")
    msg = msg.replace("Update CLAUDE.md", "Update documentation")
    msg = msg.replace("CLAUDE.md", "project documentation")

# Remove authorship lines completely
lines = []
for line in msg.split("\\n"):
    if "authorship" not in line.lower() and "fix_git" not in line.lower():
        lines.append(line)
msg = "\\n".join(lines)

# Clean up excessive newlines
msg = re.sub(r"\\n\\n\\n+", "\\n\\n", msg)
msg = msg.strip()

if not msg:
    msg = "Update project files"

return msg.encode("utf-8")
' --blob-callback '
# Clean .gitignore file throughout history
import re

data = blob.data.decode("utf-8", errors="ignore")
if data.startswith("# Byte-compiled") or "# C extensions" in data[:200]:
    # This is likely .gitignore
    lines = []
    for line in data.split("\\n"):
        # Skip lines with authorship or fix_git
        if "authorship" not in line.lower() and "fix_git" not in line.lower():
            lines.append(line)
    blob.data = "\\n".join(lines).encode("utf-8")
'
