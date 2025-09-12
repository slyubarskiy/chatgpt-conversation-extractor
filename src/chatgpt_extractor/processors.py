"""
Message processing components for content extraction and filtering.
"""

import re
from typing import Dict, List, Optional, Any

from .trackers import SchemaEvolutionTracker


class MessageProcessor:
    """Process and filter messages with enhanced content handling."""
    
    def __init__(self, tracker: SchemaEvolutionTracker):
        self.tracker = tracker
        
    def should_filter_message(self, msg: Dict[str, Any]) -> bool:
        """Determine if message should be filtered out.
        
        Args:
            msg: Message dictionary from conversation node
            
        Returns:
            True if message should be excluded from output
        """
        # Check if visually hidden
        metadata = msg.get('metadata', {})
        if metadata.get('is_visually_hidden_from_conversation'):
            return True
        
        author = msg.get('author', {})
        author_role = author.get('role')
        
        # Filter internal system messages (but keep user system messages)
        if author_role == 'system' and not self.is_user_system_message(msg):
            return True
        
        # Filter tool messages unless they contain DALL-E images
        if author_role == 'tool':
            content = msg.get('content', {})
            if not self._contains_dalle_image(content):
                return True
        
        # Filter specific content types
        content = msg.get('content', {})
        content_type = content.get('content_type', '')
        
        if content_type in ['model_editable_context', 'thoughts', 'reasoning_recap']:
            return True
        
        # Filter empty assistant placeholder messages
        if (author.get('role') == 'assistant' and 
            content_type == 'text' and 
            content.get('parts') == ['']):
            return True
        
        return False
    
    def _contains_dalle_image(self, content: Dict[str, Any]) -> bool:
        """Check if content contains DALL-E generated image."""
        if content.get('content_type') == 'multimodal_text':
            for part in content.get('parts', []):
                if isinstance(part, dict):
                    if part.get('content_type') == 'image_asset_pointer':
                        metadata = part.get('metadata')
                        # Fixed NoneType bug: Must check metadata exists before 'in' operator
                        if metadata and ('dalle' in metadata or 'dalle_prompt' in metadata):
                            return True
        return False
    
    def is_user_system_message(self, msg: Dict[str, Any]) -> bool:
        """Check if system message should be preserved."""
        metadata = msg.get('metadata', {})
        if metadata.get('is_user_system_message'):
            return True
        
        content = msg.get('content', {})
        if content.get('content_type') == 'user_editable_context':
            return True
        
        return False
    
    def extract_message_content(self, msg: Dict[str, Any], conv_id: str) -> Optional[str]:
        """Extract text content from message based on content_type.
        
        Args:
            msg: Message dictionary containing content and metadata
            conv_id: Conversation ID for tracking
            
        Returns:
            Formatted message content or None if empty/filtered
        """
        content = msg.get('content', {})
        content_type = content.get('content_type', '')
        
        # Track content type
        if content_type:
            self.tracker.track_content_type(content_type, conv_id)
        
        if content_type == 'text':
            # Standard text message
            parts = content.get('parts', [])
            if parts:
                return self.extract_from_parts(parts, conv_id)
                
        elif content_type == 'code':
            # Code message with language
            text = content.get('text', '')
            lang = content.get('language', '')
            if text:
                return f"```{lang}\n{text}\n```"
                
        elif content_type == 'execution_output':
            # Code execution output
            text = content.get('text', '')
            if text:
                return f"```output\n{text}\n```"
                
        elif content_type == 'multimodal_text':
            # Mixed content (text, images, etc.)
            parts = content.get('parts', [])
            if parts:
                return self.extract_from_parts(parts, conv_id)
                
        elif content_type == 'user_editable_context':  # Custom GPT instructions
            text = content.get('text', '')
            if text:
                # Strip OpenAI's wrapper text from custom instructions
                lines = text.split('\n')
                result_lines = []
                in_instructions = False
                
                for line in lines:
                    if 'The user provided the following information' in line:
                        in_instructions = True
                    elif in_instructions:
                        result_lines.append(line)
                
                result = '\n'.join(result_lines).strip()
                # If extraction failed, try direct wrapper removal
                if not result or len(result) > len(text) * 0.9:
                    result = text
                    for wrapper in ['The user provided the following information about themselves:',
                                  'The user provided the additional info about how they would like you to respond:']:
                        result = result.replace(wrapper, '').strip()
                
                return result if result else None
                
        elif content_type == 'tether_browsing_display':  # Rendered webpage
            result = content.get('result', '')
            if result:
                return result
                
        elif content_type == 'tether_quote':  # Web search citation
            title = content.get('title', '')
            text = content.get('text', '')
            url = content.get('url', '')
            
            parts = []
            if title:
                parts.append(f"**{title}**")
            if text:
                parts.append(f"> {text}")
            if url:
                parts.append(f"Source: {url}")
            
            return '\n'.join(parts) if parts else None
        
        elif content_type == 'sonic_webpage':  # Web reader content
            text = content.get('text', '')
            url = content.get('url', '')
            if text:
                result = text
                if url:
                    result = f"[Web Content from {url}]\n{result}"
                return result
        
        elif content_type == 'system_error':
            error_text = content.get('text', '')
            error_name = content.get('name', 'Error')
            return f"[System Error: {error_name}]\n{error_text}"
        
        elif content_type:
            # Unknown content type - attempt generic extraction
            self.tracker.track_content_type(content_type, conv_id)
            
            # Try common fields
            if text := content.get('text'):
                return text
            if parts := content.get('parts'):
                return self.extract_from_parts(parts, conv_id)
        
        return None
    
    def extract_from_parts(self, parts: List[Any], conv_id: str) -> Optional[str]:
        """Extract content from parts array (handles multimodal content)."""
        # Defensive programming for None or invalid parts
        if parts is None:
            return None
        if not isinstance(parts, list):
            return None
        if not parts:  # Empty list
            return None
        
        result_parts = []
        
        for part in parts:
            if part is None:  # Defensive: Handle None parts gracefully
                continue
                
            if isinstance(part, str):
                # Simple text part
                if part:
                    result_parts.append(part)
                    
            elif isinstance(part, dict):
                # Complex part (could be image, file, etc.)
                part_type = part.get('content_type', '')
                
                if part_type:
                    self.tracker.track_part_type(part_type, conv_id)
                
                if part_type == 'image_asset_pointer':
                    # Image reference - defensive metadata handling
                    metadata = part.get('metadata')
                    if metadata is not None:
                        # Check for DALL-E prompt in nested structure
                        dalle_dict = metadata.get('dalle')
                        if dalle_dict is not None and isinstance(dalle_dict, dict):
                            if dalle_prompt := dalle_dict.get('prompt'):
                                result_parts.append(f"[DALL-E Image: {dalle_prompt}]")
                            else:
                                result_parts.append("[Image]")
                        elif dalle_prompt := metadata.get('dalle_prompt'):
                            result_parts.append(f"[DALL-E Image: {dalle_prompt}]")
                        else:
                            result_parts.append("[Image]")
                    else:
                        result_parts.append("[Image]")
                        
                elif part_type == 'audio_transcription':
                    # Audio transcription
                    text = part.get('text', '')
                    if text:
                        result_parts.append(f"[Audio transcription]\n{text}")
                        
                elif part_type == 'audio_asset_pointer':
                    # Audio file reference
                    result_parts.append("[Audio file]")
                    
                elif part_type == 'video_asset_pointer':
                    # Video file reference
                    result_parts.append("[Video file]")
                    
                elif part_type == 'real_time_user_audio_video_asset_pointer':
                    # Real-time voice conversation with video
                    result_parts.append("[Voice conversation with video]")
                    
                elif part_type == 'code_interpreter_output':
                    # Code interpreter output
                    output = part.get('output', '')
                    if output:
                        result_parts.append(f"```output\n{output}\n```")
                        
                else:
                    # Unknown part type - try to extract text
                    if text := part.get('text'):
                        result_parts.append(text)
        
        return '\n'.join(result_parts) if result_parts else None
    
    def extract_citations(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract citations from message metadata."""
        citations = []
        metadata = msg.get('metadata', {})
        
        if 'citations' in metadata:
            for citation in metadata.get('citations', []):
                citation_data = {}
                
                # Extract citation metadata
                if citation_meta := citation.get('metadata'):
                    if title := citation_meta.get('title'):
                        citation_data['title'] = title
                    if url := citation_meta.get('url'):
                        citation_data['url'] = url
                    if type_ := citation_meta.get('type'):
                        citation_data['type'] = type_
                
                # Extract quoted text
                if quote := citation.get('quote'):
                    citation_data['quote'] = quote
                
                if citation_data:
                    citations.append(citation_data)
        
        return citations
    
    def extract_web_urls(self, msg: Dict[str, Any], conv_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """Extract web URLs from 6+ sources in message and conversation.
        
        Sources checked:
        1. Citation metadata URLs
        2. Conversation safe_urls
        3. Content URL fields (tether_quote, sonic_webpage)
        4. Content domain fields
        5. Content result text (regex)
        6. Parts array text (regex)
        """
        urls = set()
        
        content = msg.get('content', {})
        content_type = content.get('content_type', '')
        
        # Different extraction based on content type
        if content_type == 'tether_quote':
            # Extract from tether_quote
            if url := content.get('url'):
                urls.add(url)
            if domain := content.get('domain'):
                urls.add(f"https://{domain}")
                
        elif content_type == 'tether_browsing_display':
            # Check result field for URLs
            if result := content.get('result'):
                # Critical: Use module-level 're' (local import caused 89% of failures)
                url_pattern = r'https?://[^\s<>"]+'
                found_urls = re.findall(url_pattern, str(result))
                urls.update(found_urls)
            
            # Check for URL in other fields
            if url := content.get('url'):
                urls.add(url)
                
        elif content_type == 'sonic_webpage':
            # Extract from sonic webpage
            if url := content.get('url'):
                urls.add(url)
            if domain := content.get('domain'):
                urls.add(f"https://{domain}")
                
        # Generic URL extraction from any content type
        # Check citations
        citations = msg.get('metadata', {}).get('citations', [])
        for citation in citations:
            if citation_meta := citation.get('metadata'):
                if url := citation_meta.get('url'):
                    urls.add(url)
        
        # Check parts for text containing URLs
        if 'parts' in content:
            parts = content.get('parts', [])
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, str):
                        # Extract URLs from text parts
                        url_pattern = r'https?://[^\s<>"]+'
                        found_urls = re.findall(url_pattern, part)
                        urls.update(found_urls)
        
        # Check conversation-level safe_urls
        if conv_data and 'safe_urls' in conv_data:
            urls.update(conv_data['safe_urls'])
        
        return sorted(list(urls))
    
    def extract_file_names(self, msg: Dict[str, Any]) -> List[str]:
        """Extract uploaded file names from message attachments."""
        files = []
        
        # Check attachments metadata - defensive handling
        metadata = msg.get('metadata')
        if metadata is not None and isinstance(metadata, dict):
            if attachments := metadata.get('attachments'):
                if isinstance(attachments, list):
                    for attachment in attachments:
                        if isinstance(attachment, dict) and attachment is not None:
                            if name := attachment.get('name'):
                                files.append(name)
        
        # Check content for file references
        content = msg.get('content', {})
        
        # Check parts for file asset pointers
        if 'parts' in content:
            parts = content.get('parts', [])
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and part is not None:
                        if part.get('asset_pointer'):
                            # File upload reference - defensive metadata handling
                            metadata = part.get('metadata')
                            if metadata is not None and isinstance(metadata, dict):
                                if file_name := metadata.get('file_name'):
                                    files.append(file_name)
        
        return files