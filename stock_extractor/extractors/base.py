"""
Base extractor interface for YouTube Stock Recommendation Extractor.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from stock_extractor.models import StockRecommendation

class BaseExtractor(ABC):
    """Abstract base class for all stock recommendation extraction engines."""
    
    name: str = "Base Extractor"
    
    @abstractmethod
    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        """
        Extract stock recommendations from transcript chunks.
        
        Args:
            chunks: List of chunk dicts containing 'text', 'start', 'duration'
            video_id: YouTube video ID for creating timestamp URLs
            
        Returns:
            List of StockRecommendation objects
        """
        pass
