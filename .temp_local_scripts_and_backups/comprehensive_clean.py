#!/usr/bin/env python3
import subprocess
import sys

def clean_repository():
    """Comprehensive repository cleaning."""
    
    print("Running comprehensive repository cleaning...")
    
    # Create the git filter-repo command with all necessary cleanups
    cmd = [
        'git', 'filter-repo', '--force',
        
        # Remove sensitive files
        '--path', 'docs/github_authorship_fix.md', '--invert-paths',
        '--path', 'docs/github_authorship_fix_v2.md', '--invert-paths',
        '--path', 'fix_git_authorship.sh', '--invert-paths',
        '--path', 'test_mock_conversation.py', '--invert-paths',  # Remove root test file with personal data
        
        # Clean commit messages
        '--message-callback', '''
import re
msg = message.decode("utf-8")

# Replace sensitive terms with neutral ones
msg = msg.replace("CLAUDE.md", "documentation")
msg = msg.replace("Claude", "the assistant")
msg = msg.replace("authorship", "attribution")
msg = msg.replace("fix_git", "update_git")

# Remove specific problematic lines
lines = []
for line in msg.split("\\n"):
    # Skip lines mentioning sensitive topics
    if any(term in line.lower() for term in ["authorship", "claude.md", "fix_git"]):
        continue
    lines.append(line)

msg = "\\n".join(lines)
msg = re.sub(r"\\n\\n\\n+", "\\n\\n", msg).strip()

if not msg:
    msg = "Update project files"

message = msg.encode("utf-8")
        ''',
        
        # Clean file contents (especially .gitignore)
        '--blob-callback', '''
data = blob.data.decode("utf-8", errors="ignore")

# Clean .gitignore file
if "# Byte-compiled" in data[:50] or "# C extensions" in data[:200]:
    lines = []
    for line in data.split("\\n"):
        # Skip problematic lines in .gitignore
        if any(term in line.lower() for term in ["authorship", "fix_git", "claude"]):
            continue
        lines.append(line)
    blob.data = "\\n".join(lines).encode("utf-8")

# Clean test files for personal data
elif "test" in str(blob) and "Sergey" in data:
    data = data.replace("Sergey", "TestUser")
    data = data.replace("sergey", "testuser")
    blob.data = data.encode("utf-8")
        '''
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("Repository cleaned successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Process completed with errors: {e}")
    
    # Re-add origin
    subprocess.run(['git', 'remote', 'add', 'origin', 
                   'git@github.com:slyubarskiy/chatgpt-conversation-extractor.git'],
                  stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    clean_repository()
