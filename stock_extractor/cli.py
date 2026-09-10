"""
CLI interface for YouTube Stock Recommendation Extractor, Transcript Saver, and AGY AI Pipeline.
"""

import sys
import os
from typing import Optional
import typer
from rich.console import Console
from rich.status import Status

from stock_extractor.youtube import fetch_transcript
from stock_extractor.utils import chunk_transcript, parse_youtube_id
from stock_extractor.extractors import get_extractor
from stock_extractor.models import VideoReport
from stock_extractor import formatters
from stock_extractor.transcript_saver import fetch_and_save_translated_transcript
from stock_extractor.pipeline import run_pipeline

app = typer.Typer(
    name="stock-yt",
    help="Extract structured stock recommendations (ticker, action, stop-loss, target, horizon, quote, timestamp) from YouTube videos.",
    add_completion=False
)

console = Console()

@app.command("extract")
def extract(
    url: str = typer.Argument(..., help="YouTube video URL or Video ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="File path to save the generated report"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: table, markdown, json, csv, html"),
    method: str = typer.Option("auto", "--method", "-m", help="Extraction engine: auto, agy, gemini, openai, anthropic, ollama, heuristic"),
    model: Optional[str] = typer.Option(None, "--model", help="Specific LLM / AGY model name"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for OpenAI, Gemini, or Anthropic"),
    ollama_url: Optional[str] = typer.Option(None, "--ollama-url", help="Base URL for local Ollama/OpenAI-compatible server"),
    lang: str = typer.Option("en,hi,es,fr", "--lang", "-l", help="Comma-separated transcript language preferences"),
    save_transcript: bool = typer.Option(False, "--save-transcript", help="Save final translated transcript text to a file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress status spinner and headers")
):
    """
    Extract stock recommendations from a YouTube video URL and output a structured report.
    """
    video_id = parse_youtube_id(url)
    if not video_id:
        console.print(f"[bold red]Error:[/bold red] Invalid YouTube URL or Video ID: '{url}'")
        raise typer.Exit(code=1)

    languages = [l.strip() for l in lang.split(",") if l.strip()]

    # 1. Fetch transcript and metadata
    if not quiet:
        with Status(f"[bold cyan]Fetching transcript for video ID '{video_id}'...", console=console):
            try:
                snippets, metadata = fetch_transcript(url, languages=languages)
            except Exception as e:
                console.print(f"[bold red]Error fetching transcript:[/bold red] {e}")
                raise typer.Exit(code=1)
    else:
        try:
            snippets, metadata = fetch_transcript(url, languages=languages)
        except Exception as e:
            sys.stderr.write(f"Error fetching transcript: {e}\n")
            raise typer.Exit(code=1)

    if not snippets:
        console.print(f"[bold yellow]Warning:[/bold yellow] Transcript is empty for video '{video_id}'.")
        raise typer.Exit(code=0)

    # Optionally save translated transcript text
    if save_transcript:
        t_path = f"translated_transcript_{video_id}.txt"
        with open(t_path, "w", encoding="utf-8") as tf:
            tf.write(f"Title: {metadata.get('title')}\nChannel: {metadata.get('channel')}\n\n")
            for s in snippets:
                tf.write(f"[{s.get('start', 0.0):.1f}s] {s.get('text', '')}\n")
        if not quiet:
            console.print(f"[bold green]✓ Translated transcript saved to:[/bold green] {t_path}")

    # 2. Chunk transcript
    chunks = chunk_transcript(snippets, max_duration=60.0, max_words=300)

    # 3. Instantiate Extractor Engine (AGY AI by default)
    try:
        extractor = get_extractor(method=method, api_key=api_key, model=model, ollama_url=ollama_url)
    except Exception as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 4. Extract stock recommendations
    if not quiet:
        with Status(f"[bold cyan]Extracting stock recommendations using {extractor.name}...", console=console):
            recommendations = extractor.extract(chunks, video_id)
    else:
        recommendations = extractor.extract(chunks, video_id)

    # 5. Build Report Object
    report = VideoReport(
        video_id=video_id,
        video_url=metadata.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
        title=metadata.get("title", f"YouTube Video ({video_id})"),
        channel=metadata.get("channel", "Unknown Channel"),
        thumbnail_url=metadata.get("thumbnail_url", ""),
        extraction_method=extractor.name,
        recommendations=recommendations
    )

    # 6. Determine Output Format
    target_format = format
    if not target_format and output:
        ext = os.path.splitext(output)[1].lower()
        if ext in ['.md', '.markdown']:
            target_format = 'markdown'
        elif ext == '.json':
            target_format = 'json'
        elif ext == '.csv':
            target_format = 'csv'
        elif ext in ['.html', '.htm']:
            target_format = 'html'

    if not target_format:
        target_format = 'table'

    target_format = target_format.lower()

    # 7. Render or Save Output
    formatted_content = ""
    if target_format == 'markdown':
        formatted_content = formatters.format_markdown_report(report)
    elif target_format == 'json':
        formatted_content = formatters.format_json_report(report)
    elif target_format == 'csv':
        formatted_content = formatters.format_csv_report(report)
    elif target_format == 'html':
        formatted_content = formatters.format_html_report(report)
    elif target_format == 'table':
        formatters.render_console_report(report)
    else:
        console.print(f"[bold red]Error:[/bold red] Unsupported format '{target_format}'. Choose from table, markdown, json, csv, html.")
        raise typer.Exit(code=1)

    if output and formatted_content:
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        if not quiet:
            console.print(f"[bold green]✓ Report successfully saved to:[/bold green] {output}")
    elif formatted_content and target_format != 'table':
        print(formatted_content)

@app.command("transcript")
def transcript_cmd(
    url: str = typer.Argument(..., help="YouTube video URL or Video ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="File path to save the translated transcript text")
):
    """
    Fetch, translate (if non-English), and save the complete YouTube transcript with metadata to a text file.
    """
    with Status(f"[bold cyan]Fetching and translating transcript for '{url}'...", console=console):
        try:
            saved_path, meta = fetch_and_save_translated_transcript(url, output)
            console.print(f"[bold green]✓ Translated transcript successfully saved to:[/bold green] {saved_path}")
            console.print(f"Title:   [bold cyan]{meta.get('title')}[/bold cyan]")
            console.print(f"Channel: [bold cyan]{meta.get('channel')}[/bold cyan]")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)

@app.command("pipeline")
def pipeline_cmd(
    url: str = typer.Argument(..., help="YouTube video URL or Video ID"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for saved transcripts & reports"),
    method: str = typer.Option("agy", "--method", "-m", help="Extraction engine: agy, auto, gemini, openai, anthropic, ollama, heuristic"),
    model: Optional[str] = typer.Option(None, "--model", help="Specific LLM / AGY model name"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for Gemini, OpenAI, or Anthropic"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json, csv, html")
):
    """
    Automated 2-Stage AGY Pipeline: Save translated transcript file with metadata -> Analyze with AGY AI CLI -> Save analysis report.
    """
    with Status(f"[bold cyan]Running AGY automated pipeline for '{url}'...", console=console):
        try:
            t_path, r_path, report, was_reused = run_pipeline(
                url_or_id=url,
                output_dir=output_dir,
                method=method,
                model=model,
                api_key=api_key,
                report_format=format
            )
            stage1_msg = "Reused pre-saved transcript" if was_reused else "Fetched & saved new transcript"
            console.print(f"[bold green]✓ Stage 1 Complete ({stage1_msg}):[/bold green] [cyan]{t_path}[/cyan]")
            console.print(f"[bold green]✓ Stage 2 Complete (Overwrote report):[/bold green] [cyan]{r_path}[/cyan]")
            formatters.render_console_report(report)
        except Exception as e:
            console.print(f"[bold red]Pipeline Error:[/bold red] {e}")
            raise typer.Exit(code=1)

def main():
    app()

if __name__ == "__main__":
    main()
