"""
Automated 2-Stage Pipeline Module for YouTube Stock Extractor.

Stage 1: Checks if pre-saved translated transcript exists; if yes, reuses it. Otherwise fetches, translates, and saves it.
Stage 2: Process transcript with Extractor engine, extracts recommendations, and saves report named 'DD-MM-YY - Video Title.<ext>' (overwrites on rerun).
"""

import os
import sys
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from stock_extractor.transcript_saver import fetch_and_save_translated_transcript, parse_saved_transcript_file
from stock_extractor.utils import parse_youtube_id, chunk_transcript
from stock_extractor.extractors import get_extractor
from stock_extractor.models import VideoReport
from stock_extractor import formatters

def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for Windows and Unix file names."""
    # Replace invalid characters /\:*?"<>|
    clean = re.sub(r'[\\/*?:"<>|]', '', name)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:120]

def run_pipeline(
    url_or_id: str,
    output_dir: str = "output",
    method: str = "auto",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_url: Optional[str] = None,
    report_format: str = "markdown"
) -> Tuple[str, str, VideoReport, bool]:
    """
    Run the end-to-end 2-stage automated pipeline.

    Returns:
        (transcript_file_path, report_file_path, report_object, transcript_was_reused)
    """
    video_id = parse_youtube_id(url_or_id)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: '{url_or_id}'")

    transcripts_dir = os.path.join(output_dir, "transcripts")
    reports_dir = os.path.join(output_dir, "reports")
    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # ---------------------------------------------------------
    # STAGE 1: Check & Reuse existing transcript or fetch/save
    # ---------------------------------------------------------
    transcript_filename = f"translated_transcript_{video_id}.txt"
    transcript_file_path = os.path.join(transcripts_dir, transcript_filename)
    transcript_was_reused = False

    if os.path.exists(transcript_file_path) and os.path.getsize(transcript_file_path) > 0:
        # Reuse existing transcript file directly
        transcript_was_reused = True
        snippets, metadata = parse_saved_transcript_file(transcript_file_path, video_id)
    else:
        # Fetch, translate, and save transcript file once
        saved_transcript_path, metadata = fetch_and_save_translated_transcript(
            url_or_id, 
            output_path=transcript_file_path
        )
        snippets, metadata = parse_saved_transcript_file(transcript_file_path, video_id)

    # ---------------------------------------------------------
    # STAGE 2: Analyze Transcript & Save Final Report
    # ---------------------------------------------------------
    chunks = chunk_transcript(snippets, max_duration=60.0, max_words=300)

    # Get Extractor Engine
    extractor = get_extractor(method=method, api_key=api_key, model=model, ollama_url=ollama_url)

    # Perform analysis
    recommendations = extractor.extract(chunks, video_id)

    # Build VideoReport Object
    report = VideoReport(
        video_id=video_id,
        video_url=metadata.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
        title=metadata.get("title", f"YouTube Video ({video_id})"),
        channel=metadata.get("channel", "Unknown Channel"),
        thumbnail_url=metadata.get("thumbnail_url", ""),
        extraction_method=extractor.name,
        recommendations=recommendations
    )

    # ---------------------------------------------------------
    # Report File Naming: 'DD-MM-YY - Video Caption.<ext>'
    # Overwrites on rerun
    # ---------------------------------------------------------
    today_str = datetime.now().strftime("%d-%m-%y")
    clean_title = sanitize_filename(report.title)

    ext_map = {"markdown": "md", "json": "json", "csv": "csv", "html": "html"}
    ext = ext_map.get(report_format.lower(), "md")

    report_filename = f"{today_str} - {clean_title}.{ext}"
    report_file_path = os.path.join(reports_dir, report_filename)

    formatted_content = ""
    if report_format.lower() == "markdown":
        formatted_content = formatters.format_markdown_report(report)
    elif report_format.lower() == "json":
        formatted_content = formatters.format_json_report(report)
    elif report_format.lower() == "csv":
        formatted_content = formatters.format_csv_report(report)
    elif report_format.lower() == "html":
        formatted_content = formatters.format_html_report(report)
    else:
        formatted_content = formatters.format_markdown_report(report)

    # Overwrite if rerun
    with open(report_file_path, "w", encoding="utf-8") as f:
        f.write(formatted_content)

    return transcript_file_path, report_file_path, report, transcript_was_reused
