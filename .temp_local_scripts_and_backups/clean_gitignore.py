#!/usr/bin/env python3
import sys

# Read from stdin
content = sys.stdin.read()

# Remove any lines containing "authorship" or "fix_git" 
lines = content.split('\n')
filtered_lines = []

for line in lines:
    lower_line = line.lower()
    if 'authorship' not in lower_line and 'fix_git' not in lower_line:
        filtered_lines.append(line)

# Output the cleaned content
print('\n'.join(filtered_lines), end='')
