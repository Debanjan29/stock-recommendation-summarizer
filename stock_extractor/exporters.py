"""
Export utilities for generating Markdown, styled Excel (.xlsx), CSV, and JSON files from Video data.
"""

import io
import csv
import json
from typing import Dict, Any, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from stock_extractor.transliteration import ensure_no_pure_hindi


def export_markdown(video_data: Dict[str, Any]) -> str:
    """Generate GitHub-Flavored Markdown report with header metadata and formatted tables."""
    title = ensure_no_pure_hindi(video_data.get("title", "YouTube Video"))
    channel = ensure_no_pure_hindi(video_data.get("channel", "Unknown Channel"))
    url = video_data.get("video_url", "")
    engine = video_data.get("extraction_engine", "Gemini 2.5 Flash")
    recs = video_data.get("recommendations", [])
    created = video_data.get("created_at", "")

    lines = [
        f"# Stock Recommendations Report",
        f"",
        f"- **Video Title:** [{title}]({url})",
        f"- **Channel:** {channel}",
        f"- **Extraction Engine:** {engine}",
        f"- **Total Recommendations:** {len(recs)}",
        f"- **Generated At:** {created}",
        f"",
        f"## Summary Table",
        f"",
        f"| Ticker | Action | Sector | Analyst / Firm | Stop-Loss | Target | Horizon | Timestamp | Source Quote |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]

    for rec in recs:
        ticker = ensure_no_pure_hindi(rec.get("ticker", ""))
        action = ensure_no_pure_hindi(rec.get("action", "WATCH"))
        sector = ensure_no_pure_hindi(rec.get("sector", "Diversified / Other"))
        analyst = ensure_no_pure_hindi(rec.get("analyst", "N/A"))
        sl = ensure_no_pure_hindi(rec.get("stop_loss", "N/A"))
        target = ensure_no_pure_hindi(rec.get("target", "N/A"))
        horizon = ensure_no_pure_hindi(rec.get("horizon", "N/A"))
        ts_fmt = rec.get("timestamp_formatted", "00:00")
        ts_url = rec.get("timestamp_url", "")
        ts_link = f"[{ts_fmt}]({ts_url})" if ts_url else ts_fmt
        quote = ensure_no_pure_hindi(rec.get("source_quote", "")).replace("|", "\\|").replace("\n", " ")

        lines.append(f"| **{ticker}** | `{action}` | {sector} | {analyst} | {sl} | {target} | {horizon} | {ts_link} | {quote} |")

    lines.append("")
    lines.append("## Detailed Analyst Insights")
    lines.append("")

    for idx, rec in enumerate(recs, 1):
        ticker = ensure_no_pure_hindi(rec.get("ticker", ""))
        action = ensure_no_pure_hindi(rec.get("action", "WATCH"))
        sector = ensure_no_pure_hindi(rec.get("sector", "Diversified / Other"))
        analyst = ensure_no_pure_hindi(rec.get("analyst", "N/A"))
        sl = ensure_no_pure_hindi(rec.get("stop_loss", "N/A"))
        target = ensure_no_pure_hindi(rec.get("target", "N/A"))
        horizon = ensure_no_pure_hindi(rec.get("horizon", "N/A"))
        ts_fmt = rec.get("timestamp_formatted", "00:00")
        ts_url = rec.get("timestamp_url", "")
        quote = ensure_no_pure_hindi(rec.get("source_quote", ""))

        lines.append(f"### {idx}. {ticker} - `{action}`")
        lines.append(f"- **Sector:** {sector}")
        lines.append(f"- **Analyst / Firm:** {analyst}")
        lines.append(f"- **Stop-Loss:** {sl}")
        lines.append(f"- **Target Price:** {target}")
        lines.append(f"- **Horizon:** {horizon}")
        lines.append(f"- **Timestamp:** [{ts_fmt}]({ts_url})")
        lines.append(f"- **Context Quote:**")
        lines.append(f"> \"{quote}\"")
        lines.append("")

    return "\n".join(lines)


def export_excel(video_data: Dict[str, Any]) -> bytes:
    """
    Generate a styled Excel workbook (.xlsx) with:
    - Branded dark-navy header.
    - Soft color-coded fills for Actions (Buy = Light Green, Sell/Avoid = Soft Red, Hold = Soft Amber).
    - Working clickable hyperlinks to YouTube timestamps.
    - Auto-adjusted column widths.
    - Secondary sheet with Video Details.
    """
    wb = openpyxl.Workbook()

    # -------------------------------------------------------------
    # Sheet 1: Recommendations
    # -------------------------------------------------------------
    ws_recs = wb.active
    ws_recs.title = "Stock Recommendations"
    ws_recs.views.sheetView[0].showGridLines = True

    # Header styling
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Slate 800
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "Ticker", "Action", "Sector", "Analyst / Firm", "Stop-Loss", 
        "Target Price", "Horizon", "Timestamp", "Context Quote", "YouTube Link"
    ]

    ws_recs.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws_recs.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws_recs.row_dimensions[1].height = 28

    # Style colors for Actions
    buy_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")     # Soft green
    buy_font = Font(name="Segoe UI", size=10, bold=True, color="166534")
    sell_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")   # Soft red
    sell_font = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
    hold_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")   # Soft amber
    hold_font = Font(name="Segoe UI", size=10, bold=True, color="92400E")
    link_font = Font(name="Segoe UI", size=10, color="2563EB", underline="single")
    default_font = Font(name="Segoe UI", size=10)

    recs = video_data.get("recommendations", [])
    row_idx = 2

    for r in recs:
        ticker = ensure_no_pure_hindi(r.get("ticker", ""))
        action = ensure_no_pure_hindi(r.get("action", "WATCH")).upper()
        sector = ensure_no_pure_hindi(r.get("sector", "Diversified / Other"))
        analyst = ensure_no_pure_hindi(r.get("analyst", "N/A"))
        sl = ensure_no_pure_hindi(r.get("stop_loss", "N/A"))
        target = ensure_no_pure_hindi(r.get("target", "N/A"))
        horizon = ensure_no_pure_hindi(r.get("horizon", "N/A"))
        ts_fmt = r.get("timestamp_formatted", "00:00")
        ts_url = r.get("timestamp_url", "")
        quote = ensure_no_pure_hindi(r.get("source_quote", ""))

        row_data = [ticker, action, sector, analyst, sl, target, horizon, ts_fmt, quote, ts_url]
        ws_recs.append(row_data)

        # Style ticker
        c_ticker = ws_recs.cell(row=row_idx, column=1)
        c_ticker.font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
        c_ticker.alignment = Alignment(horizontal="center", vertical="center")
        c_ticker.border = thin_border

        # Style action with badges
        c_action = ws_recs.cell(row=row_idx, column=2)
        c_action.alignment = Alignment(horizontal="center", vertical="center")
        c_action.border = thin_border
        if any(b in action for b in ["BUY", "ACCUMULATE"]):
            c_action.fill = buy_fill
            c_action.font = buy_font
        elif any(s in action for s in ["SELL", "AVOID"]):
            c_action.fill = sell_fill
            c_action.font = sell_font
        else:
            c_action.fill = hold_fill
            c_action.font = hold_font

        # Style other columns (Sector, Analyst, Stop Loss, Target, Horizon)
        for c_idx in range(3, 8):
            cell = ws_recs.cell(row=row_idx, column=c_idx)
            cell.font = default_font
            cell.alignment = Alignment(horizontal="left" if c_idx == 4 else "center", vertical="center")
            cell.border = thin_border

        # Timestamp link
        c_ts = ws_recs.cell(row=row_idx, column=8)
        c_ts.alignment = Alignment(horizontal="center", vertical="center")
        c_ts.border = thin_border
        if ts_url:
            c_ts.hyperlink = ts_url
            c_ts.font = link_font

        # Quote
        c_quote = ws_recs.cell(row=row_idx, column=9)
        c_quote.font = Font(name="Segoe UI", size=9, italic=True, color="475569")
        c_quote.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        c_quote.border = thin_border

        # Direct link
        c_link = ws_recs.cell(row=row_idx, column=10)
        c_link.border = thin_border
        if ts_url:
            c_link.hyperlink = ts_url
            c_link.font = link_font

        ws_recs.row_dimensions[row_idx].height = 24
        row_idx += 1

    # Auto-fit column widths
    col_widths = {1: 16, 2: 14, 3: 20, 4: 20, 5: 15, 6: 18, 7: 18, 8: 12, 9: 45, 10: 25}
    for col_idx, width in col_widths.items():
        ws_recs.column_dimensions[get_column_letter(col_idx)].width = width

    # -------------------------------------------------------------
    # Sheet 2: Video Metadata
    # -------------------------------------------------------------
    ws_meta = wb.create_sheet(title="Video Details")
    ws_meta.views.sheetView[0].showGridLines = True

    meta_items = [
        ("Video Title", ensure_no_pure_hindi(video_data.get("title", ""))),
        ("Channel Name", ensure_no_pure_hindi(video_data.get("channel", ""))),
        ("YouTube URL", video_data.get("video_url", "")),
        ("Extraction Engine", video_data.get("extraction_engine", "")),
        ("Total Recommendations", len(recs)),
        ("Date Analyzed", video_data.get("created_at", "")),
        ("Thumbnail URL", video_data.get("thumbnail_url", ""))
    ]

    ws_meta.append(["Property", "Value"])
    ws_meta.cell(row=1, column=1).font = header_font
    ws_meta.cell(row=1, column=1).fill = header_fill
    ws_meta.cell(row=1, column=2).font = header_font
    ws_meta.cell(row=1, column=2).fill = header_fill

    for r_idx, (prop, val) in enumerate(meta_items, 2):
        ws_meta.append([prop, str(val)])
        c1 = ws_meta.cell(row=r_idx, column=1)
        c1.font = Font(name="Segoe UI", size=10, bold=True)
        c1.border = thin_border
        c2 = ws_meta.cell(row=r_idx, column=2)
        c2.font = default_font
        c2.border = thin_border
        if "http" in str(val):
            c2.hyperlink = str(val)
            c2.font = link_font

    ws_meta.column_dimensions["A"].width = 25
    ws_meta.column_dimensions["B"].width = 65

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_csv(video_data: Dict[str, Any]) -> str:
    """Generate clean CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticker", "Action", "Sector", "Analyst", "Stop Loss", "Target Price", 
        "Horizon", "Timestamp", "Timestamp URL", "Source Quote"
    ])

    for r in video_data.get("recommendations", []):
        writer.writerow([
            ensure_no_pure_hindi(r.get("ticker", "")),
            ensure_no_pure_hindi(r.get("action", "WATCH")),
            ensure_no_pure_hindi(r.get("sector", "Diversified / Other")),
            ensure_no_pure_hindi(r.get("analyst", "N/A")),
            ensure_no_pure_hindi(r.get("stop_loss", "N/A")),
            ensure_no_pure_hindi(r.get("target", "N/A")),
            ensure_no_pure_hindi(r.get("horizon", "N/A")),
            r.get("timestamp_formatted", "00:00"),
            r.get("timestamp_url", ""),
            ensure_no_pure_hindi(r.get("source_quote", ""))
        ])

    return output.getvalue()


def export_json(video_data: Dict[str, Any]) -> str:
    """Generate formatted JSON report string."""
    return json.dumps(video_data, indent=2, ensure_ascii=False)
