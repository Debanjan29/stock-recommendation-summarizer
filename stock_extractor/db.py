"""
Database module for YouTube Stock Extractor.
Supports Neon PostgreSQL in cloud environments and SQLite for local development.
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

Base = declarative_base()


class Video(Base):
    """Stores analyzed YouTube video metadata and full transcript."""
    __tablename__ = "videos"

    id = Column(String(32), primary_key=True)  # YouTube Video ID
    title = Column(String(500), nullable=False)
    channel = Column(String(255), nullable=True, default="Unknown Channel")
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    transcript_text = Column(Text, nullable=True)
    extraction_engine = Column(String(100), default="Gemini 2.5 Flash")
    total_recommendations = Column(Integer, default=0)
    buy_count = Column(Integer, default=0)
    sell_count = Column(Integer, default=0)
    hold_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    recommendations = relationship(
        "Recommendation", 
        back_populates="video", 
        cascade="all, delete-orphan",
        order_by="Recommendation.timestamp_seconds"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.id,
            "title": self.title,
            "channel": self.channel,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "extraction_engine": self.extraction_engine,
            "total_recommendations": self.total_recommendations,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "hold_count": self.hold_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "recommendations": [rec.to_dict() for rec in self.recommendations]
        }

    def get_transcript(self) -> str:
        """Return transparently decompressed transcript text."""
        from stock_extractor.storage import decompress_transcript
        return decompress_transcript(self.transcript_text)


class Recommendation(Base):
    """Stores individual stock recommendation extracted from a video."""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(50), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)
    sector = Column(String(100), default="Diversified / Other", index=True)
    analyst = Column(String(150), default="N/A")
    stop_loss = Column(String(100), default="N/A")
    target = Column(String(100), default="N/A")
    horizon = Column(String(100), default="N/A")
    source_quote = Column(Text, default="")
    timestamp_seconds = Column(Float, default=0.0)
    timestamp_formatted = Column(String(20), default="00:00")
    timestamp_url = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="recommendations")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "video_id": self.video_id,
            "ticker": self.ticker,
            "action": self.action,
            "sector": self.sector or "Diversified / Other",
            "analyst": self.analyst,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "horizon": self.horizon,
            "source_quote": self.source_quote,
            "timestamp_seconds": self.timestamp_seconds,
            "timestamp_formatted": self.timestamp_formatted,
            "timestamp_url": self.timestamp_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# Database Engine and Session Factory Configuration
def get_database_url() -> str:
    """Retrieve database URL from environment, fixing Render/Neon postgres:// prefix."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    return "sqlite:///./stock_app.db"


_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = get_database_url()
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(
            db_url, 
            connect_args=connect_args, 
            pool_pre_ping=True,
            echo=False
        )
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionFactory


