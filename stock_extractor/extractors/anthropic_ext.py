"""
Anthropic Claude Stock Extractor using REST API.
"""

import os
import json
import urllib.request
from typing import List, Dict, Any, Optional

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import EXTRACTION_SYSTEM_PROMPT, parse_llm_json_response

class AnthropicExtractor(BaseExtractor):
    """Stock extractor using Anthropic Claude API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.name = f"Anthropic ({self.model})"
        
        if not self.api_key:
            raise ValueError("Anthropic API key is missing. Set ANTHROPIC_API_KEY environment variable or pass --api-key.")

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        recommendations = []
        url = "https://api.anthropic.com/v1/messages"
        
        for chunk in chunks:
            text = chunk.get('text', '')
            start_time = chunk.get('start', 0.0)
            
            user_prompt = f"Transcript Chunk (Start Time: {start_time:.1f}s):\n\"\"\"\n{text}\n\"\"\""
            
            payload = {
                "model": self.model,
                "max_tokens": 2048,
                "system": EXTRACTION_SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            try:
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    content = result["content"][0]["text"]
                    recs = parse_llm_json_response(content, video_id, fallback_timestamp=start_time)
                    recommendations.extend(recs)
            except Exception as e:
                pass

        return recommendations
