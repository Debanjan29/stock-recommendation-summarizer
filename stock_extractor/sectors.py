"""
Sector Identification and Auto-Discovery Module for Indian Stock Market (NSE / BSE).
Provides instant O(1) in-memory lookup, corporate keyword heuristics, and free Yahoo Finance fallback for new IPOs.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Optional, Any

# Primary Standardized Sector Taxonomy for Indian Markets
SECTOR_AUTOMOBILE = "Automobile & Ancillary"
SECTOR_BANKING = "Banking & Financial Services"
SECTOR_IT = "Information Technology"
SECTOR_PHARMA = "Pharmaceuticals & Healthcare"
SECTOR_ENERGY = "Oil, Gas & Fuels"
SECTOR_DEFENSE = "Aerospace & Defense"
SECTOR_METALS = "Metals & Mining"
SECTOR_CAPITAL_GOODS = "Capital Goods & Engineering"
SECTOR_INFRA = "Infrastructure & Construction"
SECTOR_CHEMICALS = "Chemicals & Petrochemicals"
SECTOR_FMCG = "FMCG & Consumer Goods"
SECTOR_RETAIL = "Consumer Durables & Retail"
SECTOR_POWER = "Power & Utilities"
SECTOR_TELECOM = "Telecommunications"
SECTOR_REALTY = "Real Estate & Realty"
SECTOR_DIVERSIFIED = "Diversified / Other"

# Standard Master Mapping for Prominent NSE/BSE Listed Equities & Indices
BASE_SECTOR_MAP: Dict[str, str] = {
    # Indices
    "NIFTY 50": "Broad Market Index",
    "BANKNIFTY": SECTOR_BANKING,
    "SENSEX": "Broad Market Index",
    "FINNIFTY": SECTOR_BANKING,
    "MIDCPNIFTY": "Broad Market Index",

    # Automobile & EV & Ancillaries
    "TATAMOTORS": SECTOR_AUTOMOBILE,
    "MARUTI": SECTOR_AUTOMOBILE,
    "M&M": SECTOR_AUTOMOBILE,
    "BAJAJ-AUTO": SECTOR_AUTOMOBILE,
    "HEROMOTOCO": SECTOR_AUTOMOBILE,
    "EICHERMOT": SECTOR_AUTOMOBILE,
    "TVSMOTOR": SECTOR_AUTOMOBILE,
    "ASHOKLEY": SECTOR_AUTOMOBILE,
    "BHARATFORG": SECTOR_AUTOMOBILE,
    "MOTHERSON": SECTOR_AUTOMOBILE,
    "BOSCHLTD": SECTOR_AUTOMOBILE,
    "MRF": SECTOR_AUTOMOBILE,
    "APOLLOTYRE": SECTOR_AUTOMOBILE,
    "BALKRISIND": SECTOR_AUTOMOBILE,
    "NRBBEARING": SECTOR_AUTOMOBILE,
    "OLAELEC": SECTOR_AUTOMOBILE,
    "SSWL": SECTOR_AUTOMOBILE,
    "SONACOMS": SECTOR_AUTOMOBILE,

    # Banking & Financial Services
    "HDFCBANK": SECTOR_BANKING,
    "ICICIBANK": SECTOR_BANKING,
    "SBIN": SECTOR_BANKING,
    "KOTAKBANK": SECTOR_BANKING,
    "AXISBANK": SECTOR_BANKING,
    "INDUSINDBK": SECTOR_BANKING,
    "BANKBARODA": SECTOR_BANKING,
    "PNB": SECTOR_BANKING,
    "IDFCFIRSTB": SECTOR_BANKING,
    "YESBANK": SECTOR_BANKING,
    "FEDERALBNK": SECTOR_BANKING,
    "BAJFINANCE": SECTOR_BANKING,
    "BAJAJFINSV": SECTOR_BANKING,
    "CHOLAFIN": SECTOR_BANKING,
    "SHRIRAMFIN": SECTOR_BANKING,
    "MUTHOOTFIN": SECTOR_BANKING,
    "PFC": SECTOR_BANKING,
    "RECLTD": SECTOR_BANKING,
    "IRFC": SECTOR_BANKING,
    "JIOFIN": SECTOR_BANKING,
    "PBFINTECH": SECTOR_BANKING,
    "BAJAJHFL": SECTOR_BANKING,
    "HDFCLIFE": SECTOR_BANKING,
    "SBILIFE": SECTOR_BANKING,
    "ICICIPRULI": SECTOR_BANKING,
    "AAVAS": SECTOR_BANKING,
    "AADHARHFC": SECTOR_BANKING,
    "CANFINHOME": SECTOR_BANKING,
    "LICHSGFIN": SECTOR_BANKING,
    "LICI": SECTOR_BANKING,
    "TATAINVEST": SECTOR_BANKING,

    # Information Technology & Tech Platforms
    "TCS": SECTOR_IT,
    "INFY": SECTOR_IT,
    "HCLTECH": SECTOR_IT,
    "WIPRO": SECTOR_IT,
    "TECHM": SECTOR_IT,
    "LTIM": SECTOR_IT,
    "PERSISTENT": SECTOR_IT,
    "COFORGE": SECTOR_IT,
    "MPHASIS": SECTOR_IT,
    "LTTS": SECTOR_IT,
    "TATAELXSI": SECTOR_IT,
    "TATATECH": SECTOR_IT,
    "SUBEXLTD": SECTOR_IT,
    "HAPPSTMNDS": SECTOR_IT,
    "KPITTECH": SECTOR_IT,
    "CYIENT": SECTOR_IT,
    "ZOMATO": SECTOR_IT,
    "SWIGGY": SECTOR_IT,
    "PAYTM": SECTOR_IT,
    "NAUKRI": SECTOR_IT,
    "MAPMYINDIA": SECTOR_IT,
    "FSL": SECTOR_IT,
    "BSOFT": SECTOR_IT,

    # Aerospace & Defense
    "HAL": SECTOR_DEFENSE,
    "BEL": SECTOR_DEFENSE,
    "BDL": SECTOR_DEFENSE,
    "DATAPATTNS": SECTOR_DEFENSE,
    "PARAS": SECTOR_DEFENSE,
    "COCHINSHIP": SECTOR_DEFENSE,
    "MAZDOCK": SECTOR_DEFENSE,
    "GRSE": SECTOR_DEFENSE,
    "MTARTECH": SECTOR_DEFENSE,
    "AVANTEL": SECTOR_DEFENSE,
    "IDEAFORGE": SECTOR_DEFENSE,
    "AXISCADES": SECTOR_DEFENSE,
    "PTCIL": SECTOR_DEFENSE,
    "UNIMECH": SECTOR_DEFENSE,
    "MIDHANI": SECTOR_DEFENSE,

    # Oil, Gas & Fuels
    "RELIANCE": SECTOR_ENERGY,
    "ONGC": SECTOR_ENERGY,
    "IOC": SECTOR_ENERGY,
    "BPCL": SECTOR_ENERGY,
    "HPCL": SECTOR_ENERGY,
    "OIL": SECTOR_ENERGY,
    "GAIL": SECTOR_ENERGY,
    "PETRONET": SECTOR_ENERGY,
    "IGL": SECTOR_ENERGY,
    "MGL": SECTOR_ENERGY,
    "GUJGASLTD": SECTOR_ENERGY,
    "CASTROLIND": SECTOR_ENERGY,

    # Power & Utilities & Renewable Energy
    "NTPC": SECTOR_POWER,
    "POWERGRID": SECTOR_POWER,
    "TATAPOWER": SECTOR_POWER,
    "ADANIGREEN": SECTOR_POWER,
    "ADANIPOWER": SECTOR_POWER,
    "JSWENERGY": SECTOR_POWER,
    "SUZLON": SECTOR_POWER,
    "PREMIERENE": SECTOR_POWER,
    "WAAREEENER": SECTOR_POWER,
    "NHPC": SECTOR_POWER,
    "SJVN": SECTOR_POWER,
    "IEX": SECTOR_POWER,

    # Metals & Mining
    "TATASTEEL": SECTOR_METALS,
    "JSWSTEEL": SECTOR_METALS,
    "HINDALCO": SECTOR_METALS,
    "VEDL": SECTOR_METALS,
    "COALINDIA": SECTOR_METALS,
    "NMDC": SECTOR_METALS,
    "SAIL": SECTOR_METALS,
    "JINDALSTEL": SECTOR_METALS,
    "NATIONALUM": SECTOR_METALS,
    "HINDZINC": SECTOR_METALS,
    "GMDCLTD": SECTOR_METALS,

    # Pharmaceuticals & Healthcare
    "SUNPHARMA": SECTOR_PHARMA,
    "DRREDDY": SECTOR_PHARMA,
    "CIPLA": SECTOR_PHARMA,
    "DIVISLAB": SECTOR_PHARMA,
    "LUPIN": SECTOR_PHARMA,
    "APOLLOHOSP": SECTOR_PHARMA,
    "MAXHEALTH": SECTOR_PHARMA,
    "FORTIS": SECTOR_PHARMA,
    "MEDANTA": SECTOR_PHARMA,
    "MANKIND": SECTOR_PHARMA,
    "TORNTPHARM": SECTOR_PHARMA,
    "ZYDUSLIFE": SECTOR_PHARMA,
    "AUROPHARMA": SECTOR_PHARMA,
    "BIOCON": SECTOR_PHARMA,
    "ALKEM": SECTOR_PHARMA,
    "PARKHOSPS": SECTOR_PHARMA,

    # Infrastructure & Construction & Capital Goods
    "LT": SECTOR_CAPITAL_GOODS,
    "SIEMENS": SECTOR_CAPITAL_GOODS,
    "ABB": SECTOR_CAPITAL_GOODS,
    "BHEL": SECTOR_CAPITAL_GOODS,
    "HAVELLS": SECTOR_CAPITAL_GOODS,
    "CUMMINSIND": SECTOR_CAPITAL_GOODS,
    "THERMAX": SECTOR_CAPITAL_GOODS,
    "AIAENG": SECTOR_CAPITAL_GOODS,
    "TEGA": SECTOR_CAPITAL_GOODS,
    "LOHIACORP": SECTOR_CAPITAL_GOODS,
    "ULTRACEMCO": SECTOR_INFRA,
    "AMBUJACEM": SECTOR_INFRA,
    "ACC": SECTOR_INFRA,
    "DALBHARAT": SECTOR_INFRA,
    "SHREECEM": SECTOR_INFRA,
    "IRB": SECTOR_INFRA,
    "RVNL": SECTOR_INFRA,
    "IRCON": SECTOR_INFRA,
    "NBCC": SECTOR_INFRA,
    "PNCINFRA": SECTOR_INFRA,
    "KNRCON": SECTOR_INFRA,
    "DBL": SECTOR_INFRA,

    # Chemicals & Petrochemicals
    "PIDILITIND": SECTOR_CHEMICALS,
    "SRF": SECTOR_CHEMICALS,
    "GUJFLUORO": SECTOR_CHEMICALS,
    "DEEPAKNTR": SECTOR_CHEMICALS,
    "TATACHEM": SECTOR_CHEMICALS,
    "ATUL": SECTOR_CHEMICALS,
    "AARTIIND": SECTOR_CHEMICALS,
    "SUDARSCHEM": SECTOR_CHEMICALS,
    "AETHER": SECTOR_CHEMICALS,
    "FINEORG": SECTOR_CHEMICALS,
    "NAVINFLUOR": SECTOR_CHEMICALS,
    "CLEAN": SECTOR_CHEMICALS,
    "UPL": SECTOR_CHEMICALS,
    "COROMANDEL": SECTOR_CHEMICALS,

    # FMCG & Consumer Durables & Retail
    "ITC": SECTOR_FMCG,
    "HINDUNILVR": SECTOR_FMCG,
    "NESTLEIND": SECTOR_FMCG,
    "BRITANNIA": SECTOR_FMCG,
    "DABUR": SECTOR_FMCG,
    "MARICO": SECTOR_FMCG,
    "GODREJCP": SECTOR_FMCG,
    "COLPAL": SECTOR_FMCG,
    "VBL": SECTOR_FMCG,
    "TATACONSUM": SECTOR_FMCG,
    "MILKYMIST": SECTOR_FMCG,
    "SDBL": SECTOR_FMCG,
    "TITAN": SECTOR_RETAIL,
    "ASIANPAINT": SECTOR_RETAIL,
    "BERGEPAINT": SECTOR_RETAIL,
    "DMART": SECTOR_RETAIL,
    "TRENT": SECTOR_RETAIL,
    "KALYANKJIL": SECTOR_RETAIL,
    "ABFRL": SECTOR_RETAIL,
    "VOLTAS": SECTOR_RETAIL,
    "BLUESTARCO": SECTOR_RETAIL,
    "CARYSIL": SECTOR_RETAIL,
    "BRAINBEES": SECTOR_RETAIL,

    # Real Estate & Realty
    "DLF": SECTOR_REALTY,
    "GODREJPROP": SECTOR_REALTY,
    "MACROTECH": SECTOR_REALTY,
    "OBEROIRLTY": SECTOR_REALTY,
    "PRESTIGE": SECTOR_REALTY,
    "BRIGADE": SECTOR_REALTY,
    "PHOENIXLTD": SECTOR_REALTY,
    "SOBHA": SECTOR_REALTY,
    "KOLTEPATIL": SECTOR_REALTY,

    # Telecommunications
    "BHARTIARTL": SECTOR_TELECOM,
    "IDEA": SECTOR_TELECOM,
    "TATACOMM": SECTOR_TELECOM,
    "INDUSTOWER": SECTOR_TELECOM
}

# Mapping from Yahoo Finance Sector descriptions to Standard Indian Sectors
YAHOO_SECTOR_MAPPING: Dict[str, str] = {
    "financial services": SECTOR_BANKING,
    "technology": SECTOR_IT,
    "healthcare": SECTOR_PHARMA,
    "energy": SECTOR_ENERGY,
    "basic materials": SECTOR_METALS,
    "industrials": SECTOR_CAPITAL_GOODS,
    "consumer cyclical": SECTOR_RETAIL,
    "consumer defensive": SECTOR_FMCG,
    "utilities": SECTOR_POWER,
    "real estate": SECTOR_REALTY,
    "communication services": SECTOR_TELECOM
}

# Corporate Name Keywords to Infer Sector for Unindexed or Day-1 IPOs
KEYWORD_PATTERNS = [
    # Banking & Financial Services
    (r'\b(bank|banking|finance|finserv|fintech|capital|financial|housing finance|securities|wealth|leasing|holdings|asset)\b', SECTOR_BANKING),
    # Pharmaceuticals & Healthcare
    (r'\b(pharma|pharmaceutical|pharmaceuticals|laboratories|lab|labs|drugs|healthcare|hospital|hospitals|diagnostic|diagnostics|biotech|lifesciences|remedies)\b', SECTOR_PHARMA),
    # Information Technology
    (r'\b(technologies|technology|software|infotech|tech|digital|solutions|systems|consulting|cyber)\b', SECTOR_IT),
    # Automobile & Ancillary
    (r'\b(motors|motor|auto|automotive|tyres|tyre|battery|batteries|axle|bearings|bearing|wheel|wheels|ancillary)\b', SECTOR_AUTOMOBILE),
    # Power & Energy
    (r'\b(power|energy|energies|solar|wind|hydro|renewables|electricity|green energy)\b', SECTOR_POWER),
    # Oil & Gas
    (r'\b(petroleum|petro|oil|gas|refineries|refinery|lubricants|fuels)\b', SECTOR_ENERGY),
    # Aerospace & Defense
    (r'\b(aerospace|defense|defence|aeronautics|radar|dynamics|ordnance)\b', SECTOR_DEFENSE),
    # Metals & Mining
    (r'\b(steel|metals|metal|alloys|alloy|mining|mines|mineral|minerals|aluminum|copper|zinc|iron|coal)\b', SECTOR_METALS),
    # Infrastructure & Capital Goods
    (r'\b(infra|infrastructure|construction|engineers|engineering|projects|builders|cement|pipes|pipe|buildcon)\b', SECTOR_INFRA),
    # Chemicals & Petrochemicals
    (r'\b(chemicals|chemical|petrochem|fertilizers|fertilizer|organics|organic|alkalies|chlorine|fluorine)\b', SECTOR_CHEMICALS),
    # Real Estate & Realty
    (r'\b(realty|real estate|developers|properties|property|land|estates)\b', SECTOR_REALTY),
    # FMCG & Consumer
    (r'\b(foods|food|dairy|beverages|breweries|distilleries|distillery|sugar|agro|consumer products|edible)\b', SECTOR_FMCG),
    # Retail & Consumer Durables
    (r'\b(retail|fashions|fashion|textiles|textile|garments|apparel|footwear|jewellery|jewelers|appliances)\b', SECTOR_RETAIL),
    # Telecommunications
    (r'\b(telecom|telecommunications|communications|cellular|telecom towers)\b', SECTOR_TELECOM)
]


class StockSectorManager:
    """Manages sector classification with in-memory caching and online auto-discovery."""

    def __init__(self):
        self.sector_map: Dict[str, str] = dict(BASE_SECTOR_MAP)
        self.custom_file = os.path.join(os.path.dirname(__file__), "data", "custom_sectors.json")
        self._load_custom_sectors()

    def _load_custom_sectors(self):
        """Load dynamically discovered IPO sectors from disk if present."""
        if os.path.exists(self.custom_file):
            try:
                with open(self.custom_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.sector_map.update(data)
            except Exception:
                pass

    def _save_custom_sector(self, ticker: str, sector: str):
        """Persist newly discovered sector so it is fetched from network only once."""
        os.makedirs(os.path.dirname(os.path.abspath(self.custom_file)), exist_ok=True)
        try:
            current_data = {}
            if os.path.exists(self.custom_file):
                with open(self.custom_file, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            current_data[ticker] = sector
            with open(self.custom_file, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)
        except Exception:
            pass

    def get_sector(self, ticker: str, company_name: str = "", allow_online: bool = False) -> str:
        """
        Identify sector for a stock through a multi-tier pipeline:
        1. Exact ticker match in curated BASE_SECTOR_MAP & custom JSON cache
        2. Corporate naming heuristics (keywords in alias / ticker)
        3. Lookup company full name from 2,700+ NSE master DB & keyword heuristic
        4. Optional Online discovery via Yahoo Finance (for brand new IPOs)
        5. Fallback to 'Diversified / Other' (cached in memory for speed)
        """
        clean_ticker = (ticker or "").strip().upper()
        if not clean_ticker:
            return SECTOR_DIVERSIFIED

        # 1. Check in-memory base & cached map
        if clean_ticker in self.sector_map:
            return self.sector_map[clean_ticker]

        # 2. Check company name keywords if provided
        name_to_check = company_name or clean_ticker
        matched_sector = self._match_keywords(name_to_check)
        if matched_sector:
            self.sector_map[clean_ticker] = matched_sector
            return matched_sector

        # 3. Check official stock name from indian_market_manager DB if available
        try:
            from stock_extractor.indian_market import indian_market_manager
            full_name = indian_market_manager.stocks_db.get(clean_ticker, "")
            if full_name:
                matched_sector = self._match_keywords(full_name)
                if matched_sector:
                    self.sector_map[clean_ticker] = matched_sector
                    return matched_sector
        except Exception:
            pass

        # 4. Optional Online Auto-Discovery via Yahoo Finance API (For brand new IPOs)
        if allow_online:
            online_sector = self._fetch_online_sector(clean_ticker)
            if online_sector:
                self.sector_map[clean_ticker] = online_sector
                self._save_custom_sector(clean_ticker, online_sector)
                return online_sector

        # 5. Cache fallback in-memory so subsequent lookups are instantaneous
        self.sector_map[clean_ticker] = SECTOR_DIVERSIFIED
        return SECTOR_DIVERSIFIED

    def _match_keywords(self, text: str) -> Optional[str]:
        """Match corporate naming keywords to deduce sector."""
        if not text:
            return None
        text_lower = text.lower()
        for pattern, sector in KEYWORD_PATTERNS:
            if re.search(pattern, text_lower):
                return sector
        return None

    def _fetch_online_sector(self, ticker: str) -> Optional[str]:
        """Fetch sector from free Yahoo Finance quoteSummary profile endpoint."""
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}.NS?modules=assetProfile"
        try:
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    results = data.get("quoteSummary", {}).get("result", [])
                    if results:
                        profile = results[0].get("assetProfile", {})
                        raw_sector = (profile.get("sector") or "").lower().strip()
                        if raw_sector in YAHOO_SECTOR_MAPPING:
                            return YAHOO_SECTOR_MAPPING[raw_sector]
                        elif raw_sector:
                            return raw_sector.title()
        except Exception:
            pass
        return None


# Global Singleton Instance
sector_manager = StockSectorManager()


def get_stock_sector(ticker: str, company_name: str = "", allow_online: bool = False) -> str:
    """Convenience function to get sector for a stock ticker."""
    return sector_manager.get_sector(ticker, company_name, allow_online=allow_online)
