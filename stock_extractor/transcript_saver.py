"""
Module for fetching, translating, saving, and reading YouTube transcripts to/from a text file.
"""

import os
import sys
import json
import re
from typing import Dict, Any, Tuple, Optional, List
from stock_extractor.youtube import fetch_transcript
from stock_extractor.utils import format_timestamp, parse_youtube_id

def fetch_and_save_translated_transcript(
    url_or_id: str, 
    output_path: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Fetch YouTube video transcript, translate it to English (if in Hindi or non-English),
    format it with timestamps and metadata, and save to a text file.

    Returns:
        (saved_file_path, metadata)
    """
    video_id = parse_youtube_id(url_or_id)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: '{url_or_id}'")

    # 1. Fetch transcript (automatically translated if non-English) and metadata
    snippets, metadata = fetch_transcript(video_id)

    if not output_path:
        output_path = f"translated_transcript_{video_id}.txt"

    # 2. Build formatted transcript file content
    lines = [
        f"============================================================",
        f" YOUTUBE TRANSLATED TRANSCRIPT REPORT",
        f"============================================================",
        f"Title:        {metadata.get('title', 'N/A')}",
        f"Channel:      {metadata.get('channel', 'N/A')}",
        f"Video ID:     {video_id}",
        f"Video URL:    {metadata.get('video_url', f'https://www.youtube.com/watch?v={video_id}')}",
        f"Thumbnail:    {metadata.get('thumbnail_url', '')}",
        f"Snippet Count:{len(snippets)}",
        f"============================================================",
        f"",
        f"--- FULL TRANSLATED TRANSCRIPT TEXT WITH TIMESTAMPS ---",
        f""
    ]

    for snippet in snippets:
        start_sec = snippet.get('start', 0.0)
        time_str = format_timestamp(start_sec)
        text = snippet.get('text', '').strip()
        if text:
            lines.append(f"[{time_str}] {text}")

    content = "\n".join(lines)

    # 3. Save to output file
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path, metadata

def parse_saved_transcript_file(file_path: str, fallback_video_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Read pre-saved transcript text file and parse it back into (snippets, metadata).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Saved transcript file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    metadata = {
        "video_id": fallback_video_id,
        "video_url": f"https://www.youtube.com/watch?v={fallback_video_id}",
        "title": f"YouTube Video ({fallback_video_id})",
        "channel": "Unknown Channel",
        "thumbnail_url": f"https://i.ytimg.com/vi/{fallback_video_id}/hqdefault.jpg"
    }

    # Parse metadata header
    title_match = re.search(r'^Title:\s*(.+)$', content, re.M)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    channel_match = re.search(r'^Channel:\s*(.+)$', content, re.M)
    if channel_match:
        metadata["channel"] = channel_match.group(1).strip()

    vid_match = re.search(r'^Video ID:\s*(.+)$', content, re.M)
    if vid_match:
        metadata["video_id"] = vid_match.group(1).strip()

    url_match = re.search(r'^Video URL:\s*(.+)$', content, re.M)
    if url_match:
        metadata["video_url"] = url_match.group(1).strip()

    thumb_match = re.search(r'^Thumbnail:\s*(.+)$', content, re.M)
    if thumb_match:
        metadata["thumbnail_url"] = thumb_match.group(1).strip()

    # Parse transcript timestamps [MM:SS] or [HH:MM:SS]
    snippets = []
    timestamp_pattern = re.compile(r'^\[(\d{2}:)?(\d{2}):(\d{2})\]\s*(.+)$', re.M)

    matches = timestamp_pattern.findall(content)
    for match in matches:
        hrs_str, mins_str, secs_str, text = match
        hrs = int(hrs_str.replace(":", "")) if hrs_str else 0
        mins = int(mins_str)
        secs = int(secs_str)
        total_seconds = float(hrs * 3600 + mins * 60 + secs)

        snippets.append({
            "text": text.strip(),
            "start": total_seconds,
            "duration": 5.0
        })

    return snippets, metadata

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcript_saver.py <YOUTUBE_URL_OR_ID> [OUTPUT_FILE_PATH]")
        sys.exit(1)

    url_arg = sys.argv[1]
    out_arg = sys.argv[2] if len(sys.argv) > 2 else None
    file_path, meta = fetch_and_save_translated_transcript(url_arg, out_arg)
    print(f"✓ Successfully saved translated transcript for '{meta.get('title')}' to: {file_path}")
