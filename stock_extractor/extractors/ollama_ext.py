"""
Ollama / Local OpenAI-Compatible LLM Stock Extractor using REST API.
"""

import json
import urllib.request
from typing import List, Dict, Any, Optional

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import EXTRACTION_SYSTEM_PROMPT, parse_llm_json_response

class OllamaExtractor(BaseExtractor):
    """Stock extractor using local Ollama or OpenAI-compatible endpoint (e.g. LM Studio, vLLM)."""
    
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"Local LLM ({self.model})"

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        recommendations = []
        url = f"{self.base_url}/chat/completions"
        
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
                "temperature": 0.1
            }
            
            try:
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    content = result["choices"][0]["message"]["content"]
                    recs = parse_llm_json_response(content, video_id, fallback_timestamp=start_time)
                    recommendations.extend(recs)
            except Exception as e:
                pass

        return recommendations
