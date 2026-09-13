"""
FastAPI Web Application for YouTube Stock Extractor (Indian Market Edition).
Provides SSE streaming for live progress, REST API endpoints, Excel/Markdown exports, and Single Page UI.
"""

import os
import io
import re
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

from fastapi import FastAPI, Depends, Query, HTTPException, Response, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from stock_extractor.db import (
    init_db, get_db, get_video_report, get_recent_videos, search_stock_recommendations
)
from stock_extractor.service import stream_video_extraction
from stock_extractor.exporters import export_markdown, export_excel, export_csv, export_json
from stock_extractor.stock_quotes import get_stock_quote_and_fundamentals
from stock_extractor.storage import get_storage_stats, prune_expired_records
from stock_extractor.utils import parse_youtube_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database table initialization on startup."""
    init_db()
    yield


app = FastAPI(
    title="YouTube Stock Extractor (Indian Market)",
    description="Automated AI pipeline extracting Indian stock recommendations from YouTube videos.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for external API consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request schemas
class ExtractRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL or 11-char Video ID")
    api_key: Optional[str] = Field(None, description="Optional Google Gemini API key (BYOK)")
    model: Optional[str] = Field("gemini-3.6-flash", description="Gemini model name")


# -------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Health check endpoint for Render / Leapcell deployment monitoring."""
    return {"status": "ok", "service": "YouTube Stock Extractor"}


@app.get("/api/stream-extract")
async def stream_extract(
    url: str = Query(..., description="YouTube video URL or 11-char Video ID"),
    api_key: Optional[str] = Query(None, description="Optional user Gemini API Key"),
    model: str = Query("gemini-3.6-flash", description="Gemini model name"),
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) streaming endpoint providing live real-time progress
    as the transcript is fetched, translated, analyzed with Gemini, and stored.
    """
    return StreamingResponse(
        stream_video_extraction(url_or_id=url, api_key=api_key, model=model, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/extract")
async def extract_post(
    req: ExtractRequest,
    db: Session = Depends(get_db)
):
    """Non-streaming JSON endpoint for programmatic extraction."""
    video_id = parse_youtube_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL or Video ID")

    # Check database cache first
    cached = get_video_report(db, video_id)
    if cached and cached.recommendations:
        return cached.to_dict()

    # Run extraction via streaming generator until completion
    final_data = None
    last_error = None

    async for event_str in stream_video_extraction(req.url, req.api_key, req.model or "gemini-3.6-flash", db):
        clean_line = event_str.replace("data: ", "").strip()
        if clean_line:
            try:
                evt = json.loads(clean_line)
                if evt.get("phase") == "completed":
                    final_data = evt.get("data")
                elif evt.get("phase") == "error":
                    last_error = evt.get("error")
            except Exception:
                pass

    if last_error:
        raise HTTPException(status_code=500, detail=last_error)

    if final_data:
        return final_data

    raise HTTPException(status_code=500, detail="Extraction failed to produce results")


@app.get("/api/videos")
async def list_videos(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve recently analyzed videos for the gallery feed."""
    videos = get_recent_videos(db, limit=limit, offset=offset)
    return {
        "count": len(videos),
        "videos": [
            {
                "video_id": v.id,
                "title": v.title,
                "channel": v.channel,
                "video_url": v.video_url,
                "thumbnail_url": v.thumbnail_url,
                "total_recommendations": v.total_recommendations,
                "buy_count": v.buy_count,
                "sell_count": v.sell_count,
                "hold_count": v.hold_count,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in videos
        ]
    }


@app.get("/api/videos/{video_id}")
async def get_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve a single video's full report and recommendations."""
    video = get_video_report(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video report not found")
    return video.to_dict()


@app.get("/api/stocks/{ticker}")
async def get_stock_history(
    ticker: str,
    db: Session = Depends(get_db)
):
    """Find all past analyst recommendations across all videos for a given stock ticker."""
    recs = search_stock_recommendations(db, ticker)
    return {
        "ticker": ticker.upper(),
        "total_mentions": len(recs),
        "recommendations": [r.to_dict() for r in recs]
    }


@app.get("/api/stocks/{ticker}/quote")
async def get_stock_quote(ticker: str):
    """
    Retrieve live CMP, 6 core valuation fundamentals (P/E, Market Cap, 52W High/Low, P/B, Div Yield),
    and 30-day sparkline history for hover cards.
    """
    return get_stock_quote_and_fundamentals(ticker)


@app.get("/api/export/{video_id}")
async def export_report(
    video_id: str,
    format: str = Query("md", pattern="^(md|markdown|xlsx|excel|csv|json)$"),
    db: Session = Depends(get_db)
):
    """
    Download video analysis report as styled Excel (.xlsx), Markdown (.md), CSV, or JSON.
    """
    video = get_video_report(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video report not found")

    video_data = video.to_dict()
    safe_title = video.title.replace("₹", "Rs")
    clean_title = re.sub(r'[\\/*?:"<>|]', '', safe_title).strip()[:50]
    ascii_title = clean_title.encode('ascii', 'ignore').decode('ascii').strip() or "report"
    date_str = video.created_at.strftime("%d-%m-%y") if video.created_at else "report"
    base_filename = f"{date_str} - {ascii_title}"

    fmt = format.lower()

    if fmt in ["xlsx", "excel"]:
        excel_bytes = export_excel(video_data)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{base_filename}.xlsx"'
            }
        )
    elif fmt in ["md", "markdown"]:
        md_text = export_markdown(video_data)
        return Response(
            content=md_text,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{base_filename}.md"'
            }
        )
    elif fmt == "csv":
        csv_text = export_csv(video_data)
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{base_filename}.csv"'
            }
        )
    else:
        json_text = export_json(video_data)
        return Response(
            content=json_text,
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{base_filename}.json"'
            }
        )


@app.get("/api/system/storage")
async def system_storage_stats():
    """Get database row counts, disk storage usage, and 500MB free-tier status."""
    return get_storage_stats()


@app.post("/api/system/prune")
async def trigger_storage_prune(days: int = Query(15, ge=1, le=365)):
    """Manually purge records older than specified retention days and run VACUUM."""
    return prune_expired_records(retention_days=days)


# -------------------------------------------------------------
# Static Files & SPA Frontend
# -------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def serve_spa():
    """Serve the Single Page Application index.html."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        {"message": "Frontend static file index.html is being prepared. Check /api/health or /docs."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
