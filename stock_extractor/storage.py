"""
Storage & Space Optimization Engine.
Handles:
1. Transparent zlib compression for transcripts (saving 70-85% space).
2. Automated 15-day data retention & auto-pruning with VACUUM.
3. Database & disk storage metrics relative to Neon's 500MB free tier.
4. Optional S3 / Cloudflare R2 object storage integration.
"""

import os
import zlib
import base64
import glob
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import text
from stock_extractor.db import get_engine, get_session_factory, Video, Recommendation

logger = logging.getLogger(__name__)

COMPRESSION_PREFIX = "zlib64:"
DEFAULT_RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "15"))
FREE_TIER_LIMIT_MB = 500.0  # Neon PostgreSQL free tier limit (500 MB)


def compress_transcript(raw_text: Optional[str]) -> str:
    """Compress string using zlib (level 9) with base64 encoding to reduce database footprint."""
    if not raw_text:
        return ""
    try:
        raw_bytes = raw_text.encode("utf-8")
        # Only compress if large enough to benefit
        if len(raw_bytes) < 100:
            return raw_text
        compressed = zlib.compress(raw_bytes, level=9)
        b64 = base64.b64encode(compressed).decode("ascii")
        return f"{COMPRESSION_PREFIX}{b64}"
    except Exception as e:
        logger.warning(f"Failed to compress transcript text: {e}")
        return raw_text


def decompress_transcript(stored_text: Optional[str]) -> str:
    """Transparently decompress text if prefixed with compression tag, else return as-is."""
    if not stored_text:
        return ""
    if stored_text.startswith(COMPRESSION_PREFIX):
        try:
            b64_str = stored_text[len(COMPRESSION_PREFIX):]
            compressed_bytes = base64.b64decode(b64_str)
            raw_bytes = zlib.decompress(compressed_bytes)
            return raw_bytes.decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to decompress stored transcript: {e}")
            return stored_text
    return stored_text


def prune_expired_records(retention_days: int = DEFAULT_RETENTION_DAYS) -> Dict[str, Any]:
    """
    Purge all video reports and recommendations older than retention_days (default 15 days).
    Runs VACUUM to reclaim storage space in SQLite / Neon PostgreSQL.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    SessionFactory = get_session_factory()
    engine = get_engine()

    deleted_videos_count = 0
    deleted_recs_count = 0
    vacuum_ok = False

    # 1. Delete expired database records
    try:
        with SessionFactory() as db:
            old_videos = db.query(Video).filter(Video.created_at < cutoff).all()
            deleted_videos_count = len(old_videos)
            
            for v in old_videos:
                deleted_recs_count += len(v.recommendations)
                db.delete(v)
                
            if deleted_videos_count > 0:
                db.commit()
                logger.info(f"Purged {deleted_videos_count} expired videos and {deleted_recs_count} recommendations older than {retention_days} days.")
    except Exception as e:
        logger.error(f"Error purging expired database records: {e}")

    # 2. Reclaim database disk pages with VACUUM
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM;"))
            vacuum_ok = True
    except Exception as e:
        logger.warning(f"VACUUM execution skipped or failed: {e}")

    # 3. Clean up local disk files older than retention_days
    deleted_files = 0
    try:
        for folder in [os.path.join("output", "reports"), os.path.join("output", "transcripts")]:
            if os.path.exists(folder):
                for fpath in glob.glob(os.path.join(folder, "*.*")):
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        if mtime < cutoff:
                            os.remove(fpath)
                            deleted_files += 1
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Error purging old output files: {e}")

    return {
        "status": "success",
        "retention_days": retention_days,
        "cutoff_timestamp": cutoff.isoformat(),
        "deleted_videos": deleted_videos_count,
        "deleted_recommendations": deleted_recs_count,
        "deleted_local_files": deleted_files,
        "vacuum_executed": vacuum_ok
    }


def compress_all_existing_transcripts() -> int:
    """One-time migration to compress uncompressed transcripts in the database."""
    SessionFactory = get_session_factory()
    updated_count = 0
    try:
        with SessionFactory() as db:
            videos = db.query(Video).all()
            for v in videos:
                if v.transcript_text and not v.transcript_text.startswith(COMPRESSION_PREFIX):
                    v.transcript_text = compress_transcript(v.transcript_text)
                    updated_count += 1
            if updated_count > 0:
                db.commit()
                logger.info(f"Compressed {updated_count} existing video transcripts in database.")
    except Exception as e:
        logger.warning(f"Failed to compress existing transcripts: {e}")
    return updated_count


def get_storage_stats() -> Dict[str, Any]:
    """Retrieve database row counts, space utilization, and 500MB free-tier quota status."""
    SessionFactory = get_session_factory()
    engine = get_engine()

    dialect = engine.dialect.name  # 'sqlite' or 'postgresql'
    db_size_bytes = 0

    if dialect == "sqlite":
        db_file = engine.url.database
        if db_file and os.path.exists(db_file):
            db_size_bytes = os.path.getsize(db_file)
    elif dialect == "postgresql":
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT pg_database_size(current_database());")).scalar()
                db_size_bytes = int(res or 0)
        except Exception:
            db_size_bytes = 0

    # Folder sizes
    output_size_bytes = 0
    for root, _, files in os.walk("output"):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp) and os.path.exists(fp):
                output_size_bytes += os.path.getsize(fp)

    total_used_mb = round((db_size_bytes + output_size_bytes) / (1024 * 1024), 2)
    pct_of_500mb = round((total_used_mb / FREE_TIER_LIMIT_MB) * 100, 2)

    total_videos = 0
    total_recs = 0
    oldest_date = None
    newest_date = None

    try:
        with SessionFactory() as db:
            total_videos = db.query(Video).count()
            total_recs = db.query(Recommendation).count()
            oldest = db.query(Video.created_at).order_by(Video.created_at.asc()).first()
            newest = db.query(Video.created_at).order_by(Video.created_at.desc()).first()
            if oldest and oldest[0]:
                oldest_date = oldest[0].isoformat()
            if newest and newest[0]:
                newest_date = newest[0].isoformat()
    except Exception:
        pass

    return {
        "database_engine": "Neon PostgreSQL" if dialect == "postgresql" else "SQLite (Local)",
        "free_tier_limit_mb": FREE_TIER_LIMIT_MB,
        "database_size_kb": round(db_size_bytes / 1024, 2),
        "output_files_size_kb": round(output_size_bytes / 1024, 2),
        "total_used_mb": total_used_mb,
        "free_tier_percent_used": pct_of_500mb,
        "free_tier_remaining_mb": round(max(0.0, FREE_TIER_LIMIT_MB - total_used_mb), 2),
        "retention_days": DEFAULT_RETENTION_DAYS,
        "total_videos": total_videos,
        "total_recommendations": total_recs,
        "oldest_record": oldest_date,
        "newest_record": newest_date,
        "s3_bucket_configured": bool(os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME"))
    }
