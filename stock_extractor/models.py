"""
Data models for YouTube Stock Recommendation Extractor.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class StockRecommendation:
    """Represents a single stock recommendation extracted from video content."""
    ticker: str
    action: str  # BUY, SELL, HOLD, ACCUMULATE, AVOID, WATCH, TARGET ONLY
    analyst: str = "N/A"  # Individual analyst (e.g. Varun, Lokesh Settia) or Fund House (e.g. Jefferies, JPM)
    stop_loss: str = "N/A"
    target: str = "N/A"
    horizon: str = "N/A"
    source_quote: str = ""
    timestamp_seconds: float = 0.0
    timestamp_formatted: str = "00:00"
    timestamp_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class VideoReport:
    """Represents the full report for a YouTube video."""
    video_id: str
    video_url: str
    title: str = "YouTube Video"
    channel: str = "Unknown Channel"
    thumbnail_url: str = ""
    extraction_method: str = "Heuristic"
    timestamp_generated: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendations: List[StockRecommendation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "video_url": self.video_url,
            "title": self.title,
            "channel": self.channel,
            "thumbnail_url": self.thumbnail_url,
            "extraction_method": self.extraction_method,
            "timestamp_generated": self.timestamp_generated,
            "total_recommendations": len(self.recommendations),
            "recommendations": [rec.to_dict() for rec in self.recommendations]
        }
