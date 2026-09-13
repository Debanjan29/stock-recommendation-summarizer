"""
Output formatters for terminal display, Markdown, JSON, CSV, and HTML reports.
"""

import csv
import json
import io
import shutil
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from stock_extractor.models import VideoReport
from stock_extractor.transliteration import ensure_no_pure_hindi

console = Console(width=max(shutil.get_terminal_size((135, 24)).columns, 135))

def render_console_report(report: VideoReport) -> None:
    """Render a beautiful colored report in the terminal using Rich."""
    safe_title = ensure_no_pure_hindi(report.title)
    safe_channel = ensure_no_pure_hindi(report.channel)
    panel_text = (
        f"[bold blue]Title:[/bold blue] {safe_title}\n"
        f"[bold blue]Channel:[/bold blue] {safe_channel}\n"
        f"[bold blue]URL:[/bold blue] {report.video_url}\n"
        f"[bold blue]Method:[/bold blue] {report.extraction_method}\n"
        f"[bold blue]Recommendations Found:[/bold blue] [bold green]{len(report.recommendations)}[/bold green]"
    )
    console.print(Panel(panel_text, title="[bold gold1]YouTube Stock Recommendation Report[/bold gold1]", expand=False))
    
    if not report.recommendations:
        console.print("[yellow]No explicit stock recommendations detected in video transcript.[/yellow]")
        return
        
    table = Table(title="Stock Recommendations", show_header=True, header_style="bold magenta")
    table.add_column("Ticker", style="bold cyan", no_wrap=True)
    table.add_column("Action", justify="center", no_wrap=True)
    table.add_column("Sector", style="magenta")
    table.add_column("Analyst / Firm", style="yellow")
    table.add_column("Stop-Loss", style="red", no_wrap=True)
    table.add_column("Target", style="green")
    table.add_column("Horizon", style="blue")
    table.add_column("Time", style="dim", justify="center", no_wrap=True)
    table.add_column("Source Quote", style="italic", max_width=40)
    
    for rec in report.recommendations:
        action_upper = rec.action.upper()
        if "BUY" in action_upper:
            action_style = "[bold green]BUY[/bold green]"
        elif "SELL" in action_upper:
            action_style = "[bold red]SELL[/bold red]"
        elif "HOLD" in action_upper:
            action_style = "[bold yellow]HOLD[/bold yellow]"
        elif "AVOID" in action_upper:
            action_style = "[bold magenta]AVOID[/bold magenta]"
        else:
            action_style = f"[cyan]{rec.action}[/cyan]"
            
        timestamp_display = f"[link={rec.timestamp_url}]{rec.timestamp_formatted}[/link]" if rec.timestamp_url else rec.timestamp_formatted
        safe_quote = ensure_no_pure_hindi(rec.source_quote)
        sector_val = ensure_no_pure_hindi(getattr(rec, "sector", "Diversified / Other"))
        
        table.add_row(
            ensure_no_pure_hindi(rec.ticker),
            action_style,
            sector_val,
            ensure_no_pure_hindi(rec.analyst),
            ensure_no_pure_hindi(rec.stop_loss),
            ensure_no_pure_hindi(rec.target),
            ensure_no_pure_hindi(rec.horizon),
            timestamp_display,
            safe_quote
        )
        
    console.print(table)


