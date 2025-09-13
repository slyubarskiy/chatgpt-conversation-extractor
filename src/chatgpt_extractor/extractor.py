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
        
        self.schema_tracker = SchemaEvolutionTracker()
        self.message_processor = MessageProcessor(self.schema_tracker)
        
        self.conversion_failures: List[Dict[str, Any]] = []
    
    def extract_all(self) -> None:
        """Main extraction process for all conversations."""
        self.logger.info(f"ChatGPT Conversation Extractor v2.0")
        self.logger.info(f"{'='*60}")
        
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
        
        progress = ProgressTracker(total=len(conversations))
        
        for conv in conversations:
            try:
                self.process_conversation(conv)
                progress.update(success=True)
            except Exception as e:
                conv_id = conv.get('id', conv.get('conversation_id', 'unknown'))
                title = conv.get('title', 'Untitled')[:50]
                self.log_conversion_failure(conv, conv_id, title, e)
                progress.update(success=False)
        
        if not self.logger.handlers:
            print()  # Only print if no logging handlers
        
        self.save_schema_report()
        if self.conversion_failures:
            self.save_conversion_log()
        
        self.print_summary(progress)
    
    def process_conversation(self, conv: Dict[str, Any]) -> None:
        """Process single conversation to markdown."""
        if not conv:
            self.logger.warning("Skipping None or empty conversation")
            return
            
        metadata = self.extract_metadata(conv)
        conv_id = metadata['id']
        
        mapping = conv.get('mapping', {})
        current_node = conv.get('current_node')
        
        messages = self.backward_traverse(mapping, current_node, conv_id)
        
        # Collect statistics from raw messages
        stats = self.collect_message_statistics(messages, conv_id)
        
        processed = self.process_messages(messages, conv_id, conv)
        
        merged = self.merge_continuations(processed)
        
        if merged:
            # Add statistics to metadata
            metadata['total_messages'] = len(merged)
            metadata['code_messages'] = stats['code_count']
            if stats['content_types']:
                metadata['message_types'] = ', '.join(sorted(stats['content_types']))
            if stats['custom_instructions']:
                metadata['custom_instructions'] = stats['custom_instructions']
            
            content = self.generate_markdown(metadata, merged)
            
            self.save_to_file(metadata, content)
    
    def extract_metadata(self, conv: Dict[str, Any]) -> Dict[str, Any]:
        """Extract conversation metadata for YAML frontmatter.
        
        Args:
            conv: Conversation dictionary from JSON export
            
        Returns:
            Metadata dict with id, title, timestamps, model, URLs
        """
        metadata = {}
        
        metadata['id'] = conv.get('id', conv.get('conversation_id', 'unknown'))
        
        metadata['title'] = conv.get('title', 'Untitled Conversation')
        
        if create_time := conv.get('create_time'):
            metadata['created'] = datetime.fromtimestamp(create_time).isoformat() + 'Z'
        if update_time := conv.get('update_time'):
            metadata['updated'] = datetime.fromtimestamp(update_time).isoformat() + 'Z'
        
        if model := conv.get('default_model_slug'):
            metadata['model'] = model
        
        if is_starred := conv.get('is_starred'):
            metadata['starred'] = is_starred
        if is_archived := conv.get('is_archived'):
            metadata['archived'] = is_archived
        
        metadata['chat_url'] = f"https://chatgpt.com/c/{metadata['id']}"
        
        if project_id := conv.get('conversation_template_id'):
            if project_id.startswith('g-p-'):
                metadata['project_id'] = project_id
        
        return metadata
    
    def collect_message_statistics(self, messages: List[Dict[str, Any]], conv_id: str) -> Dict[str, Any]:
        """Collect statistics from raw messages.
        
        Args:
            messages: Raw messages from backward traversal
            conv_id: Conversation ID for tracking
            
        Returns:
            Dictionary with message statistics
        """
        stats = {
            'code_count': 0,
            'content_types': set(),
            'custom_instructions': None
        }
        
        for msg in messages:
            # Track content types
            content = msg.get('content', {})
            content_type = content.get('content_type', '')
            if content_type:
                stats['content_types'].add(content_type)
            
            # Count code messages
            if content_type == 'code':
                stats['code_count'] += 1
            elif content_type == 'execution_output':
                stats['code_count'] += 1
            elif content_type == 'multimodal_text':
                # Check for code interpreter output in parts
                for part in content.get('parts', []):
                    if isinstance(part, dict) and part.get('content_type') == 'code_interpreter_output':
                        stats['code_count'] += 1
                        break
            
            # Extract custom instructions
            if content_type == 'user_editable_context' and not stats['custom_instructions']:
                # This is the custom instructions message
                text = content.get('text', '')
                if text:
                    # Parse the custom instructions format
                    about_user = None
                    about_model = None
                    
                    # Look for the two sections
                    if 'The user provided the following information about themselves:' in text:
                        parts = text.split('The user provided the additional info about how they would like you to respond:')
                        if len(parts) == 2:
                            about_user = parts[0].replace('The user provided the following information about themselves:', '').strip()
                            about_model = parts[1].strip()
                        else:
                            # Try alternative format
                            about_user = text.replace('The user provided the following information about themselves:', '').strip()
                    
                    if about_user or about_model:
                        instructions = {}
                        if about_user:
                            instructions['about_user_message'] = about_user
                        if about_model:
                            instructions['about_model_message'] = about_model
                        stats['custom_instructions'] = instructions
        
        return stats
    
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
            
            # Prioritize by weight, then update_time for deterministic selection
            current_node = max(
                leaves,
                key=lambda n: (
                    n.get('message', {}).get('weight', 0),
                    n.get('message', {}).get('update_time', 0)
                )
            ).get('id')
        
        # O(n) backward traversal automatically excludes edited branches
        messages = []
        node_id = current_node
        visited = set()  # Prevent infinite loops in malformed graphs
        
        while node_id and node_id not in visited:
            visited.add(node_id)
            node = mapping.get(node_id)
            
            if not node:
                break
            
            if msg := node.get('message'):
                if metadata := msg.get('metadata'):
                    self.schema_tracker.track_metadata_keys(metadata, conv_id)
                
                if author := msg.get('author'):
                    if role := author.get('role'):
                        self.schema_tracker.track_author_role(role, conv_id)
                    if recipient := author.get('recipient'):
                        self.schema_tracker.track_recipient(recipient, conv_id)
                
                if finish_details := msg.get('finish_details'):
                    if finish_details.get('type'):
                        self.schema_tracker.track_finish_type(finish_details['type'], conv_id)
                
                messages.append(msg)
            
            node_id = node.get('parent') if node else None
        
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
            if self.message_processor.should_filter_message(msg):
                continue
            
            author_role = msg.get('author', {}).get('role')
            
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
            
            if author_role in ['user', 'assistant']:
                content = self.message_processor.extract_message_content(msg, conv_id)
                if content:  # Only add if has content after filtering
                    msg_data = {
                        'role': author_role,
                        'content': content
                    }
                    
                    citations = self.message_processor.extract_citations(msg)
                    if citations:
                        msg_data['citations'] = citations
                    
                    web_urls = self.message_processor.extract_web_urls(msg, conv_data)
                    if web_urls:
                        msg_data['web_urls'] = web_urls
                    
                    files = self.message_processor.extract_file_names(msg)
                    if files:
                        msg_data['files'] = files
                    
                    # Graph index needed for validating true adjacency in merging
                    if '_graph_index' in msg:
                        msg_data['_graph_index'] = msg['_graph_index']
                    
                    processed.append(msg_data)
            
            # Tool messages included only if they contain DALL-E images
            elif author_role == 'tool':
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
            
            if current['role'] != 'assistant':
                merged.append(current)
                i += 1
                continue
            
            if (i + 1 < len(messages) and 
                current['role'] == 'assistant' and 
                messages[i + 1]['role'] == 'assistant'):
                
                combined_content = current['content']
                
                # Collect all consecutive assistant messages
                j = i + 1
                while j < len(messages) and messages[j]['role'] == 'assistant':
                    combined_content += '\n\n' + messages[j]['content']
                    
                    if 'citations' in messages[j]:
                        if 'citations' not in current:
                            current['citations'] = []
                        current['citations'].extend(messages[j]['citations'])
                    
                    if 'web_urls' in messages[j]:
                        if 'web_urls' not in current:
                            current['web_urls'] = []
                        current['web_urls'].extend(messages[j]['web_urls'])
                    
                    j += 1
                
                merged_msg = {
                    'role': 'assistant',
                    'content': combined_content
                }
                
                if 'citations' in current:
                    merged_msg['citations'] = current['citations']
                if 'web_urls' in current:
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
        
        lines.append('---')
        for key, value in metadata.items():
            if key == 'custom_instructions' and isinstance(value, dict):
                # Format custom instructions as a YAML block string
                lines.append('custom_instructions: |')
                for inst_key, inst_value in value.items():
                    # Escape the value properly for YAML
                    escaped_value = inst_value.replace('\\', '\\\\').replace('"', '\\"')
                    lines.append(f'  {inst_key}: "{escaped_value}"')
            elif isinstance(value, str) and (':' in value or '"' in value):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f'{key}: {value}')
        lines.append('---')
        lines.append('')
        
        lines.append(f"# {metadata['title']}")
        lines.append('')
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            if role == 'system':
                lines.append('## System')
            elif role == 'user':
                lines.append('## User')
            elif role == 'assistant':
                lines.append('## Assistant')
            else:
                lines.append(f'## {role.title()}')
            
            if role == 'user' and 'files' in msg:
                for file in msg['files']:
                    lines.append(f'[File: {file}]')
            
            lines.append(content)
            
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
            
            if 'web_urls' in msg and msg['web_urls']:
                lines.append('')
                lines.append('**Web Search URLs:**')
                for url in msg['web_urls']:
                    lines.append(f'- {url}')
            
            lines.append('')
        
        return '\n'.join(lines)
    
    def save_to_file(self, metadata: Dict[str, Any], content: str) -> None:
        """Save markdown content to file with proper directory structure."""
        title = metadata['title']
        safe_title = self.sanitize_filename(title)
        
        if project_id := metadata.get('project_id'):
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
        
        # Handle filename collisions with numeric suffix
        if file_path.exists():
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
        # Windows/Unix forbidden characters: <>:"/\|?*
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        
        # ASCII control characters (0-31) break filesystem operations
        safe_title = ''.join(char for char in safe_title if ord(char) >= 32)
        
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rstrip()
        
        # Windows silently strips trailing dots/spaces, causing mismatches
        safe_title = safe_title.rstrip('. ')
        
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
    
    def log_conversion_failure(self, conv: Dict[str, Any], conv_id: str, title: str, 
                               error: Exception) -> None:
        """Log detailed information about conversion failure for analysis."""
        import traceback
        
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
        
        mapping = conv.get('mapping', {})
        structural_issues = []
        
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
        
        if not conv.get('current_node'):
            structural_issues.append("Missing current_node")
        elif conv.get('current_node') not in mapping:
            structural_issues.append("Invalid current_node")
        
        # Extract most relevant traceback line for debugging
        tb_lines = traceback.format_exc().split('\n')
        trace_snippet = None
        for line in reversed(tb_lines):
            if 'File' in line and '.py' in line:
                trace_snippet = line.strip()
                break
        
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
                f.write("="*80 + "\n")
                f.write("CONVERSATION EXTRACTION FAILURE LOG\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Total Failures: {len(self.conversion_failures)}\n")
                f.write("="*80 + "\n\n")
            
                categories: Dict[str, int] = defaultdict(int)
                for fail in self.conversion_failures:
                    categories[fail['category']] += 1
                
                f.write("FAILURE CATEGORIES:\n")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {cat}: {count}\n")
                f.write("\n")
            
                f.write("FAILED CONVERSATION IDs:\n")
                for fail in self.conversion_failures:
                    f.write(f"  - {fail['conversation_id']}\n")
                f.write("\n")
            
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
                    
                    if fail['structural_issues']:
                        f.write(f"Structural Issues: {', '.join(fail['structural_issues'])}\n")
                    
                    if fail['problematic_nodes']:
                        f.write(f"\nProblematic Nodes (sample):\n")
                        for node in fail['problematic_nodes'][:3]:
                            f.write(f"  - Node {node['node_id']}: role={node.get('role')}, ")
                            f.write(f"content_type={node.get('content_type')}, issue={node.get('issue')}\n")
                    
                    if fail['trace_snippet']:
                        f.write(f"\nTrace: {fail['trace_snippet']}\n")
                    
                    f.write("\n" + "="*80 + "\n\n")
            
                # JSON format enables programmatic failure analysis
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