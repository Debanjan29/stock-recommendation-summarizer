"""
Indian Stock Market Module.
Handles Indian stock database lookup (NSE & BSE), spoken aliases, strict Indian stock filtering,
and free external API integration (Yahoo Finance & NSE Public endpoints).
"""

import os
import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Tuple, Optional, List, Set, Any

# Standard Spoken Aliases -> Official NSE Symbol
# Words to guard against false-positive ticker collisions
COMMON_ENGLISH_WORDS: Set[str] = {
    "take", "dollar", "idea", "fact", "deep", "star", "apex", "best", "well",
    "good", "nice", "fast", "time", "rate", "mind", "gain", "mark", "care",
    "true", "team", "gold", "next", "long", "hold", "look", "more", "high",
    "low", "line", "point", "plan", "core", "bond", "deal", "free", "view",
    "for", "and", "the", "can", "out", "all", "new", "see", "day", "now"
}

# Standard Spoken Aliases -> Official NSE Symbol
SPOKEN_ALIASES: Dict[str, str] = {
    "reliance": "RELIANCE", "reliance industries": "RELIANCE", "ril": "RELIANCE",
    "tata motors": "TATAMOTORS", "tata motor": "TATAMOTORS", "tmpv": "TATAMOTORS",
    "tata steel": "TATASTEEL", "tcs": "TCS", "tata consultancy": "TCS",
    "tata power": "TATAPOWER", "tata tech": "TATATECH", "tata technologies": "TATATECH",
    "tata consumer": "TATACONSUM", "tata elxsi": "TATAELXSI", "tata communications": "TATACOMM",
    "infosys": "INFY", "infy": "INFY",
    "hdfc": "HDFCBANK", "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "icici": "ICICIBANK", "icici bank": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "axis bank": "AXISBANK", "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK", "kotak mahindra": "KOTAKBANK",
    "indusind": "INDUSINDBK", "indusind bank": "INDUSINDBK", "yes bank": "YESBANK", "idfc first": "IDFCFIRSTB",
    "itc": "ITC", "l&t": "LT", "larsen": "LT", "larsen and toubro": "LT", "larsen & toubro": "LT",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "mahindra": "M&M", "m&m": "M&M", "mahindra and mahindra": "M&M",
    "bajaj finance": "BAJFINANCE", "bajaj finserv": "BAJAJFINSV", "bajaj auto": "BAJAJ-AUTO",
    "zomato": "ZOMATO", "paytm": "PAYTM", "one97": "PAYTM", "jio financial": "JIOFIN", "jiofin": "JIOFIN",
    "policybazaar": "PBFINTECH", "policy bazaar": "PBFINTECH", "pb fintech": "PBFINTECH",
    "firstcry": "BRAINBEES", "first cry": "BRAINBEES", "brainbees": "BRAINBEES",
    "ola electric": "OLAELEC", "ola": "OLAELEC",
    "bajaj housing": "BAJAJHFL", "bajaj housing finance": "BAJAJHFL",
    "premier energies": "PREMIERENE", "premier energy": "PREMIERENE",
    "turtlemint": "TURTLEMINT", "turtlement": "TURTLEMINT", "perpint": "TURTLEMINT", "turmoil": "TURTLEMINT",
    "lohia corp": "LOHIACORP", "lohia": "LOHIACORP", "lohia coop": "LOHIACORP", "loya cock": "LOHIACORP",
    "milky mist": "MILKYMIST", "milkymist": "MILKYMIST",
    "western carriers": "WESTERN", "western": "WESTERN", "tru bulk": "WESTERN",
    "swiggy": "SWIGGY",
    "park medi": "PARKHOSPS", "park medward": "PARKHOSPS", "park medi world": "PARKHOSPS", "park mediworld": "PARKHOSPS", "parkhosps": "PARKHOSPS",
    "axiscades": "AXISCADES", "axis cades": "AXISCADES", "axis cad": "AXISCADES", "axis cd": "AXISCADES", "axiscades tech": "AXISCADES",
    "data patterns": "DATAPATTNS", "data pattern": "DATAPATTNS", "datapattns": "DATAPATTNS",
    "paras defence": "PARAS", "paras defense": "PARAS", "paras": "PARAS",
    "sswl": "SSWL", "steel strips": "SSWL", "steel strips wheels": "SSWL", "steel stiffening": "SSWL",
    "kolte patil": "KOLTEPATIL", "kolte-patil": "KOLTEPATIL", "kote patil": "KOLTEPATIL",
    "abfrl": "ABFRL", "ab frl": "ABFRL", "aditya birla fashion": "ABFRL",
    "sdbl": "SDBL", "som distilleries": "SDBL", "som distilleries & breweries": "SDBL",
    "sika": "SIKA", "cika": "SIKA", "sika interplant": "SIKA",
    "bdl": "BDL", "bharat dynamics": "BDL",
    "ideaforge": "IDEAFORGE", "idea 4": "IDEAFORGE", "idi farz": "IDEAFORGE",
    "avantel": "AVANTEL", "avantal": "AVANTEL",
    "hal": "HAL", "hindustan aeronautics": "HAL", "bhel": "BHEL", "bel": "BEL", "bharat electronics": "BEL",
    "rec": "RECLTD", "rural electrification": "RECLTD", "pfc": "PFC", "power finance": "PFC",
    "irfc": "IRFC", "indian railway finance": "IRFC", "rvnl": "RVNL", "rail vikas": "RVNL", "irctc": "IRCTC",
    "suzlon": "SUZLON", "suzlon energy": "SUZLON", "coal india": "COALINDIA",
    "ntpc": "NTPC", "power grid": "POWERGRID", "powergrid": "POWERGRID", "ongc": "ONGC", "oil india": "OIL",
    "dlf": "DLF", "godrej properties": "GODREJPROP", "d-mart": "DMART", "dmart": "DMART", "avenue supermarts": "DMART",
    "titan": "TITAN", "asian paints": "ASIANPAINT", "asian paint": "ASIANPAINT", "berger paints": "BERGERPAINT",
    "ultratech": "ULTRACEMCO", "ultratech cement": "ULTRACEMCO", "ambuja": "AMBUJACEM", "acc": "ACC",
    "cipla": "CIPLA", "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY", "dr reddys": "DRREDDY",
    "divis lab": "DIVISLAB", "divis": "DIVISLAB", "lupin": "LUPIN", "mankind pharma": "MANKIND",
    "nifty": "NIFTY 50", "nifty 50": "NIFTY 50", "nifty fifty": "NIFTY 50",
    "bank nifty": "BANKNIFTY", "banknifty": "BANKNIFTY", "nifty bank": "BANKNIFTY",
    "sensex": "SENSEX", "bsesensex": "SENSEX", "finnifty": "FINNIFTY", "midcap nifty": "MIDCPNIFTY"
}

