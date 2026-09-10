"""
Extractor package initialization and factory function.
"""

import os
from typing import Optional

from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.heuristic import HeuristicExtractor
from stock_extractor.extractors.agy_ext import AGYExtractor
from stock_extractor.extractors.openai_ext import OpenAIExtractor
from stock_extractor.extractors.gemini_ext import GeminiExtractor
from stock_extractor.extractors.anthropic_ext import AnthropicExtractor
from stock_extractor.extractors.ollama_ext import OllamaExtractor

def get_extractor(
    method: str = "auto",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    ollama_url: Optional[str] = None
) -> BaseExtractor:
    """
    Factory function to get appropriate extractor engine based on method or available API keys.
    """
    method = (method or "auto").lower()

    if method == "agy":
        return AGYExtractor(model=model)
    elif method == "openai":
        return OpenAIExtractor(api_key=api_key, model=model or "gpt-4o-mini")
    elif method == "gemini":
        return GeminiExtractor(api_key=api_key, model=model or "gemini-2.5-flash")
    elif method == "anthropic":
        return AnthropicExtractor(api_key=api_key, model=model or "claude-3-5-sonnet-20241022")
    elif method == "ollama":
        return OllamaExtractor(base_url=ollama_url or "http://localhost:11434/v1", model=model or "llama3")
    elif method == "heuristic":
        return HeuristicExtractor()
    elif method == "auto":
        # Default AGY AI CLI Extractor
        return AGYExtractor(model=model)
    else:
        raise ValueError(f"Unknown extraction method: '{method}'. Choose from 'auto', 'agy', 'heuristic', 'openai', 'gemini', 'anthropic', 'ollama'.")
