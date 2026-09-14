# Indian Stock Extractor AI (Web App & CLI) 📈🇮🇳

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini%20Flash-4285F4.svg?logo=google&logoColor=white)](https://aistudio.google.com/)
[![Database](https://img.shields.io/badge/Database-Neon%20Postgres%20%7C%20SQLite-4169E1.svg?logo=postgresql&logoColor=white)](https://neon.tech)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind%20CSS-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-36%2F36%20Passed-2ea44f.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, production-ready AI platform that ingests YouTube Indian financial videos (e.g. Hindi/multilingual market shows, Zee Business, CNBC Awaaz, Money9), translates commentary, and extracts structured **NSE / BSE stock recommendations** (`BUY`, `HOLD`, `SELL`), target prices, stop losses, analyst names, and exact video timestamps.

Equipped with **live Current Market Prices (CMP)**, **target upside/downside potential %**, **6 core valuation fundamentals**, **30-day SVG trend charts**, **zero-overhead sector classification**, **multi-tier anti-blocking defenses**, and **one-click Excel / Markdown exports**.

> [!WARNING]
> ### ⚠️ Regulatory Disclaimer & SEBI Advisory (Personal Project Notice)
> **This software is an independent personal project created exclusively for educational, informational, and academic research purposes.**
>
> The developer/maintainer is **NOT a SEBI-registered Research Analyst, Investment Adviser, or Financial Intermediary** under the SEBI (Research Analysts) Regulations, 2014 or SEBI (Investment Advisers) Regulations, 2013.
>
> All stock quotes, analyst recommendations (`BUY` / `HOLD` / `SELL`), target prices, and stop-loss levels displayed by this application are automatically extracted by AI algorithms from publicly broadcast YouTube video content. **They do NOT constitute financial advice, investment recommendations, endorsement, or a solicitation to buy or sell securities.** Equity investments involve substantial market risk. Always consult a certified, SEBI-registered financial advisor before making any trading or investment decisions.

---

## ⚡ 3-Minute Quick Start (Local Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/Debanjan29/stock-recommendation-summarizer.git
cd stock-recommendation-summarizer
```

### 2. Create and Activate a Virtual Environment

- **On Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
- **On macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the sample environment file:
```bash
cp .env.example .env
```

Open `.env` and configure your keys:
```env
# 1. Google Gemini API Key (100% Free - get yours in 10 seconds: https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# 2. Database (Optional: falls back to local SQLite 'sqlite:///./stock_app.db' automatically if left blank)
DATABASE_URL=

# 3. Storage Optimization (Retention days before auto-purge, default 15)
RETENTION_DAYS=15
```
*(You can also run without setting `GEMINI_API_KEY` in `.env` and enter your key directly inside the web UI using the **"API Key" (BYOK)** button in the navbar!)*

### 5. Launch the Web Server
```bash
# Standard command:
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Or use the included 1-click launcher scripts on Windows:
# PowerShell:   .\run_web.ps1
# Double-click: run_web.bat
```

### 6. Open in Browser
Visit **`http://localhost:8000`** in your browser.
- Click the **"Quick Test"** badge below the search box (Money9 sample video) to test the complete extraction pipeline immediately!

### 7. 🔥🔥 📱 Running on Android (Termux)   🔥🔥
You can run the entire server directly on an Android smartphone using [Termux](https://termux.dev) with our lightweight, 100% pure-Python configuration (eliminates Rust, `pydantic-core`, `pandas`, and `lxml` build delays):

```bash
# 1. Update Termux and install Python + Git
pkg update -y && pkg install python git -y

# 2. Clone repository & install Android requirements (~15 seconds)
git clone https://github.com/Debanjan29/stock-recommendation-summarizer.git
cd stock-recommendation-summarizer
pip install -r requirements-android.txt

# 3. Launch server on localhost:8000
chmod +x run_android.sh
./run_android.sh
```
Open `http://localhost:8000` in your phone's browser (Chrome, Brave, Firefox, etc.).

---

## 🚀 Key Features & Capabilities

### 1. 🤖 AI-Powered Indian Market Intelligence
- **Multilingual Transcription & Translation**: Automatically translates Hindi, Hinglish, and regional speech to English using Google DeepTranslator with zero transcript loss.
- **Hinglish & Alias Resolution**: Maps spoken aliases to official NSE/BSE symbols (e.g. *"Tata Motors"* $\rightarrow$ `TATAMOTORS`, *"Policybazaar"* $\rightarrow$ `PBFINTECH`, *"State Bank"* $\rightarrow$ `SBIN`, *"M&M"* $\rightarrow$ `M&M`, *"Reliance"* $\rightarrow$ `RELIANCE`).
- **Devanagari Normalization**: Converts Devanagari script to clean Roman English text to prevent garbled console/table outputs.
- **Strict Guardrails**: Filters out penny-stock spam and hallucinated tickers; validates against a master catalog of 2,570+ listed Indian equities.

### 2. ⚡ Real-Time Live Extraction Stepper (Server-Sent Events)
- Clean, animated 5-stage progress tracker streaming live from the backend:
  1. **Cache**: Instant lookup in PostgreSQL/SQLite (< 100ms on repeat runs).
  2. **Metadata**: Fetches title, channel name, and HD thumbnail.
  3. **Transcript**: Downloads and translates full audio captions.
  4. **Gemini AI**: Extracts actionable calls, targets, stop-losses, and exact quotes.
  5. **Database**: Saves structured report with compressed transcripts.

### 3. 📊 Interactive Stock Dialog Modal & Live Fundamentals
- **Click-to-Open Details Dialog**: Clicking any stock ticker pill in the recommendations table opens an interactive, centered modal dialog (`Esc` or click outside to dismiss).
- **Live CMP & Day's Movement**: Real-time Current Market Price (CMP) and percentage/rupee gain or loss via NSE/BSE feeds (cached with 5-minute TTL).
- **Analyst Target Potential %**: Dynamically computes upside/downside potential between the live CMP and the video analyst's target price (e.g. `+14.2% Upside`).
- **6 Core Fundamentals Grid**:
  - **P/E Ratio** (Price-to-Earnings)
  - **P/B Ratio** (Price-to-Book)
  - **Dividend Yield (%)**
  - **Market Capitalization (₹ Crores)**
  - **52-Week High (₹)**
  - **52-Week Low (₹)**
- **30-Day SVG Price Sparkline**: Responsive vector chart displaying 30-day closing price trajectory and min/max levels rendered without external chart libraries.
- **One-Click TradingView & Google Finance Links**: Jump directly to live candlestick charts with a single click.

### 4. 🏷️ Zero-Cost Offline Sector Identification
- Automatically categorizes stocks into 16 major Indian market sectors (*Banking & Financial Services*, *Automobile*, *Information Technology*, *Pharma & Healthcare*, *Aerospace & Defense*, *Power & Utilities*, etc.).
- **Zero LLM Overhead**: Resolved via in-memory lookup maps and corporate name heuristics, saving Gemini tokens.
- **Interactive Filtering**: Dynamic Sector Breakdown pill bar with live count badges and one-click table filtering.

### 5. 📥 1-Click Multi-Format Exports
- **Styled Excel (.xlsx)**: Color-coded recommendation badges (`BUY` in emerald, `SELL` in rose, `HOLD` in amber), formatted currency columns, auto-fitted column widths, and clickable video timestamp links.
- **GitHub-Flavored Markdown (.md)**: Clean markdown summary table ready to share or paste into documentation.
- **CSV & JSON**: Raw structured data for quantitative backtesting or pipeline ingestion.

---

## ⚙️ Environment Variables Reference (`.env`)

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `GEMINI_API_KEY` | **Yes** *(or via UI)* | `None` | Google Gemini API key. Free tier available at [Google AI Studio](https://aistudio.google.com/app/apikey). |
| `DATABASE_URL` | No | `sqlite:///./stock_app.db` | PostgreSQL connection string from [Neon.tech](https://neon.tech). Falls back to SQLite if omitted. |
| `RETENTION_DAYS` | No | `15` | Number of days to retain analyzed video reports and transcripts before auto-purging. |
| `PROXY_URL` | No | `None` | Optional HTTP/HTTPS/SOCKS proxy (e.g. `http://user:pass@p.webshare.io:80`). |
| `WEBSHARE_USERNAME` | No | `None` | Optional Webshare proxy username (alternative to `PROXY_URL`). |
| `WEBSHARE_PASSWORD` | No | `None` | Optional Webshare proxy password (alternative to `PROXY_URL`). |
| `YOUTUBE_COOKIES_TEXT`| No | `None` | Exported YouTube `cookies.txt` content to bypass cloud datacenter IP bans. |
| `YOUTUBE_COOKIES_FILE`| No | `None` | File path to a Netscape formatted `cookies.txt` file. |

---

## 🖥️ Command-Line Interface (CLI) Guide

In addition to the web app, you can run extractions directly from your terminal:

### 1. Extract Recommendations to Terminal Table
```bash
python -m stock_extractor.cli extract "https://youtu.be/0Kekl5cBDSk"
```

### 2. Export to Excel or Markdown File
```bash
# Save to Excel
python -m stock_extractor.cli extract "https://youtu.be/0Kekl5cBDSk" --format table --output report.xlsx

# Output Markdown directly to console
python -m stock_extractor.cli extract "https://youtu.be/0Kekl5cBDSk" --format markdown
```

### 3. Fetch and Save Translated Transcript Only
```bash
python -m stock_extractor.cli transcript "https://youtu.be/0Kekl5cBDSk" --output transcript.txt
```

### 4. Run Automated 2-Stage Pipeline (Transcript $\rightarrow$ LLM Analysis)
```bash
python -m stock_extractor.cli pipeline "https://youtu.be/0Kekl5cBDSk" --output-dir ./output --format markdown
```

---

## 📡 REST API Reference

| Endpoint | Method | Parameters | Description |
| :--- | :---: | :--- | :--- |
| `/api/stream-extract` | `GET` | `url`: YouTube video link | Server-Sent Events (SSE) stream returning real-time progress percentages and final JSON report. |
| `/api/extract` | `POST` | JSON: `{"url": "...", "api_key": "..."}` | Programmatic extraction endpoint returning full structured JSON report. |
| `/api/stocks/{ticker}/quote` | `GET` | `ticker`: Stock symbol (e.g. `RELIANCE`) | Returns live CMP, day's change, 6 valuation fundamentals, and 30-day sparkline prices. |
| `/api/videos` | `GET` | `limit` (default 20), `offset` (default 0) | Paginated list of previously analyzed videos stored in the database. |
| `/api/videos/{video_id}` | `GET` | `video_id`: 11-char YouTube ID | Retrieve complete report, stock calls, and metadata for a specific video. |
| `/api/stocks/{ticker}` | `GET` | `ticker`: Stock symbol (e.g. `TATAMOTORS`) | Search all past recommendations and analyst calls across all videos for a given stock. |
| `/api/export/{video_id}` | `GET` | `format`: `xlsx`, `md`, `csv`, `json` | Download formatted Excel file, Markdown report, CSV table, or raw JSON. |
| `/api/system/storage` | `GET` | None | Returns database engine, total storage used (MB), and 500 MB free quota usage percentage. |
| `/api/system/prune` | `POST` | `days` (default 15) | Manually triggers 15-day rolling retention cleanup and database `VACUUM`. |
| `/api/health` | `GET` | None | Service health check endpoint for monitoring uptime. |

---

## 📂 Project Architecture & Directory Structure

```
stock_recommendation_summarizer/
├── app.py                          # FastAPI application & REST/SSE endpoints
├── requirements.txt                # Production Python dependencies (Desktop / Cloud)
├── requirements-android.txt        # Ultra-lightweight dependencies (Android / Termux)
├── run_android.sh                  # 1-click Termux launcher script
├── render.yaml                     # Render.com Blueprint deployment spec
├── .env.example                    # Sample environment variables template
├── README.md                       # Comprehensive documentation
│
├── stock_extractor/                # Core Python package
│   ├── __init__.py                 # Package initialization
│   ├── youtube.py                  # Multi-tier transcript fetcher (Proxy + Direct + Invidious)
│   ├── stock_quotes.py             # Live CMP, 6 fundamentals & 30-day sparkline service
│   ├── sectors.py                  # 16-sector offline classifier (Zero LLM overhead)
│   ├── storage.py                  # PostgreSQL & SQLite persistence, zlib compression & retention
│   ├── indian_market.py            # Master catalog (2,570+ NSE/BSE stocks & indices)
│   ├── extractors.py               # Gemini 3.6 Flash & heuristic recommendation extractors
│   ├── formatters.py               # Excel (.xlsx), Markdown, CSV, and console formatters
│   ├── utils.py                    # YouTube URL parsing, chunking & timestamp utilities
│   ├── cli.py                      # Typer CLI application
│   ├── pipeline.py                 # 2-stage automated pipeline runner
│   └── models.py                   # Pydantic data schemas (StockRecommendation, VideoReport)
│
├── static/                         # Frontend Web App (Single Page Application)
│   ├── index.html                  # Responsive UI with Tailwind CSS & modals
│   └── app.js                      # SSE live progress, stock dialog modal, filters & gallery
│
└── tests/                          # Automated unit test suite
    ├── test_api.py                 # FastAPI endpoints & quote testing
    ├── test_extractors.py          # Gemini extraction & Indian ticker validation
    ├── test_formatters.py          # Excel, Markdown, and CSV export formatting
    ├── test_youtube.py             # YouTube parsing & chunking unit tests
    └── test_cli.py                 # CLI interface command tests
```

---

## 🧪 Running Automated Tests

The repository includes a comprehensive unit test suite covering API endpoints, prompt extraction, Indian market symbol validation, export formatting, and proxy routing:

```bash
# Run all unit tests
python -m unittest discover tests
```

Expected output:
```
....................................
----------------------------------------------------------------------
Ran 36 tests in 45.120s

OK
```

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>1. Can I run this completely free without paying anything?</b></summary>
Yes! The entire stack is built to run 100% free:
- <b>Google Gemini API</b>: Google AI Studio offers a free tier (15 requests/minute).
- <b>Database</b>: Local SQLite runs out-of-the-box with zero setup, with optional PostgreSQL support.
</details>

<details>
<summary><b>2. Why did my proxy return HTTP 429 when downloading captions?</b></summary>
YouTube generates a cryptographic signature on the initial video page that is tied to your connection. If your proxy rotates IPs on every single request, YouTube detects an IP mismatch on the caption download and blocks it. Our system uses persistent sessions (keep-alive) and automatically cascades to a direct connection if a proxy is blocked.
</details>

<details>
<summary><b>3. How do I switch from local SQLite to PostgreSQL?</b></summary>
Simply copy your PostgreSQL connection string and paste it into <code>DATABASE_URL</code> in your <code>.env</code> file. The application detects PostgreSQL automatically and creates all required tables on startup.
</details>

<details>
<summary><b>4. What happens when a video has already been analyzed?</b></summary>
The system checks the database first. If the video was analyzed previously, it retrieves the saved report and recommendations in under <b>100 milliseconds</b> without calling YouTube or the Gemini API again.
</details>

<details>
<summary><b>5. Can I run this server directly on my Android phone?</b></summary>
Yes! Use Termux with <code>pip install -r requirements-android.txt</code>. This uses our pure-Python mobile configuration that completely omits heavy C/Rust compilers (<code>pydantic-core</code>, <code>pandas</code>, <code>numpy</code>, <code>lxml</code>, <code>psycopg2</code>), allowing the server to install in ~15 seconds and run locally on <code>http://localhost:8000</code>.
</details>

---

## ⚖️ Regulatory Disclaimer & SEBI Advisory

This repository and application are developed as an **open-source personal research project** designed to explore natural language processing (NLP), speech translation, and structured LLM information extraction from financial multimedia.

1. **Non-Registration Status**: The developer/maintainer is **not registered with the Securities and Exchange Board of India (SEBI)** in any capacity, including as a Research Analyst (under SEBI Research Analysts Regulations, 2014) or Investment Adviser (under SEBI Investment Advisers Regulations, 2013).
2. **No Investment Advice**: The output generated by this application does not represent the opinions, endorsements, or advice of the project creator. All data points (analyst names, targets, stop losses, sentiments) reflect third-party public YouTube speech transcribed and summarized by automated algorithms.
3. **No Commercial Solicitation**: This tool does not offer portfolio management, tip-providing services, or commercial financial advising.
4. **Limitation of Liability**: This software is provided "as-is" without warranty of any kind. Under no circumstances shall the author or contributors be held liable for any financial losses, trading damages, or decisions made based on information generated by this tool. Always consult a certified SEBI-registered financial advisor before trading.

---

## 📜 License

Distributed under the **MIT License** as an open-source personal project. See `LICENSE` for more information. Built for educational and research exploration of the Indian Stock Market (NSE / BSE).
