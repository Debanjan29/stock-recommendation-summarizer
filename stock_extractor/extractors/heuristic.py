"""
Strict & Intelligent Heuristic Stock Extractor for Indian Stock Market.
Requires genuine recommendation signals and prioritizes exact SL, Target, and Horizon parameter extraction.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from stock_extractor.models import StockRecommendation
from stock_extractor.extractors.base import BaseExtractor
from stock_extractor.utils import format_timestamp, make_timestamp_url
from stock_extractor.indian_market import indian_market_manager

class HeuristicExtractor(BaseExtractor):
    """Intelligent Heuristic Extractor prioritizing SL, Target, Horizon, and eliminating noise."""
    
    name = "Heuristic NLP (Indian Market)"
    
    def __init__(self):
        # Strict recommendation triggers to avoid false positives on conversational phrases
        self.buy_triggers = re.compile(
            r'\b(buy\b|buying\b|bullish\s+on\b|accumulate\b|accumulating\b|entry\s+(?:at|near)\b|go\s+long\b|add\s+to\s+portfolio\b|rating\s+of\s+(?:5|five)\b|highest\s+rating\b|top\s+pick\b|buy\s+candidate\b|strong\s+buy\b)', 
            re.I
        )
        self.sell_triggers = re.compile(
            r'\b(sell\s+(?:this|stock|here)?\b|selling\s+off\b|exit\s+position\b|bearish\s+on\b|book\s+profit\b|take\s+profit\b|go\s+short\b|avoid\s+(?:this|buying)\b|do\s+not\s+buy\b)', 
            re.I
        )
        self.hold_triggers = re.compile(r'\b(hold\s+this\b|stay\s+invested\b|maintain\s+position\b|keep\s+holding\b)\b', re.I)
        self.watch_triggers = re.compile(r'\b(watch\b|watching\b|keep\s+on\s+radar\b|keep\s+an\s+eye\b|track\s+(?:this|closely)?\b|tracking\b|study\s+this\b|rating\s+of\s+(?:3|4|three|four)\b)', re.I)
        
        # Stop loss patterns
        self.sl_patterns = [
            re.compile(r'(?:stop\s*loss|sl|stop\s*level|risk\s*below|exit\s*below|support\s*at)\s*(?:is|at|of|=|:|\s+)?\s*([₹|Rs\.?|INR]?\s*\d+(?:\.\d+)?%?)', re.I),
            re.compile(r'(?:keep\s+a\s+|with\s+a\s+)?stop\s*loss\s*(?:of|at|around)?\s*([₹|Rs\.?|INR]?\s*\d+(?:\.\d+)?%?)', re.I),
            re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:rs|rupees|inr|₹)?\s*(?:stop\s*loss|sl)\b', re.I)
        ]
        
        # Target patterns
        self.tp_patterns = [
            re.compile(r'(?:target|price\s*target|tp|upside\s*of|heading\s*to|can\s*reach|looking\s*for|upside\s*potential)\s*(?:is|at|of|=|:|\s+)?\s*([₹|Rs\.?|INR]?\s*\d+(?:\.\d+)?(?:\s*(?:to|-)\s*[₹|Rs\.?|INR]?\s*\d+(?:\.\d+)?)?%?)', re.I),
            re.compile(r'(?:1st|first|2nd|second|next|final)\s*target\s*(?:is|of|at)?\s*([₹|Rs\.?|INR]?\s*\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?%?)', re.I),
            re.compile(r'\b(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s*(?:rs|rupees|inr|₹)?\s*(?:target|tp)\b', re.I)
        ]
        
        # Time horizon patterns (avoid bare 'today' to prevent conversational False Positives)
        self.horizon_patterns = [
            (re.compile(r'\b(intraday|day\s*trade|same\s*day)\b', re.I), "Intraday"),
            (re.compile(r'\b(short\s*term|swing|1-2\s*weeks|few\s*days|couple of weeks)\b', re.I), "Short-term (1-2 weeks)"),
            (re.compile(r'\b(medium\s*term|3-6\s*months|1-3\s*months|positional|few months)\b', re.I), "Medium-term (1-6 months)"),
            (re.compile(r'\b(long\s*term|1-3\s*years|investment|investing|multibagger|years|long haul|2-3\s*years|3 years)\b', re.I), "Long-term (1+ years)")
        ]

    def extract(self, chunks: List[Dict[str, Any]], video_id: str) -> List[StockRecommendation]:
        recommendations: List[StockRecommendation] = []
        seen_tickers = set()

        for chunk in chunks:
            text = chunk.get('text', '')
            chunk_start = chunk.get('start', 0.0)
            snippets = chunk.get('snippets', [])

            # Detect valid Indian stock mentions
            stock_mentions = self._detect_stocks(text)
            if not stock_mentions:
                continue

            sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if len(s.strip()) > 3]

            for ticker, company_alias in stock_mentions:
                if ticker in seen_tickers:
                    continue

                # Locate specific sentence containing this stock mention
                matching_sentence = text[:200]
                best_snippet_time = chunk_start
                stock_sentences = []

                for s_idx, sentence in enumerate(sentences):
                    if re.search(r'\b' + re.escape(company_alias) + r'\b', sentence, re.I) or \
                       re.search(r'\b' + re.escape(ticker) + r'\b', sentence, re.I):
                        matching_sentence = sentence
                        # Context window: current sentence + next sentence
                        context_window = sentence
                        if s_idx + 1 < len(sentences):
                            context_window += ". " + sentences[s_idx + 1]
                        stock_sentences.append(context_window)

                        for snip in snippets:
                            if company_alias.lower() in snip.get('text', '').lower() or ticker.lower() in snip.get('text', '').lower():
                                best_snippet_time = snip.get('start', chunk_start)
                                break
                        break

                scoped_text = " ".join(stock_sentences) if stock_sentences else text

                # Extract action, SL, Target scoped to the stock's own sentence context to prevent cross-stock contamination
                action = self._detect_action(scoped_text)
                analyst = self._extract_analyst(scoped_text)
                stop_loss = self._extract_stop_loss(scoped_text)
                target = self._extract_target(scoped_text)
                horizon = self._extract_horizon(scoped_text)

                unique_tickers = {m[0] for m in stock_mentions}

                # Fallback to chunk text if single distinct ticker in chunk
                if len(unique_tickers) == 1:
                    if not action:
                        action = self._detect_action(text)
                    if analyst == "N/A":
                        analyst = self._extract_analyst(text)
                    if stop_loss == "N/A":
                        stop_loss = self._extract_stop_loss(text)
                    if target == "N/A":
                        target = self._extract_target(text)
                    if horizon == "N/A":
                        horizon = self._extract_horizon(text)

                # Strict Quality Gate: Do not emit noise where Action is None/WATCH and SL/Target are both N/A
                if not action and stop_loss == "N/A" and target == "N/A":
                    continue
                if action == "WATCH" and stop_loss == "N/A" and target == "N/A" and horizon == "N/A":
                    continue

                if not action:
                    action = "BUY" if (target != "N/A" or stop_loss != "N/A") else "WATCH"

                seen_tickers.add(ticker)

                rec = StockRecommendation(
                    ticker=ticker,
                    action=action,
                    analyst=analyst,
                    stop_loss=stop_loss,
                    target=target,
                    horizon=horizon,
                    source_quote=matching_sentence[:250],
                    timestamp_seconds=best_snippet_time,
                    timestamp_formatted=format_timestamp(best_snippet_time),
                    timestamp_url=make_timestamp_url(video_id, best_snippet_time)
                )
                recommendations.append(rec)

        return recommendations

    def _detect_stocks(self, text: str) -> List[Tuple[str, str]]:
        """
        Detect Indian stocks strictly matching spoken aliases or major Indian market symbols.
        Avoids random uppercase words or mis-translated noise.
        """
        found = []
        text_lower = text.lower()
        
        # 1. Match known spoken aliases
        for alias, symbol in indian_market_manager.alias_map.items():
            if len(alias) >= 3 and re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                found.append((symbol, alias))

        # 2. Match explicit stock tickers (must be in alias map or major database)
        explicit_matches = re.findall(r'\b([A-Z0-9&-]{3,10})\b', text)
        for cand in explicit_matches:
            if cand in indian_market_manager.stocks_db and len(cand) >= 3:
                # Filter out suspicious short 3-letter tokens that are generic words
                if cand not in ["FOR", "AND", "THE", "CAN", "OUT", "LCL"]:
                    found.append((cand, indian_market_manager.stocks_db[cand]))

        unique_found = []
        seen_syms = set()
        for sym, name in found:
            if sym not in seen_syms and indian_market_manager.is_indian_stock(sym, name):
                seen_syms.add(sym)
                unique_found.append((sym, name))

        return unique_found

    def _detect_action(self, text: str) -> Optional[str]:
        if self.buy_triggers.search(text):
            return "BUY"
        elif self.sell_triggers.search(text):
            return "SELL"
        elif self.hold_triggers.search(text):
            return "HOLD"
        elif self.watch_triggers.search(text):
            return "WATCH"
        return None

    def _extract_stop_loss(self, text: str) -> str:
        for pattern in self.sl_patterns:
            match = pattern.search(text)
            if match:
                val = match.group(1).strip()
                if val and val.lower() not in ["the", "a", "is"]:
                    return val if ("₹" in val or "Rs" in val or "%" in val) else f"Rs {val}"
        return "N/A"

    def _extract_target(self, text: str) -> str:
        for pattern in self.tp_patterns:
            match = pattern.search(text)
            if match:
                val = match.group(1).strip()
                if val and val.lower() not in ["the", "a", "is"]:
                    return val if ("₹" in val or "Rs" in val or "%" in val) else f"Rs {val}"
        return "N/A"

    def _extract_horizon(self, text: str) -> str:
        for pattern, horizon_name in self.horizon_patterns:
            if pattern.search(text):
                return horizon_name
        return "N/A"

    def _extract_analyst(self, text: str) -> str:
        """Identify institutional fund house (Jefferies, JPM, Nomura) or individual analyst mentioned."""
        fund_houses = [
            "Jefferies", "JPMorgan", "J.P. Morgan", "Morgan Stanley", "Goldman Sachs",
            "CLSA", "Nomura", "Macquarie", "UBS", "HSBC", "Citi", "Citigroup", "Bernstein",
            "Motilal Oswal", "ICICI Direct", "Kotak Securities", "Kotak Institutional Equities",
            "HDFC Securities", "Axis Capital", "Nuvama", "Sharekhan", "Anand Rathi", "Emkay"
        ]
        for fh in fund_houses:
            if re.search(r'\b' + re.escape(fh) + r'\b', text, re.I):
                return fh

        # Detect analyst honorifics (e.g. Varun ji, Lokesh sir)
        m = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:ji|sir)\b', text)
        if m:
            name = m.group(1).strip()
            if not re.search(r'(?:from|question\s+from|ask(?:ing)?)\s+' + re.escape(name), text, re.I):
                return name

        return "N/A"
