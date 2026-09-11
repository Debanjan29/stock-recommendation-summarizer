"""
Antigravity AGY AI CLI Extractor Module.
Executes non-interactive AGY AI CLI execution or direct LLM analysis to generate structured Indian stock recommendations.
"""

import os
import sys
import glob
import shutil
import subprocess
import re
from typing import List, Dict, Any, Optional

from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.extractors.llm_base import EXTRACTION_SYSTEM_PROMPT, parse_llm_response, parse_llm_markdown_table_response

class AGYExtractor(BaseExtractor):
    """AGY AI CLI Extractor that captures and parses LLM responses directly from transcripts."""
    
    name = "Antigravity AGY AI CLI"

    def __init__(self, model: Optional[str] = None):
        self.model = model or "gemini-3.8-flash-high"
        self.name = f"Antigravity AGY AI CLI ({self.model})"
        self.agy_bin = shutil.which("agy") or shutil.which("agy.cmd") or shutil.which("agy.exe")

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        """
        Analyze transcript using AGY AI CLI non-interactive execution, direct LLM engines, or pre-analyzed reports.
        """
        transcript_file = os.path.join("output", "transcripts", f"translated_transcript_{video_id}.txt")
        
        full_text = ""
        if os.path.exists(transcript_file):
            try:
                with open(transcript_file, "r", encoding="utf-8") as tf:
                    full_text = tf.read()
            except Exception:
                pass

        if not full_text and chunks:
            full_text = "\n".join([f"[{c.get('start', 0.0):.1f}s] {c.get('text', '')}" for c in chunks])

        # -------------------------------------------------------------
        # Tier 1: Check for existing high-fidelity analysis report for this video
        # -------------------------------------------------------------
        reports_dir = os.path.join("output", "reports")
        if os.path.exists(reports_dir):
            for r_file in glob.glob(os.path.join(reports_dir, "*.md")):
                try:
                    with open(r_file, "r", encoding="utf-8", errors="ignore") as rf:
                        content = rf.read()
                        if video_id in content:
                            from stock_extractor.transliteration import has_devanagari
                            # Do not reuse old reports containing pure Devanagari Hindi
                            if has_devanagari(content):
                                continue
                            recs = parse_llm_markdown_table_response(content, video_id)
                            if recs and len(recs) >= 2:
                                return recs
                except Exception:
                    pass

        # -------------------------------------------------------------
        # Tier 2: Try invoking AGY CLI non-interactively ('agy --print')
        # -------------------------------------------------------------
        if self.agy_bin and full_text:
            prompt = (
                f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
                f"Video ID: {video_id}\n\n"
                f"Full Translated Video Transcript:\n\"\"\"\n{full_text[:45000]}\n\"\"\""
            )
            cmd = [
                self.agy_bin,
                "--model", self.model,
                "-p", prompt,
                "--dangerously-skip-permissions"
            ]
            try:
                result = subprocess.run(
                    cmd, 
                    stdin=subprocess.DEVNULL,
                    capture_output=True, 
                    text=True, 
                    timeout=180, 
                    encoding="utf-8",
                    errors="replace"
                )
                if result.returncode == 0 and result.stdout:
                    recs = parse_llm_response(result.stdout, video_id)
                    if recs:
                        return recs
                elif result.returncode != 0:
                    print(f"[AGY CLI] Warning: agy exited with code {result.returncode}. Stderr: {result.stderr.strip()[:200]}")
            except subprocess.TimeoutExpired:
                print(f"[AGY CLI] Warning: agy execution timed out after 180 seconds.")
            except Exception as e:
                print(f"[AGY CLI] Warning: agy execution failed: {e}")

        # -------------------------------------------------------------
        # Tier 3: Check for configured LLM REST APIs (Gemini, OpenAI, etc.)
        # -------------------------------------------------------------
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from stock_extractor.extractors.gemini_ext import GeminiExtractor
                gem_ext = GeminiExtractor(api_key=gemini_key)
                recs = gem_ext.extract(chunks, video_id)
                if recs:
                    return recs
            except Exception:
                pass

        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from stock_extractor.extractors.openai_ext import OpenAIExtractor
                oai_ext = OpenAIExtractor(api_key=openai_key)
                recs = oai_ext.extract(chunks, video_id)
                if recs:
                    return recs
            except Exception:
                pass

        # -------------------------------------------------------------
        # Strict Policy: "LLM or nothing"
        # -------------------------------------------------------------
        raise RuntimeError(
            f"LLM Extraction failed for video '{video_id}'. No active LLM provider (AGY AI CLI, Gemini, OpenAI, Claude, or Ollama) "
            f"returned valid stock recommendations. Heuristic guessing is strictly disabled per project requirements ('LLM or nothing')."
        )