def format_markdown_report(report: VideoReport) -> str:
    """Format report as GitHub-Flavored Markdown."""
    safe_title = ensure_no_pure_hindi(report.title)
    safe_channel = ensure_no_pure_hindi(report.channel)
    lines = [
        f"# Stock Recommendations Report",
        f"",
        f"- **Video Title:** [{safe_title}]({report.video_url})",
        f"- **Channel:** {safe_channel}",
        f"- **Extraction Engine:** {report.extraction_method}",
        f"- **Total Recommendations:** {len(report.recommendations)}",
        f"- **Generated At:** {report.timestamp_generated}",
        f"",
        f"## Summary Table",
        f"",
        f"| Ticker | Action | Sector | Analyst / Firm | Stop-Loss | Target | Horizon | Timestamp | Source Quote |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for rec in report.recommendations:
        ts_link = f"[{rec.timestamp_formatted}]({rec.timestamp_url})" if rec.timestamp_url else rec.timestamp_formatted
        safe_quote = ensure_no_pure_hindi(rec.source_quote)
        quote_clean = safe_quote.replace("|", "\\|").replace("\n", " ")
        sector_val = ensure_no_pure_hindi(getattr(rec, "sector", "Diversified / Other"))
        lines.append(f"| **{ensure_no_pure_hindi(rec.ticker)}** | `{rec.action}` | {sector_val} | {ensure_no_pure_hindi(rec.analyst)} | {ensure_no_pure_hindi(rec.stop_loss)} | {ensure_no_pure_hindi(rec.target)} | {ensure_no_pure_hindi(rec.horizon)} | {ts_link} | {quote_clean} |")
        
    lines.append("")
    lines.append("## Detailed Breakdown")
    lines.append("")
    
    for idx, rec in enumerate(report.recommendations, 1):
        ts_link = f"[{rec.timestamp_formatted}]({rec.timestamp_url})" if rec.timestamp_url else rec.timestamp_formatted
        safe_quote = ensure_no_pure_hindi(rec.source_quote)
        sector_val = ensure_no_pure_hindi(getattr(rec, "sector", "Diversified / Other"))
        lines.append(f"### {idx}. {ensure_no_pure_hindi(rec.ticker)} - `{rec.action}`")
        lines.append(f"- **Sector:** {sector_val}")
        lines.append(f"- **Analyst / Firm:** {ensure_no_pure_hindi(rec.analyst)}")
        lines.append(f"- **Stop-Loss:** {ensure_no_pure_hindi(rec.stop_loss)}")
        lines.append(f"- **Target Price:** {ensure_no_pure_hindi(rec.target)}")
        lines.append(f"- **Horizon:** {ensure_no_pure_hindi(rec.horizon)}")
        lines.append(f"- **Timestamp:** {ts_link}")
        lines.append(f"- **Context Quote:**")
        lines.append(f"> \"{safe_quote}\"")
        lines.append("")
        
    return "\n".join(lines)


def format_json_report(report: VideoReport) -> str:
    """Format report as pretty JSON string."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def format_csv_report(report: VideoReport) -> str:
    """Format report as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ticker", "action", "sector", "analyst", "stop_loss", "target", "horizon", 
        "timestamp_formatted", "timestamp_seconds", "timestamp_url", "source_quote"
    ])
    
    for rec in report.recommendations:
        sector_val = getattr(rec, "sector", "Diversified / Other")
        writer.writerow([
            rec.ticker, rec.action, sector_val, rec.analyst, rec.stop_loss, rec.target, rec.horizon,
            rec.timestamp_formatted, rec.timestamp_seconds, rec.timestamp_url, rec.source_quote
        ])
        
    return output.getvalue()


def format_html_report(report: VideoReport) -> str:
    """Format report as a self-contained styled HTML report."""
    rows_html = []
    for rec in report.recommendations:
        action_cls = "badge-buy" if "BUY" in rec.action.upper() else ("badge-sell" if "SELL" in rec.action.upper() else "badge-other")
        ts_html = f'<a href="{rec.timestamp_url}" target="_blank" class="timestamp-link">{rec.timestamp_formatted} 🔗</a>' if rec.timestamp_url else rec.timestamp_formatted
        sector_val = getattr(rec, "sector", "Diversified / Other")
        rows_html.append(f"""
        <tr>
            <td class="ticker">{rec.ticker}</td>
            <td><span class="badge {action_cls}">{rec.action}</span></td>
            <td><span class="badge badge-other">{sector_val}</span></td>
            <td>{rec.analyst}</td>
            <td>{rec.stop_loss}</td>
            <td>{rec.target}</td>
            <td>{rec.horizon}</td>
            <td>{ts_html}</td>
            <td class="quote">"{rec.source_quote}"</td>
        </tr>
        """)
        
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Report - {report.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h1 {{ color: #38bdf8; font-size: 1.8rem; margin-top: 0; }}
        .meta {{ display: flex; gap: 1.5rem; background: #334155; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; flex-wrap: wrap; }}
        .meta-item {{ font-size: 0.95rem; }}
        .meta-item strong {{ color: #94a3b8; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #38bdf8; font-weight: 600; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 0.05em; }}
        tr:hover {{ background: #334155; }}
        .ticker {{ font-weight: bold; color: #38bdf8; font-size: 1.1rem; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 0.8rem; text-transform: uppercase; }}
        .badge-buy {{ background: #166534; color: #4ade80; }}
        .badge-sell {{ background: #991b1b; color: #fca5a5; }}
        .badge-other {{ background: #854d0e; color: #fef08a; }}
        .timestamp-link {{ color: #38bdf8; text-decoration: none; font-weight: 500; }}
        .timestamp-link:hover {{ text-decoration: underline; }}
        .quote {{ font-style: italic; color: #cbd5e1; font-size: 0.9rem; max-width: 400px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 YouTube Stock Recommendation Report</h1>
        <div class="meta">
            <div class="meta-item"><strong>Title:</strong> <a href="{report.video_url}" target="_blank" style="color: #38bdf8;">{report.title}</a></div>
            <div class="meta-item"><strong>Channel:</strong> {report.channel}</div>
            <div class="meta-item"><strong>Engine:</strong> {report.extraction_method}</div>
            <div class="meta-item"><strong>Recommendations Found:</strong> {len(report.recommendations)}</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Action</th>
                    <th>Sector</th>
                    <th>Analyst / Firm</th>
                    <th>Stop-Loss</th>
                    <th>Target</th>
                    <th>Horizon</th>
                    <th>Timestamp</th>
                    <th>Source Quote</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    return html_content
