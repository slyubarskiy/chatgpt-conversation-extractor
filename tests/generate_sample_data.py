#!/usr/bin/env python3
"""
Generate sample conversation data for testing and benchmarking.
"""

import json
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_conversation(index: int, complexity: str = 'simple') -> dict:
    """Generate a single conversation with specified complexity."""
    
    base_time = int(datetime(2024, 1, 1).timestamp())
    
    if complexity == 'simple':
        # Simple 2-message conversation
        return {
            "id": f"conv-{index:06d}",
            "title": f"Conversation {index}: {random.choice(['Python Help', 'Code Review', 'Debug Issue', 'Learning Question'])}",
            "create_time": base_time + index * 3600,
            "update_time": base_time + index * 3600 + 1800,
            "mapping": {
                "node-1": {
                    "id": "node-1",
                    "parent": None,
                    "children": ["node-2"],
                    "message": None
                },
                "node-2": {
                    "id": "node-2",
                    "parent": "node-1",
                    "children": ["node-3"],
                    "message": {
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": [f"Question {index}: How do I implement {random.choice(['sorting', 'searching', 'hashing', 'recursion'])}?"]
                        }
                    }
                },
                "node-3": {
                    "id": "node-3",
                    "parent": "node-2",
                    "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {
                            "content_type": "text",
                            "parts": [f"Answer {index}: Here's how you can implement that...\n```python\n# Example code\nprint('Hello')\n```"]
                        }
                    }
                }
            },
            "current_node": "node-3",
            "default_model_slug": random.choice(["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"])
        }
    
    elif complexity == 'complex':
        # Complex conversation with branches, multiple content types
        nodes = {"node-1": {"id": "node-1", "parent": None, "children": ["node-2"], "message": None}}
        
        # Add system message
        nodes["node-2"] = {
            "id": "node-2",
            "parent": "node-1",
            "children": ["node-3"],
            "message": {
                "author": {"role": "system"},
                "content": {"content_type": "text", "parts": ["You are a helpful coding assistant."]},
                "metadata": {"is_user_system_message": True}
            }
        }
        
        # Add conversation with branches
        parent = "node-2"
        for i in range(3, 8):
            node_id = f"node-{i}"
            
            # Randomly decide content type
            content_types = ['text', 'code', 'multimodal_text']
            content_type = random.choice(content_types)
            
            if content_type == 'text':
                content = {
                    "content_type": "text",
                    "parts": [f"Message {i}: {random.choice(['Explain', 'Show me', 'How does', 'What is'])} something"]
                }
            elif content_type == 'code':
                content = {
                    "content_type": "code",
                    "text": f"def function_{i}():\n    return {i}",
                    "language": "python"
                }
            else:  # multimodal_text
                content = {
                    "content_type": "multimodal_text",
                    "parts": [
                        f"Text part {i}",
                        {
                            "content_type": "image_asset_pointer",
                            "metadata": {"dalle": {"prompt": f"Image {i}"}}
                        }
                    ]
                }
            
            nodes[node_id] = {
                "id": node_id,
                "parent": parent,
                "children": [],
                "message": {
                    "author": {"role": "user" if i % 2 else "assistant"},
                    "content": content,
                    "metadata": {
                        "citations": [
                            {"metadata": {"url": f"https://example{i}.com", "title": f"Source {i}"}}
                        ] if random.random() > 0.7 else []
                    }
                }
            }
            
            # Update parent's children
            nodes[parent]["children"].append(node_id)
            parent = node_id
        
        # Add a branch (edit)
        nodes["node-3"]["children"].append("node-3b")
        nodes["node-3b"] = {
            "id": "node-3b",
            "parent": "node-3",
            "children": [],
            "message": {
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["Actually, let me rephrase that..."]}
            }
        }
        
        return {
            "id": f"complex-{index:06d}",
            "title": f"Complex Conversation {index}",
            "create_time": base_time + index * 7200,
            "update_time": base_time + index * 7200 + 3600,
            "mapping": nodes,
            "current_node": f"node-7",
            "conversation_template_id": f"g-p-project-{index % 3}" if index % 3 == 0 else None,
            "default_model_slug": "gpt-4",
            "safe_urls": [f"https://safe{index}.com"],
            "moderation_results": []
        }
    
    return generate_conversation(index, 'simple')  # fallback


def main():
    parser = argparse.ArgumentParser(description='Generate sample conversation data')
    parser.add_argument('--size', choices=['small', 'medium', 'large'], 
                       default='medium', help='Dataset size')
    parser.add_argument('--complexity', choices=['simple', 'complex', 'mixed'],
                       default='simple', help='Conversation complexity')
    parser.add_argument('--output', default='sample_conversations.json',
                       help='Output filename')
    
    args = parser.parse_args()
    
    # Determine count based on size
    sizes = {
        'small': 10,
        'medium': 100,
        'large': 1000
    }
    count = sizes[args.size]
    
    print(f"Generating {count} {args.complexity} conversations...")
    
    conversations = []
    for i in range(count):
        if args.complexity == 'mixed':
            # Mix of simple and complex
            complexity = 'complex' if i % 5 == 0 else 'simple'
        else:
            complexity = args.complexity
        
        conversations.append(generate_conversation(i, complexity))
    
    # Save to file
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(conversations, f, indent=2)
    
    print(f"Generated {len(conversations)} conversations")
    print(f"Saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")


if __name__ == '__main__':
    main()