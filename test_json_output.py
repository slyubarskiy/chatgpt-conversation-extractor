#!/usr/bin/env python3
"""
Quick test script for JSON output functionality.
Tests both single and multiple JSON formats with a minimal dataset.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def create_test_conversation():
    """Create a minimal test conversation."""
    return {
        "id": "test-conv-001",
        "title": "Test JSON Output",
        "create_time": 1704067200.0,  # 2024-01-01 00:00:00 UTC
        "update_time": 1704153600.0,  # 2024-01-02 00:00:00 UTC
        "default_model_slug": "gpt-4",
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
                    "author": {"role": "user"},
                    "content": {
                        "content_type": "text",
                        "parts": ["Test question about JSON output"]
                    }
                }
            },
            "msg2": {
                "id": "msg2",
                "parent": "msg1",
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "text",
                        "parts": ["This is a test response for JSON output verification."]
                    }
                }
            }
        },
        "current_node": "msg2"
    }

def test_json_output():
    """Test JSON output generation."""
    from chatgpt_extractor.extractor import ConversationExtractorV2
    
    # Create test data
    test_conversations = [create_test_conversation()]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save test data
        input_file = Path(tmpdir) / "test_conversations.json"
        with open(input_file, 'w') as f:
            json.dump(test_conversations, f)
        
        output_dir = Path(tmpdir) / "output"
        
        print("Testing JSON output formats...")
        print("=" * 60)
        
        # Test 1: Multiple JSON files
        print("\n1. Testing multiple JSON format...")
        extractor = ConversationExtractorV2(
            input_file=str(input_file),
            output_dir=str(output_dir / "test1"),
            output_format='json',
            json_format='multiple',
            preserve_timestamps=False  # Disable for testing
        )
        extractor.extract_all()
        
        # Check output
        json_files = list((output_dir / "test1" / "json").glob("*.json"))
        assert len(json_files) == 1, f"Expected 1 JSON file, got {len(json_files)}"
        
        with open(json_files[0]) as f:
            data = json.load(f)
            assert data['id'] == 'test-conv-001'
            assert len(data['messages']) == 2
            print(f"   ✓ Created individual JSON: {json_files[0].name}")
        
        # Test 2: Single consolidated JSON
        print("\n2. Testing single JSON format...")
        extractor = ConversationExtractorV2(
            input_file=str(input_file),
            output_dir=str(output_dir / "test2"),
            output_format='json',
            json_format='single',
            preserve_timestamps=False
        )
        extractor.extract_all()
        
        # Check output
        json_files = list((output_dir / "test2").glob("conversations_export_*.json"))
        assert len(json_files) == 1, f"Expected 1 consolidated JSON, got {len(json_files)}"
        
        with open(json_files[0]) as f:
            data = json.load(f)
            assert 'export_metadata' in data
            assert data['export_metadata']['total_conversations'] == 1
            assert len(data['conversations']) == 1
            print(f"   ✓ Created consolidated JSON: {json_files[0].name}")
        
        # Test 3: Both markdown and JSON
        print("\n3. Testing both formats...")
        extractor = ConversationExtractorV2(
            input_file=str(input_file),
            output_dir=str(output_dir / "test3"),
            output_format='both',
            json_format='multiple',
            preserve_timestamps=False
        )
        extractor.extract_all()
        
        # Check outputs
        md_files = list((output_dir / "test3" / "md").glob("*.md"))
        json_files = list((output_dir / "test3" / "json").glob("*.json"))
        assert len(md_files) == 1, f"Expected 1 markdown file, got {len(md_files)}"
        assert len(json_files) == 1, f"Expected 1 JSON file, got {len(json_files)}"
        print(f"   ✓ Created both formats: {md_files[0].name} and {json_files[0].name}")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        return True

if __name__ == "__main__":
    try:
        test_json_output()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)