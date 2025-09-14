#!/usr/bin/env python3
import re

def clean_message(msg):
    """Clean commit message of sensitive references."""
    
    # Remove any line mentioning CLAUDE.md
    lines = msg.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Skip lines that mention CLAUDE.md
        if 'CLAUDE.md' in line:
            continue
        # Skip lines about authorship
        if 'authorship' in line.lower():
            continue
        # Skip lines about fix_git
        if 'fix_git' in line.lower():
            continue
        cleaned_lines.append(line)
    
    # Rejoin and clean up extra newlines
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n\n+', '\n\n', result).strip()
    
    # If message becomes empty, provide a default
    if not result or result.isspace():
        result = "Update project files"
    
    return result

# Read from stdin
import sys
msg = sys.stdin.read()
print(clean_message(msg))
