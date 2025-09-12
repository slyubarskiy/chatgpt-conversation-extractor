"""
Tracking components for schema evolution and progress monitoring.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any
from collections import defaultdict
from datetime import datetime


@dataclass
class SchemaEvolutionTracker:
    """Track unknown patterns and schema changes."""
    content_types: Set[str] = field(default_factory=set)
    author_roles: Set[str] = field(default_factory=set)
    recipient_values: Set[str] = field(default_factory=set)
    metadata_keys: Set[str] = field(default_factory=set)
    part_types: Set[str] = field(default_factory=set)
    finish_types: Set[str] = field(default_factory=set)
    unknown_samples: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    
    # Known patterns for comparison
    KNOWN_CONTENT_TYPES = {
        'text', 'code', 'multimodal_text', 'execution_output', 
        'tether_quote', 'tether_browsing_display', 'user_editable_context',
        'model_editable_context', 'thoughts', 'reasoning_recap', 'sonic_webpage',
        'system_error'
    }
    
    KNOWN_ROLES = {'system', 'user', 'assistant', 'tool'}
    
    KNOWN_PART_TYPES = {
        'image_asset_pointer', 'audio_transcription', 'audio_asset_pointer',
        'video_asset_pointer', 'code_interpreter_output'
    }
    
    def track_content_type(self, content_type: str, conv_id: str) -> None:
        """Track content types and log unknowns."""
        self.content_types.add(content_type)
        if content_type and content_type not in self.KNOWN_CONTENT_TYPES:
            if len(self.unknown_samples['content_types']) < 10:
                self.unknown_samples['content_types'].append(f"{conv_id}: {content_type}")
    
    def track_author_role(self, role: str, conv_id: str) -> None:
        """Track author roles."""
        self.author_roles.add(role)
        if role and role not in self.KNOWN_ROLES:
            if len(self.unknown_samples['author_roles']) < 10:
                self.unknown_samples['author_roles'].append(f"{conv_id}: {role}")
    
    def track_recipient(self, recipient: str, conv_id: str) -> None:
        """Track recipient values (tools)."""
        if recipient:
            self.recipient_values.add(recipient)
    
    def track_metadata_keys(self, metadata: Dict[str, Any], conv_id: str) -> None:
        """Track metadata field names."""
        if metadata:
            for key in metadata.keys():
                self.metadata_keys.add(key)
    
    def track_part_type(self, part_type: str, conv_id: str) -> None:
        """Track part types in multimodal content."""
        self.part_types.add(part_type)
        if part_type and part_type not in self.KNOWN_PART_TYPES:
            if len(self.unknown_samples['part_types']) < 10:
                self.unknown_samples['part_types'].append(f"{conv_id}: {part_type}")
    
    def track_finish_type(self, finish_type: str, conv_id: str) -> None:
        """Track finish_details types."""
        if finish_type:
            self.finish_types.add(finish_type)
    
    def generate_report(self) -> str:
        """Generate evolution tracking report."""
        report = []
        report.append("="*60)
        report.append("SCHEMA EVOLUTION TRACKING REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("="*60)
        report.append("")
        
        # Content Types
        report.append("## Content Types")
        known = self.content_types & self.KNOWN_CONTENT_TYPES
        unknown = self.content_types - self.KNOWN_CONTENT_TYPES
        report.append(f"  Known types found: {len(known)}")
        report.append(f"  Unknown types found: {len(unknown)}")
        if unknown:
            report.append("  Unknown types:")
            for ct in sorted(unknown):
                report.append(f"    - {ct}")
            if self.unknown_samples['content_types']:
                report.append("  Sample conversations:")
                for sample in self.unknown_samples['content_types'][:3]:
                    report.append(f"    {sample}")
        report.append("")
        
        # Author Roles
        report.append("## Author Roles")
        known = self.author_roles & self.KNOWN_ROLES
        unknown = self.author_roles - self.KNOWN_ROLES
        report.append(f"  Known roles found: {len(known)}")
        report.append(f"  Unknown roles found: {len(unknown)}")
        if unknown:
            report.append("  Unknown roles:")
            for role in sorted(unknown):
                report.append(f"    - {role}")
            if self.unknown_samples['author_roles']:
                report.append("  Sample conversations:")
                for sample in self.unknown_samples['author_roles'][:3]:
                    report.append(f"    {sample}")
        report.append("")
        
        # Part Types
        report.append("## Part Types in Multimodal Content")
        known = self.part_types & self.KNOWN_PART_TYPES
        unknown = self.part_types - self.KNOWN_PART_TYPES
        report.append(f"  Known part types: {len(known)}")
        report.append(f"  Unknown part types: {len(unknown)}")
        if unknown:
            report.append("  Unknown part types:")
            for pt in sorted(unknown):
                report.append(f"    - {pt}")
            if self.unknown_samples['part_types']:
                report.append("  Sample conversations:")
                for sample in self.unknown_samples['part_types'][:3]:
                    report.append(f"    {sample}")
        report.append("")
        
        # Recipients
        if self.recipient_values:
            report.append("## Recipients (Tools)")
            report.append(f"  Unique recipients found: {len(self.recipient_values)}")
            for recipient in sorted(self.recipient_values)[:10]:
                report.append(f"    - {recipient}")
            report.append("")
        
        # Finish Types
        if self.finish_types:
            report.append("## Finish Types")
            report.append(f"  Unique finish types found: {len(self.finish_types)}")
            for ft in sorted(self.finish_types):
                report.append(f"    - {ft}")
            report.append("")
        
        # Metadata Keys
        if self.metadata_keys:
            report.append("## Metadata Keys")
            report.append(f"  Total unique keys: {len(self.metadata_keys)}")
            report.append("")
        
        return '\n'.join(report)


@dataclass
class ProgressTracker:
    """Enhanced progress tracking with ETA."""
    total: int
    processed: int = 0
    failed: int = 0
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    
    def update(self, success: bool = True) -> None:
        """Update progress counters."""
        self.processed += 1
        if not success:
            self.failed += 1
        
        # Show progress every 100 items or at milestones
        current_time = time.time()
        if (self.processed % 100 == 0 or 
            self.processed == self.total or
            current_time - self.last_update > 5):  # Also update every 5 seconds
            
            self.show_progress()
            self.last_update = current_time
    
    def show_progress(self) -> None:
        """Display progress with ETA."""
        elapsed = time.time() - self.start_time
        
        if elapsed > 0:
            rate = self.processed / elapsed
            remaining = self.total - self.processed
            eta = remaining / rate if rate > 0 else 0
        else:
            rate = 0
            eta = 0
        
        percent = (self.processed / self.total * 100) if self.total > 0 else 0
        
        # Format ETA
        if eta < 60:
            eta_str = f"{eta:.0f}s"
        else:
            eta_str = f"{eta/60:.1f}m"
        
        # Clear line and print progress
        print(f"\r  Progress: {self.processed}/{self.total} ({percent:.1f}%) | "
              f"Failed: {self.failed} | Rate: {rate:.1f}/s | ETA: {eta_str}", 
              end='', flush=True)
    
    def final_stats(self) -> Dict[str, Any]:
        """Return final statistics."""
        elapsed = time.time() - self.start_time
        success_rate = ((self.processed - self.failed) / self.processed * 100) if self.processed > 0 else 0
        
        return {
            'total': self.total,
            'processed': self.processed,
            'failed': self.failed,
            'success_rate': success_rate,
            'elapsed_time': elapsed,
            'rate': self.processed / elapsed if elapsed > 0 else 0
        }