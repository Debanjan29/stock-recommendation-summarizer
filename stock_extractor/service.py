"""
Unified extraction pipeline service supporting real-time Server-Sent Events (SSE) streaming and direct async execution.
"""

import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from sqlalchemy.orm import Session

from stock_extractor.utils import parse_youtube_id, format_timestamp, make_timestamp_url
from stock_extractor.youtube import fetch_transcript
from stock_extractor.transliteration import ensure_no_pure_hindi
from stock_extractor.extractors.gemini_ext import GeminiExtractor
from stock_extractor.db import get_video_report, save_video_report


async def stream_video_extraction(
    url_or_id: str,
    api_key: Optional[str] = None,
    model: str = "gemini-3.6-flash",
    db: Optional[Session] = None
) -> AsyncGenerator[str, None]:
    """
    Asynchronous generator yielding Server-Sent Events (SSE) formatted strings
    for real-time frontend progress tracking.
    """
    def make_event(phase: str, status: str, progress: int, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> str:
        payload = {
            "phase": phase,
            "status": status,
            "progress": progress,
            "data": data,
            "error": error
        }
        return f"data: {json.dumps(payload)}\n\n"

    video_id = parse_youtube_id(url_or_id)
    if not video_id:
        yield make_event("error", "Invalid YouTube URL or Video ID provided.", 0, error="Invalid YouTube URL")
        return

    # -------------------------------------------------------------
    # Step 1: Database Cache Check
    # -------------------------------------------------------------
    yield make_event("cache_check", "Checking database for existing analysis...", 10)
    await asyncio.sleep(0.1)

    if db:
        cached_video = get_video_report(db, video_id)
        if cached_video and cached_video.recommendations:
            yield make_event(
                "completed", 
                f"Retrieved existing analysis from database ({len(cached_video.recommendations)} recommendations).", 
                100, 
                data=cached_video.to_dict()
            )
            return

    # -------------------------------------------------------------
    # Step 2: Fetch Metadata & Transcript
    # -------------------------------------------------------------
    yield make_event("transcript", "Downloading YouTube transcript and video metadata...", 30)
    await asyncio.sleep(0.1)

    try:
        # Run blocking network fetch in executor to keep event loop free
        loop = asyncio.get_event_loop()
        snippets, metadata = await loop.run_in_executor(None, fetch_transcript, video_id)
    except Exception as e:
        yield make_event(
            "error", 
            f"Failed to fetch transcript: {e}", 
            0, 
            error=str(e)
        )
        return

    if not snippets:
        yield make_event("error", "Transcript is empty or unavailable for this video.", 0, error="Empty transcript")
        return

    # Build formatted transcript text
    full_transcript_lines = []
    for s in snippets:
        sec = s.get("start", 0.0)
        time_str = format_timestamp(sec)
        txt = s.get("text", "").strip()
        if txt:
            full_transcript_lines.append(f"[{time_str}] {txt}")

    full_transcript_text = "\n".join(full_transcript_lines)

    # -------------------------------------------------------------
    # Step 3: LLM Analysis with Gemini
    # -------------------------------------------------------------
    yield make_event("llm_analyze", f"Analyzing transcript with Google Gemini ({model})...", 65)
    await asyncio.sleep(0.1)

    try:
        extractor = GeminiExtractor(api_key=api_key, model=model)
        loop = asyncio.get_event_loop()
        recommendations = await loop.run_in_executor(
            None, extractor.extract_from_text, full_transcript_text, video_id
        )
    except Exception as e:
        # Fallback check if local agy CLI can be invoked
        try:
            from stock_extractor.extractors.agy_ext import AGYExtractor
            agy = AGYExtractor()
            if agy.agy_bin:
                cause = "Gemini key missing." if "missing" in str(e).lower() else f"Gemini error ({e})."
                yield make_event("llm_analyze", f"{cause} Falling back to local Antigravity AGY CLI (takes ~60-90s)...", 75)
                # Ensure output/transcripts directory has this transcript for AGY
                t_dir = os.path.join("output", "transcripts")
                os.makedirs(t_dir, exist_ok=True)
                t_file = os.path.join(t_dir, f"translated_transcript_{video_id}.txt")
                if not os.path.exists(t_file):
                    try:
                        with open(t_file, "w", encoding="utf-8") as tf:
                            tf.write(f"Title: {metadata.get('title')}\nChannel: {metadata.get('channel')}\n\n")
                            tf.write(full_transcript_text)
                    except Exception:
                        pass

                chunks = [{"text": s["text"], "start": s["start"], "duration": s["duration"]} for s in snippets]
                recommendations = await loop.run_in_executor(None, agy.extract, chunks, video_id)
                extractor = agy
            else:
                raise e
        except Exception:
            yield make_event(
                "error", 
                f"AI Extraction failed: {e}. (Tip: Add GEMINI_API_KEY in .env or click the API Key button in the UI)", 
                0, 
                error=str(e)
            )
            return

    # -------------------------------------------------------------
    # Step 4: Validation & Sanitization
    # -------------------------------------------------------------
    yield make_event("market_validate", "Sanitizing Indian market tickers and transliterating...", 85)
    await asyncio.sleep(0.1)

    clean_title = ensure_no_pure_hindi(metadata.get("title", f"YouTube Video ({video_id})"))
    clean_channel = ensure_no_pure_hindi(metadata.get("channel", "Unknown Channel"))
    metadata["title"] = clean_title
    metadata["channel"] = clean_channel

    # -------------------------------------------------------------
    # Step 5: Save to Database
    # -------------------------------------------------------------
    yield make_event("db_save", "Saving report and recommendations to database...", 95)
    await asyncio.sleep(0.1)

    result_data = None
    if db:
        try:
            saved_video = save_video_report(
                db=db,
                video_id=video_id,
                metadata=metadata,
                transcript_text=full_transcript_text,
                recommendations=recommendations,
                engine_name=extractor.name
            )
            result_data = saved_video.to_dict()
        except Exception as dbe:
            # If DB save encounters an issue, still return results to the user
            pass

    if not result_data:
        # Construct fallback dictionary
        rec_dicts = []
        buy_count = 0
        sell_count = 0
        hold_count = 0

        for r in recommendations:
            act = r.action.upper()
            if any(b in act for b in ["BUY", "ACCUMULATE"]):
                buy_count += 1
            elif any(s in act for s in ["SELL", "AVOID"]):
                sell_count += 1
            else:
                hold_count += 1

            rec_dicts.append(r.to_dict() if hasattr(r, "to_dict") else r)

        result_data = {
            "video_id": video_id,
            "title": clean_title,
            "channel": clean_channel,
            "video_url": metadata.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
            "thumbnail_url": metadata.get("thumbnail_url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
            "extraction_engine": extractor.name,
            "total_recommendations": len(recommendations),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
            "recommendations": rec_dicts
        }

    # -------------------------------------------------------------
    # Step 6: Complete
    # -------------------------------------------------------------
    yield make_event(
        "completed", 
        f"Extraction complete! Found {len(recommendations)} recommendations.", 
        100, 
        data=result_data
    )
