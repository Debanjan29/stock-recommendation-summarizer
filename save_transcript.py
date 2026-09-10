"""
Standalone script to store the final text after YouTube transcript is translated to English.
"""

import sys

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from stock_extractor.transcript_saver import fetch_and_save_translated_transcript

def main():
    if len(sys.argv) < 2:
        print("Usage: python save_transcript.py <YOUTUBE_URL_OR_ID> [OUTPUT_FILE]")
        sys.exit(1)

    url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Fetching and translating transcript for: {url}...")
    saved_path, meta = fetch_and_save_translated_transcript(url, output_path)

    print("\n============================================================")
    print("SUCCESS: TRANSLATED TRANSCRIPT SUCCESSFULLY SAVED!")
    print("============================================================")
    print(f"Title:       {meta.get('title')}")
    print(f"Channel:     {meta.get('channel')}")
    print(f"Saved File:  {saved_path}")
    print("============================================================\n")

if __name__ == "__main__":
    main()
