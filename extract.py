#!/usr/bin/env python3
"""
Convenience wrapper for direct execution of ChatGPT Conversation Extractor.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chatgpt_extractor.__main__ import main

if __name__ == "__main__":
    main()