def init_db():
    """Create all database tables if they do not exist, and ensure sector column exists."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # Lightweight migration check for sector column on existing SQLite/Postgres DBs
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            # Check if sector column exists in recommendations table
            if engine.dialect.name == "sqlite":
                result = conn.execute(text("PRAGMA table_info(recommendations);")).fetchall()
                col_names = [r[1] for r in result]
                if "sector" not in col_names:
                    conn.execute(text("ALTER TABLE recommendations ADD COLUMN sector VARCHAR(100) DEFAULT 'Diversified / Other';"))
                    conn.commit()
            elif engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS sector VARCHAR(100) DEFAULT 'Diversified / Other';"))
                conn.commit()
    except Exception:
        pass

    # Backfill missing/diversified sectors for existing records
    try:
        from stock_extractor.sectors import get_stock_sector
        SessionMaker = get_session_factory()
        with SessionMaker() as session:
            unresolved_recs = session.query(Recommendation).filter(
                (Recommendation.sector == None) | (Recommendation.sector == "Diversified / Other")
            ).all()
            updated = False
            for rec in unresolved_recs:
                resolved = get_stock_sector(rec.ticker)
                if resolved and resolved != "Diversified / Other":
                    rec.sector = resolved
                    updated = True
            if updated:
                session.commit()
    except Exception:
        pass

    # Storage auto-retention check (15 days) & transcript compression
    try:
        from stock_extractor.storage import prune_expired_records, compress_all_existing_transcripts
        prune_expired_records()
        compress_all_existing_transcripts()
    except Exception:
        pass


def get_db():
    """Dependency generator for FastAPI route handlers."""
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


def save_video_report(
    db: Session,
    video_id: str,
    metadata: Dict[str, Any],
    transcript_text: str,
    recommendations: List[Any],
    engine_name: str = "Gemini 2.5 Flash"
) -> Video:
    """Save or update a Video record with all recommendations in a single transaction."""
    from stock_extractor.storage import compress_transcript
    stored_transcript = compress_transcript(transcript_text)

    # Count actions
    buy_count = 0
    sell_count = 0
    hold_count = 0

    for r in recommendations:
        act = getattr(r, "action", "").upper() if hasattr(r, "action") else r.get("action", "").upper()
        if any(b in act for b in ["BUY", "ACCUMULATE"]):
            buy_count += 1
        elif any(s in act for s in ["SELL", "AVOID"]):
            sell_count += 1
        else:
            hold_count += 1

    # Check if video already exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        # Delete old recommendations and update metadata
        video.title = metadata.get("title", video.title)
        video.channel = metadata.get("channel", video.channel)
        video.video_url = metadata.get("video_url", video.video_url)
        video.thumbnail_url = metadata.get("thumbnail_url", video.thumbnail_url)
        video.transcript_text = stored_transcript
        video.extraction_engine = engine_name
        video.total_recommendations = len(recommendations)
        video.buy_count = buy_count
        video.sell_count = sell_count
        video.hold_count = hold_count
        video.created_at = datetime.utcnow()
        video.recommendations.clear()
    else:
        video = Video(
            id=video_id,
            title=metadata.get("title", f"YouTube Video ({video_id})"),
            channel=metadata.get("channel", "Unknown Channel"),
            video_url=metadata.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
            thumbnail_url=metadata.get("thumbnail_url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
            transcript_text=stored_transcript,
            extraction_engine=engine_name,
            total_recommendations=len(recommendations),
            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            created_at=datetime.utcnow()
        )
        db.add(video)

    db.flush()

    for r in recommendations:
        if hasattr(r, "ticker"):
            ticker = r.ticker
            action = r.action
            sector = getattr(r, "sector", None)
            analyst = getattr(r, "analyst", "N/A")
            stop_loss = getattr(r, "stop_loss", "N/A")
            target = getattr(r, "target", "N/A")
            horizon = getattr(r, "horizon", "N/A")
            source_quote = getattr(r, "source_quote", "")
            timestamp_seconds = getattr(r, "timestamp_seconds", 0.0)
            timestamp_formatted = getattr(r, "timestamp_formatted", "00:00")
            timestamp_url = getattr(r, "timestamp_url", "")
        else:
            ticker = r.get("ticker", "")
            action = r.get("action", "WATCH")
            sector = r.get("sector")
            analyst = r.get("analyst", "N/A")
            stop_loss = r.get("stop_loss", "N/A")
            target = r.get("target", "N/A")
            horizon = r.get("horizon", "N/A")
            source_quote = r.get("source_quote", "")
            timestamp_seconds = float(r.get("timestamp_seconds", 0.0))
            timestamp_formatted = r.get("timestamp_formatted", "00:00")
            timestamp_url = r.get("timestamp_url", "")

        if not sector or sector == "Diversified / Other":
            try:
                from stock_extractor.sectors import get_stock_sector
                sector = get_stock_sector(ticker)
            except Exception:
                sector = "Diversified / Other"

        rec_row = Recommendation(
            video_id=video.id,
            ticker=ticker,
            action=action,
            sector=sector,
            analyst=analyst,
            stop_loss=stop_loss,
            target=target,
            horizon=horizon,
            source_quote=source_quote,
            timestamp_seconds=timestamp_seconds,
            timestamp_formatted=timestamp_formatted,
            timestamp_url=timestamp_url,
            created_at=datetime.utcnow()
        )
        db.add(rec_row)

    db.commit()
    db.refresh(video)
    return video


def get_video_report(db: Session, video_id: str) -> Optional[Video]:
    """Retrieve full video record and its recommendations by video ID."""
    return db.query(Video).filter(Video.id == video_id).first()


def get_recent_videos(db: Session, limit: int = 20, offset: int = 0) -> List[Video]:
    """Retrieve most recently analyzed videos for the gallery feed."""
    return (
        db.query(Video)
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def search_stock_recommendations(db: Session, ticker: str) -> List[Recommendation]:
    """Find all recommendations across all videos for a given stock ticker."""
    return (
        db.query(Recommendation)
        .filter(Recommendation.ticker == ticker.upper())
        .order_by(Recommendation.created_at.desc())
        .all()
    )
