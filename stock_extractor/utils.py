"""
Utility functions for YouTube URL parsing, timestamp conversion, and transcript chunking.
"""

import re
from typing import List, Dict, Any, Optional

def parse_youtube_id(url_or_id: str) -> Optional[str]:
    """
    Extract 11-character YouTube video ID from various URL formats or direct ID string.
    
    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - Direct 11-char ID
    """
    url_or_id = url_or_id.strip()
    
    # Direct 11-character ID pattern
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
        
    patterns = [
        r'(?:v=|\/)([a-zA-Z0-9_-]{11})(?:[&?\/]|$)',
        r'youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
            
    return None

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS format."""
    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def make_timestamp_url(video_id: str, seconds: float) -> str:
    """Create a shareable YouTube URL with timestamp parameter."""
    sec_int = int(round(seconds))
    return f"https://youtu.be/{video_id}?t={sec_int}"

def chunk_transcript(
    snippets: List[Dict[str, Any]], 
    max_duration: float = 60.0, 
    max_words: int = 350
) -> List[Dict[str, Any]]:
    """
    Group fine-grained transcript snippets into coherent contiguous chunks.
    Each chunk retains start_time, duration, text, and source snippets.
    """
    if not snippets:
        return []
        
    chunks = []
    current_chunk = {
        'start': snippets[0].get('start', 0.0),
        'duration': 0.0,
        'text': '',
        'snippets': []
    }
    
    words_count = 0
    chunk_start = snippets[0].get('start', 0.0)
    
    for item in snippets:
        text = item.get('text', '').strip()
        start = item.get('start', 0.0)
        dur = item.get('duration', 0.0)
        
        if not text:
            continue
            
        text_words = len(text.split())
        
        # Check chunk boundary conditions
        if current_chunk['text'] and ((start - chunk_start >= max_duration) or (words_count + text_words > max_words)):
            # Finalize current chunk
            current_chunk['duration'] = round(start - chunk_start, 2)
            current_chunk['text'] = current_chunk['text'].strip()
            chunks.append(current_chunk)
            
            # Start new chunk
            chunk_start = start
            words_count = text_words
            current_chunk = {
                'start': start,
                'duration': dur,
                'text': text,
                'snippets': [item]
            }
        else:
            if current_chunk['text']:
                current_chunk['text'] += " " + text
            else:
                current_chunk['text'] = text
            words_count += text_words
            current_chunk['snippets'].append(item)
            current_chunk['duration'] = round((start + dur) - chunk_start, 2)
            
    if current_chunk['text']:
        current_chunk['text'] = current_chunk['text'].strip()
        chunks.append(current_chunk)
        
    return chunks
