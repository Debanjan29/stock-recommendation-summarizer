# YouTube Stock Extractor CLI (Indian Market Edition) 📈🇮🇳

An automated 2-stage CLI pipeline that ingests a YouTube video URL, fetches & translates transcripts to English with full metadata, and runs the AGY AI CLI (`agy --print`) non-interactively to generate structured Indian stock recommendation reports.

---

## 🚀 Key Features

- **2-Stage Automated Pipeline**:
  - **Stage 1 (Transcript Saver & Reuser)**: Fetches YouTube transcript, translates Hindi/multilingual audio to English, attaches complete metadata (Title, Channel, Video URL, Thumbnail, Snippets), and saves to `output/transcripts/translated_transcript_<video_id>.txt`. If the transcript file already exists, it is reused directly on rerun without re-fetching.
  - **Stage 2 (AGY AI Analysis Engine)**: Feeds the pre-saved transcript to AGY CLI non-interactively (`agy --print`) to extract stock recommendations (Ticker, Action, Rating, Price, Stop Loss, Target, Horizon, Quote, Timestamp).

- **Strict Indian Market Focus (NSE & BSE)**:
  - Supports **2,570+ listed equities on NSE & BSE** plus major indices (`NIFTY 50`, `BANKNIFTY`, `SENSEX`).
  - Maps spoken Indian company aliases (e.g. "Tata Motors" $\rightarrow$ `TATAMOTORS`, "Policybazaar" $\rightarrow$ `PBFINTECH`, "State Bank" $\rightarrow$ `SBIN`, "Reliance" $\rightarrow$ `RELIANCE`, "Zomato" $\rightarrow$ `ZOMATO`).
  - Free live validation via Yahoo Finance Search API (`.NS` / `.BO`).

- **Custom Report Naming & Overwrite Behavior**:
  - Reports are saved in `output/reports/` named as `DD-MM-YY - <Video Title>.md`.
  - Automatically overwrites/rewrites existing report files on rerun.

---

## 💻 Quickstart

### 1. PowerShell (Windows)
```powershell
.\run_pipeline.ps1 -Url "https://youtu.be/4iM-AAsR1IU"
```

### 2. Bash (Linux / macOS)
```bash
./run_pipeline.sh "https://youtu.be/4iM-AAsR1IU"
```

### 3. Python Pipeline Execution
```bash
python pipeline.py "https://youtu.be/4iM-AAsR1IU" --method agy
```

### 4. Save Transcript Only
```bash
python save_transcript.py "https://youtu.be/4iM-AAsR1IU"
```

---

## 📂 Output Directory Structure

```text
stock_1/
├── output/
│   ├── transcripts/
│   │   └── translated_transcript_<video_id>.txt    # Formatted translated transcript
│   └── reports/
│       └── DD-MM-YY - <Video Title>.md              # Final AGY AI analysis report
├── stock_extractor/                                 # Core Python package
├── pipeline.py                                      # Python pipeline runner
├── save_transcript.py                              # Standalone transcript saver
├── run_pipeline.ps1                                 # PowerShell script
├── run_pipeline.sh                                  # Bash script
└── README.md                                        # Documentation
```

---

## 🧪 Testing

Run the automated test suite:
```bash
python -m unittest discover tests
```
