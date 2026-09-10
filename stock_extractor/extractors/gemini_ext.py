"""
Google Gemini LLM Stock Extractor using REST API.
"""

import os
import json
import urllib.request
from typing import List, Dict, Any, Optional

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import EXTRACTION_SYSTEM_PROMPT, parse_llm_json_response

class GeminiExtractor(BaseExtractor):
    """Stock extractor using Google Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.name = f"Gemini ({self.model})"
        
        if not self.api_key:
            raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY environment variable or pass --api-key.")

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        recommendations = []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        for chunk in chunks:
            text = chunk.get('text', '')
            start_time = chunk.get('start', 0.0)
            
            prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nTranscript Chunk (Start Time: {start_time:.1f}s):\n\"\"\"\n{text}\n\"\"\""
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            
            try:
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                    recs = parse_llm_json_response(content, video_id, fallback_timestamp=start_time)
                    recommendations.extend(recs)
            except Exception as e:
                pass

        return recommendations
