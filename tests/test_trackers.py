"""
Tests for the tracking components.
"""

import time
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chatgpt_extractor.trackers import SchemaEvolutionTracker, ProgressTracker


class TestSchemaEvolutionTracker:
    """Test suite for SchemaEvolutionTracker."""
    
    @pytest.fixture
    def tracker(self):
        """Create a SchemaEvolutionTracker instance."""
        return SchemaEvolutionTracker()
    
    def test_track_known_content_type(self, tracker):
        """Test tracking of known content types."""
        tracker.track_content_type('text', 'conv-1')
        assert 'text' in tracker.content_types
        assert len(tracker.unknown_samples['content_types']) == 0
    
    def test_track_unknown_content_type(self, tracker):
        """Test tracking of unknown content types."""
        tracker.track_content_type('new_type', 'conv-1')
        assert 'new_type' in tracker.content_types
        assert 'conv-1: new_type' in tracker.unknown_samples['content_types']
    
    def test_track_author_roles(self, tracker):
        """Test tracking of author roles."""
        tracker.track_author_role('user', 'conv-1')
        tracker.track_author_role('custom_role', 'conv-2')
        
        assert 'user' in tracker.author_roles
        assert 'custom_role' in tracker.author_roles
        assert 'conv-2: custom_role' in tracker.unknown_samples['author_roles']
    
    def test_track_metadata_keys(self, tracker):
        """Test tracking of metadata keys."""
        metadata = {
            'key1': 'value1',
            'key2': 'value2',
            'nested': {'key3': 'value3'}
        }
        tracker.track_metadata_keys(metadata, 'conv-1')
        
        assert 'key1' in tracker.metadata_keys
        assert 'key2' in tracker.metadata_keys
        assert 'nested' in tracker.metadata_keys
    
    def test_track_part_types(self, tracker):
        """Test tracking of part types."""
        tracker.track_part_type('image_asset_pointer', 'conv-1')
        tracker.track_part_type('unknown_pointer', 'conv-2')
        
        assert 'image_asset_pointer' in tracker.part_types
        assert 'unknown_pointer' in tracker.part_types
        assert 'conv-2: unknown_pointer' in tracker.unknown_samples['part_types']
    
    def test_sample_limit(self, tracker):
        """Test that unknown samples are limited to 10."""
        for i in range(15):
            tracker.track_content_type(f'unknown_{i}', f'conv-{i}')
        
        assert len(tracker.unknown_samples['content_types']) == 10
    
    def test_generate_report(self, tracker):
        """Test report generation."""
        # Add some data
        tracker.track_content_type('text', 'conv-1')
        tracker.track_content_type('unknown_type', 'conv-2')
        tracker.track_author_role('user', 'conv-1')
        tracker.track_recipient('dalle.text2im', 'conv-3')
        tracker.track_finish_type('stop', 'conv-1')
        
        report = tracker.generate_report()
        
        # Check report contains expected sections
        assert 'SCHEMA EVOLUTION TRACKING REPORT' in report
        assert '## Content Types' in report
        assert '## Author Roles' in report
        assert 'Known types found: 1' in report
        assert 'Unknown types found: 1' in report


class TestProgressTracker:
    """Test suite for ProgressTracker."""
    
    def test_initialization(self):
        """Test progress tracker initialization."""
        tracker = ProgressTracker(total=100)
        assert tracker.total == 100
        assert tracker.processed == 0
        assert tracker.failed == 0
    
    def test_update_success(self):
        """Test updating with successful processing."""
        tracker = ProgressTracker(total=10)
        tracker.update(success=True)
        
        assert tracker.processed == 1
        assert tracker.failed == 0
    
    def test_update_failure(self):
        """Test updating with failed processing."""
        tracker = ProgressTracker(total=10)
        tracker.update(success=False)
        
        assert tracker.processed == 1
        assert tracker.failed == 1
    
    def test_final_stats(self):
        """Test final statistics calculation."""
        tracker = ProgressTracker(total=10)
        
        # Simulate some processing
        for i in range(8):
            tracker.update(success=True)
        for i in range(2):
            tracker.update(success=False)
        
        stats = tracker.final_stats()
        
        assert stats['total'] == 10
        assert stats['processed'] == 10
        assert stats['failed'] == 2
        assert stats['success_rate'] == 80.0
        assert 'elapsed_time' in stats
        assert 'rate' in stats
    
    def test_show_progress_output(self, capsys):
        """Test progress display output."""
        tracker = ProgressTracker(total=100)
        
        # Update and show progress
        for i in range(5):
            tracker.update(success=True)
        tracker.show_progress()
        
        captured = capsys.readouterr()
        
        # Check output contains expected elements
        assert 'Progress:' in captured.out
        assert '5/100' in captured.out
        assert 'Failed: 0' in captured.out
        assert 'Rate:' in captured.out
        assert 'ETA:' in captured.out
    
    def test_eta_calculation(self):
        """Test ETA calculation."""
        tracker = ProgressTracker(total=100)
        
        # Simulate some delay
        tracker.start_time = time.time() - 10  # 10 seconds ago
        tracker.processed = 50
        
        tracker.show_progress()
        
        # With 50 processed in 10 seconds, rate is 5/s
        # 50 remaining should take ~10 seconds
        # Just verify the calculation doesn't crash
        assert tracker.processed == 50
    
    def test_milestone_updates(self, capsys):
        """Test that progress updates at milestones."""
        tracker = ProgressTracker(total=1000)
        
        # Process 99 - no output expected
        for i in range(99):
            tracker.update()
        
        # Process 100th - should trigger update
        tracker.update()
        
        captured = capsys.readouterr()
        assert 'Progress:' in captured.out
        assert '100/1000' in captured.out
    
    def test_zero_total_handling(self):
        """Test handling of zero total (edge case)."""
        tracker = ProgressTracker(total=0)
        
        # Should not crash
        tracker.show_progress()
        stats = tracker.final_stats()
        
        assert stats['total'] == 0
        assert stats['success_rate'] == 0