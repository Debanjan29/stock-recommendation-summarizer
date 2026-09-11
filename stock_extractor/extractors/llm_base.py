"""
Base class and prompt helpers for LLM-based stock extractors targeting Indian Stock Market.
"""

import json
import re
from typing import List, Dict, Any, Optional
from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.utils import format_timestamp, make_timestamp_url
from stock_extractor.indian_market import indian_market_manager
from stock_extractor.transliteration import ensure_no_pure_hindi

EXTRACTION_SYSTEM_PROMPT = """You are an expert Indian financial market analyst assistant.
Your task is to analyze YouTube video transcript snippets and extract EVERY stock recommendation or financial analysis mentioned ONLY for Indian Stock Market (NSE / BSE equities and Indian Indices like NIFTY 50, BANKNIFTY, SENSEX, RELIANCE, TATAMOTORS, HDFCBANK, SBIN, ZOMATO, etc.).

STRICT REQUIREMENT 1: Focus ONLY on Indian stock market stocks and indices. Do NOT include foreign/US stocks.

CRITICAL LANGUAGE REQUIREMENT (NO PURE HINDI / NO DEVANAGARI SCRIPT):
- NO PURE HINDI IN DEVANAGARI SCRIPT: Under NO circumstance should any output or report field (source_quote, analyst, horizon, rationale, etc.) be in pure Devanagari Hindi (e.g., no हिंदी script).
- Allowed languages:
  1. English (e.g., clear English translation or summary).
  2. Hinglish (Hindi spoken in Roman/English alphabet, e.g. "So far 7:30 baje tak SGX Nifty 0.50% down tha. Large cap mein HDFC Bank aur Reliance safe lag rahe hain").
  3. Both English and Hinglish (e.g., "Hinglish quote / English translation").
- If the speaker spoke in Hindi in the video, transcribe it into Hinglish (Roman English letters) or translate it into English, or both. NEVER output pure Hindi in Devanagari script.

For each Indian stock mentioned, extract:
- ticker: Official NSE/BSE stock ticker symbol or index name (e.g., RELIANCE, TATAMOTORS, HDFCBANK, SBIN, NIFTY 50, SENSEX).
- action: One of [BUY, SELL, HOLD, ACCUMULATE, AVOID, WATCH].
- analyst: Name of the individual analyst/expert (e.g., 'Varun', 'Lokesh Settia', 'Anil Singhvi', 'Dipan Mehta') or institutional fund house/brokerage (e.g., 'Jefferies', 'JPMorgan', 'Morgan Stanley', 'Nomura', 'CLSA', 'Motilal Oswal') who made or is quoted making the recommendation, otherwise 'N/A'.
- stop_loss: Stop-loss level or price in INR/Rs/₹ if mentioned (e.g., "Rs 1420", "1400", "5% below entry"), otherwise "N/A".
- target: Target price or range in INR/Rs/₹ (e.g., "Rs 1800", "1800-1850", "+25%"), otherwise "N/A".
- horizon: Time horizon for the trade/investment (e.g., "Short-term (1-2 weeks)", "Long-term (1-3 yrs)", "Intraday"), otherwise "N/A".
- source_quote: Direct source quote or verbatim context sentence spoken in the video in English, Hinglish (Roman alphabet), or bilingual English+Hinglish. NEVER in Devanagari Hindi.
- timestamp_seconds: Approximate start timestamp in seconds from the snippet.

Return ONLY a valid JSON array of objects. Do not include markdown formatting or extra commentary.
Example:
[
  {
    "ticker": "TATAMOTORS",
    "action": "BUY",
    "analyst": "Jefferies",
    "stop_loss": "Rs 950",
    "target": "Rs 1100",
    "horizon": "Short-term",
    "source_quote": "Tata Motors looks strong, Jefferies maintains buy with stop loss at 950 and target 1100.",
    "timestamp_seconds": 125.0
  }
]
"""

