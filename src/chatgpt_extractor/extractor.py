"""
Main extractor class for ChatGPT conversation processing.
"""

import json
import os
import re
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

import yaml

from .processors import MessageProcessor
from .trackers import SchemaEvolutionTracker, ProgressTracker
from .logging_config import get_logger, log_exception


class ConversationExtractorV2:
    """Enhanced ChatGPT conversation extractor with schema tracking."""
    
    def __init__(self, input_file: str, output_dir: str):
        """Initialize the extractor.
        
        Args:
            input_file: Path to conversations.json
            output_dir: Directory for output markdown files
        """
        self.logger = get_logger(__name__)
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            self.logger.critical(f"Permission denied creating output directory {self.output_dir}")
            raise
        except Exception as e:
            log_exception(self.logger, e, f"creating output directory {self.output_dir}")
            raise
        
        # Initialize components
        self.schema_tracker = SchemaEvolutionTracker()
        self.message_processor = MessageProcessor(self.schema_tracker)
        
        # Track failures
        self.conversion_failures = []
    
    def extract_all(self) -> None:
        """Main extraction process for all conversations."""
        self.logger.info(f"ChatGPT Conversation Extractor v2.0")
        self.logger.info(f"{'='*60}")
        
        # Load conversations with exception handling
        try:
            self.logger.info(f"Loading conversations from {self.input_file}")
            with open(self.input_file, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
        except FileNotFoundError:
            self.logger.critical(f"Input file not found: {self.input_file}")
            raise
        except json.JSONDecodeError as e:
            self.logger.critical(f"Invalid JSON in {self.input_file}: Line {e.lineno}, Column {e.colno}")
            self.logger.debug(f"JSON error details: {e.msg}")
            raise
        except PermissionError as e:
            self.logger.critical(f"Permission denied reading {self.input_file}")
            raise
        except Exception as e:
            log_exception(self.logger, e, "loading conversations")
            raise
        
        self.logger.info(f"Found {len(conversations)} conversations to process")
        self.logger.info(f"Output directory: {self.output_dir}")
        
        # Initialize progress tracking
        progress = ProgressTracker(total=len(conversations))
        
        # Process each conversation
        for conv in conversations:
            try:
                self.process_conversation(conv)
                progress.update(success=True)
            except Exception as e:
                conv_id = conv.get('id', conv.get('conversation_id', 'unknown'))
                title = conv.get('title', 'Untitled')[:50]
                self.log_conversion_failure(conv, conv_id, title, e)
                progress.update(success=False)
        
        # Clear progress line for clean output
        if not self.logger.handlers:
            print()  # Only print if no logging handlers
        
        # Save tracking reports
        self.save_schema_report()
        if self.conversion_failures:
            self.save_conversion_log()
        
        # Print summary
        self.print_summary(progress)
    
    def process_conversation(self, conv: Dict[str, Any]) -> None:
        """Process single conversation to markdown."""
        # Handle None or invalid input
        if not conv:
            self.logger.warning("Skipping None or empty conversation")
            return
            
        # Extract metadata
        metadata = self.extract_metadata(conv)
        conv_id = metadata['id']
        
        # Get conversation graph
        mapping = conv.get('mapping', {})
        current_node = conv.get('current_node')
        
        # Traverse conversation
        messages = self.backward_traverse(mapping, current_node, conv_id)
        
        # Process messages
        processed = self.process_messages(messages, conv_id, conv)
        
        # Merge continuations
        merged = self.merge_continuations(processed)
        
        if merged:
            # Generate markdown
            content = self.generate_markdown(metadata, merged)
            
            # Save to file
            self.save_to_file(metadata, content)
    
    def extract_metadata(self, conv: Dict[str, Any]) -> Dict[str, Any]:
        """Extract conversation metadata for YAML frontmatter.
        
        Args:
            conv: Conversation dictionary from JSON export
            
        Returns:
            Metadata dict with id, title, timestamps, model, URLs
        """
        metadata = {}
        
        # IDs
        metadata['id'] = conv.get('id', conv.get('conversation_id', 'unknown'))
        
        # Title
        metadata['title'] = conv.get('title', 'Untitled Conversation')
        
        # Timestamps
        if create_time := conv.get('create_time'):
            metadata['created'] = datetime.fromtimestamp(create_time).isoformat() + 'Z'
        if update_time := conv.get('update_time'):
            metadata['updated'] = datetime.fromtimestamp(update_time).isoformat() + 'Z'
        
        # Model
        if model := conv.get('default_model_slug'):
            metadata['model'] = model
        
        # Conversation metadata
        if is_starred := conv.get('is_starred'):
            metadata['starred'] = is_starred
        if is_archived := conv.get('is_archived'):
            metadata['archived'] = is_archived
        
        # URL
        metadata['chat_url'] = f"https://chatgpt.com/c/{metadata['id']}"
        
        # Project info
        if project_id := conv.get('conversation_template_id'):
            if project_id.startswith('g-p-'):
                metadata['project_id'] = project_id
        
        return metadata
    
    def backward_traverse(self, mapping: Dict[str, Any], current_node: Optional[str], 
                         conv_id: str) -> List[Dict[str, Any]]:
        """Traverse conversation graph backwards from current node to root.
        
        Args:
            mapping: Node ID to node object mapping from conversation
            current_node: Starting node ID (may be None)
            conv_id: Conversation ID for error tracking
            
        Returns:
            List of messages in chronological order (root to current)
            
        Note:
            O(n) complexity vs O(n² for forward traversal with branches.
            Automatically excludes edited/regenerated branches.
        """
        if not mapping:
            return []
        
        # Fallback strategy: Find highest-weight leaf if current_node missing
        if not current_node or current_node not in mapping:
            leaves = []
            for node_id, node in mapping.items():
                if not node.get('children'):
                    if node.get('message'):
                        leaves.append(node)
            
            if not leaves:
                return []
            
            # Sort by weight and update_time
            current_node = max(
                leaves,
                key=lambda n: (
                    n.get('message', {}).get('weight', 0),
                    n.get('message', {}).get('update_time', 0)
                )
            ).get('id')
        
        # Backward traversal: O(n) complexity, auto-excludes branches
        messages = []
        node_id = current_node
        visited = set()  # Prevent infinite loops in malformed graphs
        
        while node_id and node_id not in visited:
            visited.add(node_id)
            node = mapping.get(node_id)
            
            if not node:
                break
            
            if msg := node.get('message'):
                # Track metadata
                if metadata := msg.get('metadata'):
                    self.schema_tracker.track_metadata_keys(metadata, conv_id)
                
                # Track author role
                if author := msg.get('author'):
                    if role := author.get('role'):
                        self.schema_tracker.track_author_role(role, conv_id)
                    if recipient := author.get('recipient'):
                        self.schema_tracker.track_recipient(recipient, conv_id)
                
                # Track finish details
                if finish_details := msg.get('finish_details'):
                    if finish_details.get('type'):
                        self.schema_tracker.track_finish_type(finish_details['type'], conv_id)
                
                messages.append(msg)
            
            node_id = node.get('parent') if node else None
        
        # Reverse to get chronological order
        return list(reversed(messages))
    
    def process_messages(self, messages: List[Dict[str, Any]], conv_id: str, 
                        conv_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter and process messages for markdown output.
        
        Args:
            messages: Raw messages from backward traversal
            conv_id: Conversation ID for tracking
            conv_data: Full conversation data for URL extraction
            
        Returns:
            Processed messages with content, role, and metadata
        """
        processed = []
        system_prompt_added = False
        
        for msg in messages:
            # Skip if should be filtered
            if self.message_processor.should_filter_message(msg):
                continue
            
            author_role = msg.get('author', {}).get('role')
            
            # Handle system messages
            if author_role == 'system':
                if not system_prompt_added and self.message_processor.is_user_system_message(msg):
                    content = self.message_processor.extract_message_content(msg, conv_id)
                    if content:
                        processed.append({
                            'role': 'system',
                            'content': content
                        })
                        system_prompt_added = True
                continue
            
            # Process user/assistant messages
            if author_role in ['user', 'assistant']:
                content = self.message_processor.extract_message_content(msg, conv_id)
                if content:  # Only add if has content after filtering
                    msg_data = {
                        'role': author_role,
                        'content': content
                    }
                    
                    # Extract additional data
                    citations = self.message_processor.extract_citations(msg)
                    if citations:
                        msg_data['citations'] = citations
                    
                    web_urls = self.message_processor.extract_web_urls(msg, conv_data)
                    if web_urls:
                        msg_data['web_urls'] = web_urls
                    
                    files = self.message_processor.extract_file_names(msg)
                    if files:
                        msg_data['files'] = files
                    
                    # Preserve graph index for proper message continuation merging
                    if '_graph_index' in msg:
                        msg_data['_graph_index'] = msg['_graph_index']
                    
                    processed.append(msg_data)
            
            # Handle tool messages with DALL-E content
            elif author_role == 'tool':
                # Check for DALL-E images
                content = msg.get('content', {})
                if self.message_processor._contains_dalle_image(content):
                    extracted = self.message_processor.extract_message_content(msg, conv_id)
                    if extracted:
                        processed.append({
                            'role': 'assistant',
                            'content': extracted
                        })
        
        return processed
    
    def merge_continuations(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge consecutive assistant messages that are continuations.
        
        Validates messages are truly consecutive using graph indices when available.
        """
        if not messages:
            return messages
        
        merged = []
        i = 0
        
        while i < len(messages):
            current = messages[i]
            
            # For non-assistant messages, just add and continue
            if current['role'] != 'assistant':
                merged.append(current)
                i += 1
                continue
            
            # Check if next message should be merged
            if (i + 1 < len(messages) and 
                current['role'] == 'assistant' and 
                messages[i + 1]['role'] == 'assistant'):
                
                # Merge content
                combined_content = current['content']
                
                # Collect all consecutive assistant messages (validates true adjacency)
                j = i + 1
                while j < len(messages) and messages[j]['role'] == 'assistant':
                    combined_content += '\n\n' + messages[j]['content']
                    
                    # Merge citations and URLs
                    if 'citations' in messages[j]:
                        if 'citations' not in current:
                            current['citations'] = []
                        current['citations'].extend(messages[j]['citations'])
                    
                    if 'web_urls' in messages[j]:
                        if 'web_urls' not in current:
                            current['web_urls'] = []
                        current['web_urls'].extend(messages[j]['web_urls'])
                    
                    j += 1
                
                # Create merged message
                merged_msg = {
                    'role': 'assistant',
                    'content': combined_content
                }
                
                # Add merged citations and URLs
                if 'citations' in current:
                    merged_msg['citations'] = current['citations']
                if 'web_urls' in current:
                    # Deduplicate URLs
                    merged_msg['web_urls'] = sorted(list(set(current['web_urls'])))
                
                merged.append(merged_msg)
                i = j
            else:
                merged.append(current)
                i += 1
        
        return merged
    
    def generate_markdown(self, metadata: Dict[str, Any], messages: List[Dict[str, Any]]) -> str:
        """Generate markdown content with YAML frontmatter for conversation."""
        lines = []
        
        # YAML frontmatter
        lines.append('---')
        for key, value in metadata.items():
            if isinstance(value, str) and (':' in value or '"' in value):
                # Quote strings that contain special characters
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f'{key}: {value}')
        lines.append('---')
        lines.append('')
        
        # Title
        lines.append(f"# {metadata['title']}")
        lines.append('')
        
        # Messages
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # Format role header
            if role == 'system':
                lines.append('## System')
            elif role == 'user':
                lines.append('## User')
            elif role == 'assistant':
                lines.append('## Assistant')
            else:
                lines.append(f'## {role.title()}')
            
            # Add file indicators for user messages
            if role == 'user' and 'files' in msg:
                for file in msg['files']:
                    lines.append(f'[File: {file}]')
            
            # Add content
            lines.append(content)
            
            # Add citations
            if 'citations' in msg:
                lines.append('')
                lines.append('**Citations:**')
                for citation in msg['citations']:
                    title = citation.get('title', 'Untitled')
                    url = citation.get('url', '')
                    type_ = citation.get('type', 'webpage')
                    
                    if url:
                        lines.append(f'- [{type_}] {title} - {url}')
                    else:
                        lines.append(f'- [{type_}] {title}')
            
            # Add web URLs
            if 'web_urls' in msg and msg['web_urls']:
                lines.append('')
                lines.append('**Web Search URLs:**')
                for url in msg['web_urls']:
                    lines.append(f'- {url}')
            
            lines.append('')
        
        return '\n'.join(lines)
    
    def save_to_file(self, metadata: Dict[str, Any], content: str) -> None:
        """Save markdown content to file with proper directory structure."""
        # Generate filename
        title = metadata['title']
        safe_title = self.sanitize_filename(title)
        
        # Check for project directory
        if project_id := metadata.get('project_id'):
            # Create project directory
            project_dir = self.output_dir / project_id
            try:
                project_dir.mkdir(exist_ok=True)
            except PermissionError:
                self.logger.error(f"Permission denied creating project directory {project_dir}")
                raise
            except Exception as e:
                log_exception(self.logger, e, f"creating project directory {project_dir}")
                raise
            file_path = project_dir / f"{safe_title}.md"
        else:
            file_path = self.output_dir / f"{safe_title}.md"
        
        # Handle duplicates
        if file_path.exists():
            # Add number suffix
            counter = 2
            while True:
                if metadata.get('project_id'):
                    new_path = file_path.parent / f"{safe_title} ({counter}).md"
                else:
                    new_path = self.output_dir / f"{safe_title} ({counter}).md"
                
                if not new_path.exists():
                    file_path = new_path
                    break
                counter += 1
        
        # Write file with exception handling
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.debug(f"Successfully wrote {file_path}")
        except PermissionError:
            self.logger.error(f"Permission denied writing to {file_path}")
            raise
        except IOError as e:
            self.logger.error(f"I/O error writing to {file_path}: {e}")
            raise
        except Exception as e:
            log_exception(self.logger, e, f"writing to {file_path}")
            raise
    
    def sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """Convert title to safe filename."""
        # Remove or replace invalid characters
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        
        # Remove control characters
        safe_title = ''.join(char for char in safe_title if ord(char) >= 32)
        
        # Truncate if too long
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rstrip()
        
        # Remove trailing dots and spaces (Windows compatibility)
        safe_title = safe_title.rstrip('. ')
        
        # Default if empty
        if not safe_title:
            safe_title = 'untitled'
        
        return safe_title
    
    def print_summary(self, progress: ProgressTracker) -> None:
        """Print extraction summary."""
        stats = progress.final_stats()
        
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("EXTRACTION COMPLETE!")
        self.logger.info("="*60)
        self.logger.info(f"  Total conversations: {stats['total']}")
        self.logger.info(f"  Successfully processed: {stats['processed'] - stats['failed']}")
        self.logger.info(f"  Failed: {stats['failed']}")
        self.logger.info(f"  Success rate: {stats['success_rate']:.1f}%")
        self.logger.info(f"  Time elapsed: {stats['elapsed_time']:.1f}s")
        self.logger.info(f"  Processing rate: {stats['rate']:.1f} conv/s")
        self.logger.info(f"  Output directory: {self.output_dir}")
        self.logger.info("="*60)
    
    def save_schema_report(self) -> None:
        """Save schema evolution tracking report."""
        report_path = self.output_dir / 'schema_evolution.log'
        report = self.schema_tracker.generate_report()
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.debug(f"Schema report saved to {report_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save schema report: {e}")
            # Non-critical, so we don't raise
    
    def log_conversion_failure(self, conv: Dict[str, Any], conv_id: str, title: str, 
                               error: Exception) -> None:
        """Log detailed information about conversion failure for analysis."""
        import traceback
        
        # Categorize error
        error_str = str(error)
        error_type = type(error).__name__
        
        if 'NoneType' in error_str:
            category = 'NoneType_error'
        elif error_type == 'KeyError':
            category = 'KeyError'
        elif 'list index out of range' in error_str:
            category = 'IndexError'
        elif 'expected string or bytes-like object' in error_str:
            category = 'TypeError_regex'
        else:
            category = 'Other'
        
        # Analyze conversation structure
        mapping = conv.get('mapping', {})
        structural_issues = []
        
        # Check for None content
        none_content_count = 0
        none_parts_count = 0
        empty_parts_count = 0
        problematic_nodes = []
        
        for node_id, node in mapping.items():
            if msg := node.get('message'):
                content = msg.get('content')
                author = msg.get('author', {})
                
                if content is None:
                    none_content_count += 1
                    problematic_nodes.append({
                        'node_id': node_id[:8],
                        'role': author.get('role'),
                        'issue': 'None content'
                    })
                elif content:
                    if content.get('parts') is None:
                        none_parts_count += 1
                        problematic_nodes.append({
                            'node_id': node_id[:8],
                            'role': author.get('role'),
                            'content_type': content.get('content_type'),
                            'issue': 'None parts'
                        })
                    elif content.get('parts') == []:
                        empty_parts_count += 1
        
        if none_content_count > 0:
            structural_issues.append(f"None content in {none_content_count} messages")
        if none_parts_count > 0:
            structural_issues.append(f"None parts in {none_parts_count} messages")
        if empty_parts_count > 0:
            structural_issues.append(f"Empty parts in {empty_parts_count} messages")
        
        # Check current_node
        if not conv.get('current_node'):
            structural_issues.append("Missing current_node")
        elif conv.get('current_node') not in mapping:
            structural_issues.append("Invalid current_node")
        
        # Get first line of traceback
        tb_lines = traceback.format_exc().split('\n')
        trace_snippet = None
        for line in reversed(tb_lines):
            if 'File' in line and '.py' in line:
                trace_snippet = line.strip()
                break
        
        # Create failure record
        failure_record = {
            'conversation_id': conv_id,
            'title': title,
            'error_message': error_str[:500],  # Truncate long errors
            'error_type': error_type,
            'category': category,
            'structural_issues': structural_issues,
            'message_count': len([n for n in mapping.values() if n.get('message')]),
            'metadata': {
                'has_current_node': bool(conv.get('current_node')),
                'has_mapping': bool(mapping),
                'project_id': conv.get('conversation_template_id'),
            },
            'problematic_nodes': problematic_nodes[:5],  # Sample
            'trace_snippet': trace_snippet
        }
        
        self.conversion_failures.append(failure_record)
    
    def save_conversion_log(self) -> None:
        """Save detailed conversion failure log to file."""
        if not self.conversion_failures:
            return
        
        log_path = self.output_dir / 'conversion_log.log'
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                # Write header
                f.write("="*80 + "\n")
                f.write("CONVERSATION EXTRACTION FAILURE LOG\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Total Failures: {len(self.conversion_failures)}\n")
                f.write("="*80 + "\n\n")
            
                # Summary by category
                categories = defaultdict(int)
                for fail in self.conversion_failures:
                    categories[fail['category']] += 1
                
                f.write("FAILURE CATEGORIES:\n")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {cat}: {count}\n")
                f.write("\n")
            
                # Failed conversation IDs
                f.write("FAILED CONVERSATION IDs:\n")
                for fail in self.conversion_failures:
                    f.write(f"  - {fail['conversation_id']}\n")
                f.write("\n")
            
                # Detailed failures
                f.write("="*80 + "\n")
                f.write("DETAILED FAILURE INFORMATION\n")
                f.write("="*80 + "\n\n")
                
                for i, fail in enumerate(self.conversion_failures, 1):
                    f.write(f"Failure #{i}\n")
                    f.write(f"ID: {fail['conversation_id']}\n")
                    f.write(f"Title: {fail['title']}\n")
                    f.write(f"Category: {fail['category']}\n")
                    f.write(f"Error Type: {fail['error_type']}\n")
                    f.write(f"Error: {fail['error_message']}\n")
                    
                    # Structural issues
                    if fail['structural_issues']:
                        f.write(f"Structural Issues: {', '.join(fail['structural_issues'])}\n")
                    
                    # Problematic nodes
                    if fail['problematic_nodes']:
                        f.write(f"\nProblematic Nodes (sample):\n")
                        for node in fail['problematic_nodes'][:3]:
                            f.write(f"  - Node {node['node_id']}: role={node.get('role')}, ")
                            f.write(f"content_type={node.get('content_type')}, issue={node.get('issue')}\n")
                    
                    # Trace
                    if fail['trace_snippet']:
                        f.write(f"\nTrace: {fail['trace_snippet']}\n")
                    
                    f.write("\n" + "="*80 + "\n\n")
            
                # Write JSON version for programmatic access
                json_path = self.output_dir / 'conversion_failures.json'
                try:
                    with open(json_path, 'w', encoding='utf-8') as jf:
                        json.dump(self.conversion_failures, jf, indent=2, default=str)
                    f.write(f"\nJSON version saved to: conversion_failures.json\n")
                except Exception as e:
                    self.logger.warning(f"Failed to save JSON failure log: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to save conversion log: {e}")
            # Non-critical, so we don't raise