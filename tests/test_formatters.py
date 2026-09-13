"""
Unit tests for report formatters (Markdown, JSON, CSV, HTML).
"""

import unittest
import json
from stock_extractor.models import StockRecommendation, VideoReport
from stock_extractor.formatters import (
    format_markdown_report,
    format_json_report,
    format_csv_report,
    format_html_report
)

class TestFormatters(unittest.TestCase):

    def setUp(self):
        rec = StockRecommendation(
            ticker="AAPL",
            action="BUY",
            sector="Technology",
            analyst="Morgan Stanley",
            stop_loss="$150",
            target="$200",
            horizon="Short-term",
            source_quote="Buy Apple at 170 with stop loss 150 and target 200.",
            timestamp_seconds=252.0,
            timestamp_formatted="04:12",
            timestamp_url="https://youtu.be/dQw4w9WgXcQ?t=252"
        )
        self.report = VideoReport(
            video_id="dQw4w9WgXcQ",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="Top Stock Recommendations",
            channel="Finance Channel",
            extraction_method="Test Engine",
            recommendations=[rec]
        )

    def test_format_markdown(self):
        md = format_markdown_report(self.report)
        self.assertIn("# Stock Recommendations Report", md)
        self.assertIn("Top Stock Recommendations", md)
        self.assertIn("| **AAPL** | `BUY` | Technology | Morgan Stanley | $150 | $200 |", md)
        self.assertIn("[04:12](https://youtu.be/dQw4w9WgXcQ?t=252)", md)

    def test_format_json(self):
        json_str = format_json_report(self.report)
        data = json.loads(json_str)
        self.assertEqual(data["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(data["total_recommendations"], 1)
        self.assertEqual(data["recommendations"][0]["ticker"], "AAPL")
        self.assertEqual(data["recommendations"][0]["sector"], "Technology")
        self.assertEqual(data["recommendations"][0]["analyst"], "Morgan Stanley")

    def test_format_csv(self):
        csv_str = format_csv_report(self.report)
        self.assertIn("ticker,action,sector,analyst,stop_loss,target", csv_str)
        self.assertIn("AAPL,BUY,Technology,Morgan Stanley,$150,$200", csv_str)

    def test_format_html(self):
        html_str = format_html_report(self.report)
        self.assertIn("<!DOCTYPE html>", html_str)
        self.assertIn("AAPL", html_str)
        self.assertIn("Technology", html_str)
        self.assertIn("Morgan Stanley", html_str)
        self.assertIn("badge-buy", html_str)

    def test_hindi_sanitization_in_report(self):
        rec = StockRecommendation(
            ticker="RELIANCE",
            action="BUY",
            analyst="अनिल सिंघवी",
            stop_loss="Rs 1400",
            target="Rs 1600",
            horizon="Long-term",
            source_quote="रिलायंस में खरीदारी करें, बहुत मजबूत है।",
            timestamp_seconds=100.0,
            timestamp_formatted="01:40",
            timestamp_url="https://youtu.be/test?t=100"
        )
        report = VideoReport(
            video_id="test",
            video_url="https://www.youtube.com/watch?v=test",
            title="यहाँ रखें नजर!",
            channel="सुमित मेहरोत्रा",
            extraction_method="Test Engine",
            recommendations=[rec]
        )
        md = format_markdown_report(report)
        import re
        self.assertFalse(bool(re.search(r'[\u0900-\u097F]', md)), "Report markdown must not contain pure Devanagari Hindi characters")
        self.assertIn("RELIANCE", md)
        self.assertIn("khareedaaree", md.lower())

if __name__ == "__main__":
    unittest.main()