def parse_llm_json_response(
    raw_response: str, 
    video_id: str, 
    fallback_timestamp: float = 0.0
) -> List[StockRecommendation]:
    """Parse JSON array output from LLM and convert to StockRecommendation objects with Indian stock validation."""
    recommendations = []
    
    # Strip markdown codeblocks if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except Exception:
        data = None
        # Try extracting from ```json ... ``` codeblock
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_response)
        if m:
            try:
                data = json.loads(m.group(1).strip())
            except Exception:
                pass
        # Try extracting JSON array [ ... ] directly
        if data is None:
            m = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', raw_response)
            if m:
                try:
                    data = json.loads(m.group(1).strip())
                except Exception:
                    pass

    try:
        if isinstance(data, dict) and "recommendations" in data:
            data = data["recommendations"]
            
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                raw_ticker = str(item.get("ticker", "")).strip()
                action = str(item.get("action", "WATCH")).strip().upper()
                if not raw_ticker or raw_ticker.upper() == "N/A":
                    continue
                    
                # Validate & resolve to Indian market ticker
                resolved = indian_market_manager.resolve_ticker(raw_ticker)
                ticker = resolved[0] if resolved else raw_ticker.upper()
                
                # Enforce strict Indian market filtering
                if not indian_market_manager.is_indian_stock(ticker, raw_ticker):
                    continue

                t_sec = float(item.get("timestamp_seconds", fallback_timestamp))
                raw_analyst = str(item.get("analyst", item.get("firm", item.get("fund_house", "N/A")))).strip()
                analyst = "N/A" if not raw_analyst or raw_analyst.upper() in ["NONE", "NULL", ""] else raw_analyst
                
                rec = StockRecommendation(
                    ticker=ensure_no_pure_hindi(ticker),
                    action=ensure_no_pure_hindi(action),
                    analyst=ensure_no_pure_hindi(analyst),
                    stop_loss=ensure_no_pure_hindi(str(item.get("stop_loss", "N/A")).strip()),
                    target=ensure_no_pure_hindi(str(item.get("target", "N/A")).strip()),
                    horizon=ensure_no_pure_hindi(str(item.get("horizon", "N/A")).strip()),
                    source_quote=ensure_no_pure_hindi(str(item.get("source_quote", "")).strip()),
                    timestamp_seconds=t_sec,
                    timestamp_formatted=format_timestamp(t_sec),
                    timestamp_url=make_timestamp_url(video_id, t_sec)
                )
                recommendations.append(rec)
    except Exception:
        pass

    return recommendations

