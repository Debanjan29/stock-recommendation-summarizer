"""
OpenAI LLM Stock Extractor using REST API.
"""

import os
import json
import urllib.request
from typing import List, Dict, Any, Optional

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import EXTRACTION_SYSTEM_PROMPT, parse_llm_json_response

class OpenAIExtractor(BaseExtractor):
    """Stock extractor using OpenAI Chat Completions API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.name = f"OpenAI ({self.model})"
        
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set OPENAI_API_KEY environment variable or pass --api-key.")

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        recommendations = []
        url = "https://api.openai.com/v1/chat/completions"
        
        for chunk in chunks:
            text = chunk.get('text', '')
            start_time = chunk.get('start', 0.0)
            
            user_prompt = f"Transcript Chunk (Start Time: {start_time:.1f}s):\n\"\"\"\n{text}\n\"\"\""
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"} if "gpt-4" in self.model or "gpt-3.5" in self.model else None
            }
            
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    content = result["choices"][0]["message"]["content"]
                    recs = parse_llm_json_response(content, video_id, fallback_timestamp=start_time)
                    recommendations.extend(recs)
            except Exception as e:
                # Log or handle error gracefully per chunk
                pass

        return recommendations