# Major Indian Market Indices
INDIAN_INDICES: Set[str] = {
    "NIFTY 50", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", 
    "NIFTY IT", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY BANK", "NIFTY REALTY", "NIFTY FMCG"
}

class IndianStockManager:
    """Manager for loading, validating, and searching Indian market stocks."""
    
    def __init__(self):
        self.stocks_db: Dict[str, str] = {}
        self.alias_map: Dict[str, str] = dict(SPOKEN_ALIASES)
        self._load_master_db()

    def _load_master_db(self):
        """Load Indian stock database from local JSON or fetch from NSE."""
        db_path = os.path.join(os.path.dirname(__file__), "data", "indian_stocks_master.json")
        
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    self.stocks_db = json.load(f)
            except Exception:
                pass

        if not self.stocks_db:
            # Fallback inline dictionary of major stocks if file missing
            self.stocks_db = {
                "RELIANCE": "Reliance Industries Limited",
                "TATAMOTORS": "Tata Motors Limited",
                "TATASTEEL": "Tata Steel Limited",
                "TCS": "Tata Consultancy Services Limited",
                "INFY": "Infosys Limited",
                "HDFCBANK": "HDFC Bank Limited",
                "ICICIBANK": "ICICI Bank Limited",
                "SBIN": "State Bank of India",
                "ITC": "ITC Limited",
                "LT": "Larsen & Toubro Limited",
                "ZOMATO": "Zomato Limited",
                "SUZLON": "Suzlon Energy Limited",
                "HAL": "Hindustan Aeronautics Limited",
                "NIFTY 50": "NIFTY 50 Index",
                "BANKNIFTY": "NIFTY Bank Index",
                "SENSEX": "BSE SENSEX Index"
            }

        # Ensure important modern Indian companies exist in stocks_db
        extra_stocks = {
            "LOHIACORP": "Lohia Corp Limited",
            "TURTLEMINT": "Turtlemint Fintech Limited",
            "WESTERN": "Western Carriers (India) Limited",
            "MILKYMIST": "Milky Mist Dairy Food Limited",
            "SWIGGY": "Swiggy Limited",
            "PBFINTECH": "PB Fintech Limited",
            "PARKHOSPS": "Park Medi World Limited"
        }
        for s_ticker, s_name in extra_stocks.items():
            if s_ticker not in self.stocks_db:
                self.stocks_db[s_ticker] = s_name

        # Build reverse mapping from lower-case company names to ticker
        for ticker, name in self.stocks_db.items():
            clean_name = re.sub(r'\b(limited|ltd|corp|corporation|inc|industries|company|holdings|services)\b', '', name, flags=re.I).strip().lower()
            if clean_name and len(clean_name) > 3 and clean_name not in self.alias_map:
                if clean_name not in COMMON_ENGLISH_WORDS:
                    self.alias_map[clean_name] = ticker

            # Also index prominent 2-word prefixes (e.g. 'milky mist dairy food' -> 'milky mist')
            parts = clean_name.split()
            if len(parts) >= 2:
                prefix = f"{parts[0]} {parts[1]}"
                if len(prefix) > 5 and prefix not in self.alias_map and prefix not in COMMON_ENGLISH_WORDS:
                    self.alias_map[prefix] = ticker

        # Ensure all spoken alias target symbols exist in stocks_db
        for alias, sym in SPOKEN_ALIASES.items():
            if sym not in self.stocks_db:
                self.stocks_db[sym] = alias.title()

    def is_indian_stock(self, ticker: str, company_name: str = "") -> bool:
        """
        Verify whether a ticker or company name belongs strictly to the Indian stock market (NSE / BSE).
        Excludes foreign / US stocks (e.g. AAPL, TSLA, NVDA) and common dictionary words.
        """
        ticker_upper = ticker.strip().upper()
        ticker_lower = ticker.strip().lower()
        company_lower = company_name.strip().lower()

        # Reject bare common English words unless accompanied by explicit corporate suffix/context
        if ticker_lower in COMMON_ENGLISH_WORDS:
            if not company_lower or company_lower == ticker_lower:
                return False
            corporate_indicators = ["ltd", "limited", "corp", "industries", "industry", "solutions", "pharma", "bank", "holdings", "shares", "stock"]
            if not any(ci in company_lower for ci in corporate_indicators):
                return False
        
        if ticker_upper in INDIAN_INDICES:
            return True
            
        if ticker_upper in self.stocks_db:
            return True
            
        if company_lower in self.alias_map:
            return True

        # Check online via free API if unknown locally
        api_result = self.query_free_yahoo_api(ticker)
        if api_result and api_result.get("is_indian"):
            return True

        return False

    def query_free_yahoo_api(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Query free Yahoo Finance Search API to check if a symbol/company is listed on NSE (.NS) or BSE (.BO).
        No API key required.
        """
        encoded_query = urllib.parse.quote(query)
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={encoded_query}&quotesCount=5"
        
        try:
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    quotes = data.get("quotes", [])
                    for q in quotes:
                        symbol = q.get("symbol", "")
                        exchange = q.get("exchange", "")
                        shortname = q.get("shortname") or q.get("longname") or ""
                        
                        if symbol.endswith(".NS") or symbol.endswith(".BO") or exchange in ["NSI", "BSE", "NSE"]:
                            clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
                            return {
                                "symbol": clean_symbol,
                                "exchange": "NSE" if ".NS" in symbol or exchange == "NSI" else "BSE",
                                "name": shortname,
                                "is_indian": True
                            }
        except Exception:
            pass
            
        return None

    def resolve_ticker(self, text_mention: str) -> Optional[Tuple[str, str]]:
        """
        Resolve a text mention or ticker candidate to (official_symbol, company_name).
        Returns None if not an Indian stock or if it's a common dictionary word.
        """
        clean_text = text_mention.strip()
        lower_text = clean_text.lower()
        upper_text = clean_text.upper()

        if lower_text in COMMON_ENGLISH_WORDS:
            return None

        # 1. Direct Alias Match
        if lower_text in self.alias_map:
            sym = self.alias_map[lower_text]
            name = self.stocks_db.get(sym, sym)
            return sym, name

        # 2. Direct Ticker Match in NSE Database
        if upper_text in self.stocks_db:
            return upper_text, self.stocks_db[upper_text]

        # 3. Direct Index Match
        if upper_text in INDIAN_INDICES:
            return upper_text, f"{upper_text} Index"

        # 4. Check Free API Online
        api_res = self.query_free_yahoo_api(clean_text)
        if api_res and api_res.get("is_indian"):
            sym = api_res["symbol"]
            name = api_res["name"] or sym
            return sym, name

        return None

# Global Instance Singleton
indian_market_manager = IndianStockManager()