def parse_llm_markdown_table_response(
    raw_response: str, 
    video_id: str, 
    fallback_timestamp: float = 0.0
) -> List[StockRecommendation]:
    """Parse Markdown table output from LLM if response was formatted as table instead of raw JSON."""
    recommendations = []
    seen_tickers = set()
    lines = raw_response.splitlines()

    col_map = {
        "ticker": 0,
        "action": 1,
        "analyst": -1,
        "sl": -1,
        "target": -1,
        "horizon": -1,
        "timestamp": -1,
        "quote": -1
    }
    header_detected = False

    for line in lines:
        line_clean = line.strip()
        if not line_clean.startswith("|") or "---" in line_clean:
            continue
        parts = [p.strip() for p in line_clean.strip("|").split("|")]
        if len(parts) >= 4:
            clean_headers = [re.sub(r'[*`\[\]]', '', p).strip().lower() for p in parts]
            if any(h in ["ticker", "stock", "stock name", "company", "symbol", "name"] for h in clean_headers[:2]):
                for idx, h in enumerate(clean_headers):
                    if any(k in h for k in ["analyst", "fund", "house", "broker", "firm", "expert", "recommender"]):
                        col_map["analyst"] = idx
                    elif any(k in h for k in ["stop", "sl", "stop-loss"]):
                        col_map["sl"] = idx
                    elif any(k in h for k in ["target", "tgt", "tp"]):
                        col_map["target"] = idx
                    elif any(k in h for k in ["horizon", "timeframe", "term"]):
                        col_map["horizon"] = idx
                    elif any(k in h for k in ["timestamp", "time"]):
                        col_map["timestamp"] = idx
                    elif any(k in h for k in ["quote", "source", "context", "rationale"]):
                        col_map["quote"] = idx
                header_detected = True
                continue

            raw_ticker = re.sub(r'[*`\[\]]', '', parts[0]).strip()
            if not raw_ticker or raw_ticker.upper() == "N/A":
                continue

            action = "WATCH"
            analyst = "N/A"
            stop_loss = "N/A"
            target = "N/A"
            horizon = "N/A"
            ts_col = ""
            quote = ""

            if header_detected:
                action = re.sub(r'[*`\[\]]', '', parts[col_map["action"]]).strip().upper() if col_map["action"] < len(parts) else "WATCH"
                if col_map["analyst"] != -1 and col_map["analyst"] < len(parts):
                    analyst = re.sub(r'[*`\[\]]', '', parts[col_map["analyst"]]).strip()
                if col_map["sl"] != -1 and col_map["sl"] < len(parts):
                    stop_loss = re.sub(r'[*`\[\]]', '', parts[col_map["sl"]]).strip()
                if col_map["target"] != -1 and col_map["target"] < len(parts):
                    target = re.sub(r'[*`\[\]]', '', parts[col_map["target"]]).strip()
                if col_map["horizon"] != -1 and col_map["horizon"] < len(parts):
                    horizon = re.sub(r'[*`\[\]]', '', parts[col_map["horizon"]]).strip()
                if col_map["timestamp"] != -1 and col_map["timestamp"] < len(parts):
                    ts_col = parts[col_map["timestamp"]].strip()
                if col_map["quote"] != -1 and col_map["quote"] < len(parts):
                    quote = parts[col_map["quote"]].strip()
            else:
                action = re.sub(r'[*`\[\]]', '', parts[1]).strip().upper() if len(parts) > 1 else "WATCH"
                if len(parts) >= 8:
                    analyst = re.sub(r'[*`\[\]]', '', parts[2]).strip()
                    stop_loss = re.sub(r'[*`\[\]]', '', parts[3]).strip()
                    target = re.sub(r'[*`\[\]]', '', parts[4]).strip()
                    horizon = re.sub(r'[*`\[\]]', '', parts[5]).strip()
                    ts_col = parts[6].strip()
                    quote = parts[7].strip()
                elif len(parts) == 7:
                    stop_loss = re.sub(r'[*`\[\]]', '', parts[2]).strip()
                    target = re.sub(r'[*`\[\]]', '', parts[3]).strip()
                    horizon = re.sub(r'[*`\[\]]', '', parts[4]).strip()
                    ts_col = parts[5].strip()
                    quote = parts[6].strip()
                elif len(parts) == 6:
                    stop_loss = re.sub(r'[*`\[\]]', '', parts[2]).strip()
                    target = re.sub(r'[*`\[\]]', '', parts[3]).strip()
                    horizon = re.sub(r'[*`\[\]]', '', parts[4]).strip()
                    if re.search(r'\[?(\d{1,2}):(\d{2})\]?', parts[5]):
                        ts_col = parts[5].strip()
                    else:
                        quote = parts[5].strip()

            # Check if this row is from an auxiliary/matrix table rather than the recommendation table
            if not any(va in action for va in ["BUY", "SELL", "HOLD", "WATCH", "TRACK", "BENCHMARK", "ACCUMULATE", "AVOID"]):
                continue

            if not analyst or analyst.upper() in ["NONE", "NULL", "-", ""]:
                analyst = "N/A"

            # Clean quote of surrounding quotes or links
            quote = re.sub(r'^["\']|["\']$', '', quote).strip()

            # Extract timestamp from row if present [MM:SS]
            ts_sec = fallback_timestamp
            ts_search_target = ts_col if ts_col else line_clean
            ts_match = re.search(r'\[?(\d{1,2}):(\d{2})\]?', ts_search_target)
            if ts_match:
                ts_sec = float(int(ts_match.group(1)) * 60 + int(ts_match.group(2)))

            resolved = indian_market_manager.resolve_ticker(raw_ticker)
            ticker = resolved[0] if resolved else raw_ticker.upper()

            if ticker in seen_tickers:
                continue

            if not indian_market_manager.is_indian_stock(ticker, raw_ticker):
                continue

            seen_tickers.add(ticker)

            rec = StockRecommendation(
                ticker=ensure_no_pure_hindi(ticker),
                action=ensure_no_pure_hindi(action),
                analyst=ensure_no_pure_hindi(analyst),
                stop_loss=ensure_no_pure_hindi(stop_loss),
                target=ensure_no_pure_hindi(target),
                horizon=ensure_no_pure_hindi(horizon),
                source_quote=ensure_no_pure_hindi(quote[:250]),
                timestamp_seconds=ts_sec,
                timestamp_formatted=format_timestamp(ts_sec),
                timestamp_url=make_timestamp_url(video_id, ts_sec)
            )
            recommendations.append(rec)
    return recommendations

def parse_llm_response(
    raw_response: str, 
    video_id: str, 
    fallback_timestamp: float = 0.0
) -> List[StockRecommendation]:
    """Universal LLM response parser: handles JSON array, JSON object, and Markdown tables."""
    if not raw_response or not raw_response.strip():
        return []
    recs = parse_llm_json_response(raw_response, video_id, fallback_timestamp)
    if not recs:
        recs = parse_llm_markdown_table_response(raw_response, video_id, fallback_timestamp)
    return recs
