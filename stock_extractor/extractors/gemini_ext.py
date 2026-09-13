"""
Google Gemini LLM Stock Extractor using REST API.
Supports single-shot full transcript analysis with automated model deprecation fallback.
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import (
    EXTRACTION_SYSTEM_PROMPT, parse_llm_response
)


class GeminiExtractor(BaseExtractor):
    """Stock extractor using Google Gemini API with smart model fallback."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-3.6-flash"
        self.name = f"Google Gemini ({self.model})"

        if not self.api_key:
            raise ValueError(
                "Gemini API key is missing. Set GEMINI_API_KEY environment variable or provide your API key in the UI."
            )

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        """Extract stock recommendations from transcript chunks."""
        full_text_lines = []
        for c in chunks:
            start_sec = c.get("start", 0.0)
            mins = int(start_sec // 60)
            secs = int(start_sec % 60)
            text = c.get("text", "").strip()
            if text:
                full_text_lines.append(f"[{mins:02d}:{secs:02d}] {text}")

        full_text = "\n".join(full_text_lines)
        return self.extract_from_text(full_text, video_id)

    def extract_from_text(self, transcript_text: str, video_id: str) -> List[StockRecommendation]:
        """
        Analyze the full translated transcript with automatic fallback across models
        (e.g., gemini-3.6-flash, gemini-2.0-flash, gemini-1.5-flash) if Google reports a 404/deprecation.
        """
        # Candidate models to try in order of preference (verified working with Google API)
        models_to_try = [self.model, "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"]
        # Deduplicate while preserving order
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        prompt = (
            f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
            f"Video ID: {video_id}\n\n"
            f"Full Translated Video Transcript:\n\"\"\"\n{transcript_text[:65000]}\n\"\"\""
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        json_data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        last_error = None

        for current_model in unique_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={self.api_key}"
            try:
                req = urllib.request.Request(url, data=json_data, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    candidates = result.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        recs = parse_llm_response(content, video_id)
                        if recs:
                            self.model = current_model
                            self.name = f"Google Gemini ({self.model})"
                            return recs
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="replace")
                last_error = f"Gemini API Error ({he.code}): {err_body}"

                # Check if error message explicitly advises a new model (e.g., 'use models/gemini-3.6-flash')
                suggested_match = re.search(r'use models/([a-zA-Z0-9.-]+)', err_body)
                if suggested_match:
                    suggested_model = suggested_match.group(1)
                    if suggested_model not in unique_models:
                        unique_models.append(suggested_model)

                # If 404 (model retired/not found), continue to next candidate model
                if he.code == 404:
                    continue
                else:
                    raise RuntimeError(last_error)
            except Exception as e:
                last_error = str(e)
                continue

        if last_error:
            raise RuntimeError(last_error)

        return []
