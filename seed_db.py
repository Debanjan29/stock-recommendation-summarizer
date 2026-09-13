"""
One-time utility to sync existing markdown reports in output/reports/ into the database.
"""

import os
import glob
import re
from datetime import datetime

import sys

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from stock_extractor.db import init_db, get_session_factory, save_video_report, Video
from stock_extractor.extractors.llm_base import parse_llm_markdown_table_response


def seed():
    init_db()
    SessionFactory = get_session_factory()
    db = SessionFactory()

    reports_dir = os.path.join(os.path.dirname(__file__), "output", "reports")
    if not os.path.exists(reports_dir):
        print("No output/reports directory found.")
        return

    md_files = glob.glob(os.path.join(reports_dir, "*.md"))
    print(f"Found {len(md_files)} markdown reports to check...")

    for f_path in md_files:
        try:
            with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Find video ID
            vid_match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', content) or \
                        re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', content)
            if not vid_match:
                continue

            video_id = vid_match.group(1)

            # Check if already in DB
            existing = db.query(Video).filter(Video.id == video_id).first()
            if existing:
                print(f"✓ Video {video_id} already in database. Skipping.")
                continue

            # Extract title and channel
            title_match = re.search(r'\*\*Video Title:\*\*\s*\[?([^\]\n]+)\]?', content)
            channel_match = re.search(r'\*\*Channel:\*\*\s*(.+)$', content, re.M)

            title = title_match.group(1).strip() if title_match else f"YouTube Video ({video_id})"
            channel = channel_match.group(1).strip() if channel_match else "Unknown Channel"

            # Parse recommendations table
            recs = parse_llm_markdown_table_response(content, video_id)
            if not recs:
                continue

            metadata = {
                "title": title,
                "channel": channel,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            }

            save_video_report(
                db=db,
                video_id=video_id,
                metadata=metadata,
                transcript_text="",
                recommendations=recs,
                engine_name="Antigravity AGY / Gemini"
            )
            print(f"✓ Imported {video_id}: '{title}' ({len(recs)} recommendations)")
        except Exception as e:
            print(f"Error seeding {f_path}: {e}")

    db.close()
    print("Database seeding completed.")


if __name__ == "__main__":
    seed()
