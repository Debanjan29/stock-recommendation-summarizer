"""
Standalone script to run the 2-Stage Pipeline:
Stage 1: Checks for existing transcript file; reuses it if present, otherwise saves translated transcript.
Stage 2: Performs analysis with Gemini / AGY / LLM engine and saves report named 'DD-MM-YY - Video Caption.<ext>' (overwrites on rerun).
"""

import sys
import argparse
from typing import Optional

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from stock_extractor.pipeline import run_pipeline
from stock_extractor import formatters

def main():
    parser = argparse.ArgumentParser(
        description="Automated 2-Stage Pipeline: Reuse/Fetch transcript -> Analyze with AGY/Gemini/LLM -> Save report named 'DD-MM-YY - Video Title.<ext>' (rewritten on rerun)."
    )
    parser.add_argument("url", help="YouTube video URL or Video ID")
    parser.add_argument("-o", "--output-dir", default="output", help="Output directory for saved transcripts & reports (default: 'output')")
    parser.add_argument("-m", "--method", default="agy", help="Extraction engine: agy, auto, gemini, openai, anthropic, ollama, heuristic")
    parser.add_argument("--model", help="Specific LLM / AGY model name")
    parser.add_argument("--api-key", help="API key for Gemini, OpenAI, or Anthropic")
    parser.add_argument("-f", "--format", default="markdown", choices=["markdown", "json", "csv", "html"], help="Analysis report output format")

    args = parser.parse_args()

    print(f"\n============================================================")
    print(f" STARTING AUTOMATED 2-STAGE STOCK EXTRACTION PIPELINE")
    print(f" Video URL: {args.url}")
    print(f"============================================================")

    try:
        t_path, r_path, report, was_reused = run_pipeline(
            url_or_id=args.url,
            output_dir=args.output_dir,
            method=args.method,
            model=args.model,
            api_key=args.api_key,
            report_format=args.format
        )

        status_str = "REUSED EXISTING TRANSCRIPT" if was_reused else "FETCHED & TRANSLATED NEW TRANSCRIPT"
        print(f"\n[STAGE 1/2] {status_str}: {t_path}")
        print(f"[STAGE 2/2] GENERATED & OVERWROTE ANALYSIS REPORT: {r_path}")

        print("\n============================================================")
        print(" PIPELINE COMPLETED SUCCESSFULLY!")
        print("============================================================")
        print(f"1. Transcript File: {t_path}")
        print(f"2. Analysis Report: {r_path}")
        print(f"Total Recommendations Extracted: {len(report.recommendations)}")
        print("============================================================\n")

        # Render console report summary
        formatters.render_console_report(report)

    except Exception as e:
        print(f"\n[ERROR] Pipeline execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
