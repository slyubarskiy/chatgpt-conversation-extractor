#!/usr/bin/env python3
"""Create a mock conversation with custom instructions to test metadata."""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from chatgpt_extractor.extractor import ConversationExtractorV2

def create_mock_conversation():
    """Create a mock conversation with the expected custom instructions format."""
    
    # Create a mock conversation based on the user's example
    mock_conv = {
        "id": "68c1c76c-ad4c-8327-98e9-79e173dd434d",
        "title": "The Seagull synopsis",
        "create_time": 1726000008.55726,
        "update_time": 1726003938.640054,
        "default_model_slug": "gpt-5",
        "mapping": {
            "root": {
                "id": "root",
                "parent": None,
                "children": ["msg1"],
                "message": None
            },
            "msg1": {
                "id": "msg1",
                "parent": "root",
                "children": ["msg2"],
                "message": {
                    "author": {"role": "system"},
                    "content": {
                        "content_type": "user_editable_context",
                        "text": """The user provided the following information about themselves: Preferred name: Sergey
Role: I'm an experienced leader in Data, AI, and Strategic Business Transformation with 10+ years of driving measurable impact across telecom, tech, and consumer goods. I specialize in turning complex analytics into clear business value—up to £18M on a single project. I am passionate about integrating advanced analytics into everyday operations and marketing, leading high-performing cross-functional teams, and enabling smarter, faster decisions through innovation and insight.
Other Information: Do not search online unless i specifically ask you to.

The user provided the additional info about how they would like you to respond: Be thorough, structured, concise, deep, forward-thinking.
Structure clearly: Use headings, bullets, and sub-bullets to organise content into digestible chunks:
	•	Keep it concise: Short sentences, minimal jargon, avoid long paragraphs.
	•	Highlight the key point quickly: Start with the "main takeaway" before details.
	•	Use emphasis wisely: Bold or italics for important words, but don't overuse.
	•	Provide actionable steps: If advice, break it into simple numbered steps or checklists.
	•	Support memory & focus: End with a short recap ("In short…") or 2–3 takeaways."""
                    },
                    "metadata": {"is_user_system_message": True}
                }
            },
            "msg2": {
                "id": "msg2",
                "parent": "msg1",
                "children": ["msg3"],
                "message": {
                    "author": {"role": "user"},
                    "content": {
                        "content_type": "text",
                        "parts": ["Can you give me a synopsis of Chekhov's 'The Seagull'?"]
                    }
                }
            },
            "msg3": {
                "id": "msg3",
                "parent": "msg2",
                "children": ["msg4"],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "text",
                        "parts": ["# The Seagull by Anton Chekhov - Synopsis\n\n## Main Takeaway\nA tragicomedy about unrequited love, artistic ambition, and generational conflict at a Russian country estate."]
                    }
                }
            },
            "msg4": {
                "id": "msg4",
                "parent": "msg3",
                "children": ["msg5"],
                "message": {
                    "author": {"role": "user"},
                    "content": {
                        "content_type": "text",
                        "parts": ["Can you show me a simple Python function to analyze sentiment?"]
                    }
                }
            },
            "msg5": {
                "id": "msg5",
                "parent": "msg4",
                "children": ["msg6"],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "code",
                        "language": "python",
                        "text": "def analyze_sentiment(text):\n    # Simple sentiment analysis\n    positive_words = ['good', 'great', 'excellent']\n    negative_words = ['bad', 'terrible', 'awful']\n    return 'positive' if any(w in text.lower() for w in positive_words) else 'negative'"
                    }
                }
            },
            "msg6": {
                "id": "msg6",
                "parent": "msg5",
                "children": [],
                "message": {
                    "author": {"role": "user"},
                    "content": {
                        "content_type": "code",
                        "language": "python",
                        "text": "# Testing the function\nprint(analyze_sentiment('This is great!'))"
                    }
                }
            }
        },
        "current_node": "msg6"
    }
    
    return mock_conv

def test_mock_extraction():
    """Test extraction with mock conversation."""
    output_dir = Path('/mnt/c/chatgpt_history/chatgpt_conversation_json_extractor/chatgpt_conversation_json_extractor/test_output')
    output_dir.mkdir(exist_ok=True)
    
    # Create mock conversation
    mock_conv = create_mock_conversation()
    
    # Save to temp file
    temp_file = Path('/mnt/c/chatgpt_history/chatgpt_conversation_json_extractor/chatgpt_conversation_json_extractor/test_mock_conv.json')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump([mock_conv], f)
    
    # Extract
    print(f"Extracting mock conversation: {mock_conv['title']}")
    extractor = ConversationExtractorV2(str(temp_file), str(output_dir))
    extractor.extract_all()
    
    # Read the output
    output_files = list(output_dir.glob('*.md'))
    if output_files:
        output_file = output_files[0]
        print(f"\nOutput file: {output_file.name}")
        
        # Show metadata section
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print("\nMetadata header:")
            print("=" * 60)
            in_metadata = False
            for line in lines:
                if line.strip() == '---':
                    if not in_metadata:
                        in_metadata = True
                        print(line.rstrip())
                    else:
                        print(line.rstrip())
                        break
                elif in_metadata:
                    print(line.rstrip())
    
    # Clean up
    temp_file.unlink()

if __name__ == "__main__":
    test_mock_extraction()