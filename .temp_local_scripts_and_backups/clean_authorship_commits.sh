#!/bin/bash
# Script to clean authorship references from commit messages

git filter-repo --force --message-callback '
import re
msg = message.decode("utf-8")

# List of commits to modify
commits_to_clean = {
    "611f6bb": "Update .gitignore",
    "6248422": "Update .gitignore", 
    "08d3c5e": "Update .gitignore"
}

# Check if this is one of the commits we need to clean
for commit_start, new_msg in commits_to_clean.items():
    if msg.startswith(commit_start):
        return new_msg.encode("utf-8")

# Remove any mention of authorship from all commits
if "authorship" in msg.lower():
    # Replace the message with a generic one
    return "Update .gitignore".encode("utf-8")
    
return message
'
