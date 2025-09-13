#!/usr/bin/env python3
"""Test script to verify metadata enhancements."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from chatgpt_extractor.extractor import ConversationExtractorV2

def test_single_conversation():
    """Extract a single conversation to test metadata."""
    input_file = Path('/mnt/c/chatgpt_history/chatgpt_conversation_json_extractor/my_data/conversations.json')
    output_dir = Path('/mnt/c/chatgpt_history/chatgpt_conversation_json_extractor/chatgpt_conversation_json_extractor/test_output')
    
    # Create test output directory
    output_dir.mkdir(exist_ok=True)
    
    # Load conversations
    with open(input_file, 'r', encoding='utf-8') as f:
        all_conversations = json.load(f)
    
    # Find the specific conversation
    target_id = '68c1c76c-ad4c-8327-98e9-79e173dd434d'  # The Seagull synopsis - has custom instructions
    test_conv = None
    
    for conv in all_conversations:
        if conv.get('id') == target_id:
            test_conv = conv
            break
    
    if not test_conv:
        print(f"Conversation {target_id} not found")
        return
    
    # Save just this conversation to a temp file
    temp_file = Path('/mnt/c/chatgpt_history/chatgpt_conversation_json_extractor/chatgpt_conversation_json_extractor/test_single_conv.json')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump([test_conv], f)
    
    # Extract
    print(f"Extracting conversation: {test_conv.get('title')}")
    extractor = ConversationExtractorV2(str(temp_file), str(output_dir))
    extractor.extract_all()
    
    # Read the output file
    output_files = list(output_dir.glob('*.md'))
    if output_files:
        output_file = output_files[0]
        print(f"\nOutput file: {output_file}")
        
        # Show first 30 lines (the metadata)
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print("\nMetadata header:")
            print("=" * 60)
            for i, line in enumerate(lines[:30]):
                print(line.rstrip())
                if line.strip() == '---' and i > 0:
                    break
    
    # Clean up
    temp_file.unlink()

if __name__ == "__main__":
    test_single_conversation()