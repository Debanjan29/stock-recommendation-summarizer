"""
Automated tests for FastAPI endpoints, database models, and Excel exports.
"""

import unittest
from fastapi.testclient import TestClient

from app import app
from stock_extractor.db import init_db, get_session_factory, Video
from stock_extractor.exporters import export_excel, export_markdown, export_csv, export_json


class TestAPIAndExports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        SessionFactory = get_session_factory()
        with SessionFactory() as db:
            if db.query(Video).count() == 0:
                from stock_extractor.db import save_video_report
                from stock_extractor.models import StockRecommendation
                rec = StockRecommendation(
                    ticker="RELIANCE",
                    action="BUY",
                    sector="Oil, Gas & Fuels",
                    analyst="Top Analyst",
                    stop_loss="1200",
                    target="1400",
                    horizon="Short-term",
                    timestamp_formatted="01:30",
                    timestamp_url="https://youtu.be/test_seed_vid?t=90",
                    source_quote="Buy Reliance with target 1400"
                )
                save_video_report(
                    db,
                    video_id="test_seed_vid",
                    metadata={"title": "Test Video", "channel": "Test Channel"},
                    transcript_text="Test transcript",
                    recommendations=[rec],
                    engine_name="Test Engine"
                )
        cls.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_list_videos(self):
        response = self.client.get("/api/videos?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("videos", data)
        self.assertGreater(data["count"], 0)

    def test_get_single_video(self):
        # Retrieve the first video ID from the list
        list_resp = self.client.get("/api/videos?limit=1")
        self.assertEqual(list_resp.status_code, 200)
        videos = list_resp.json()["videos"]
        if videos:
            vid = videos[0]["video_id"]
            resp = self.client.get(f"/api/videos/{vid}")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["video_id"], vid)
            self.assertIn("recommendations", data)
            for r in data["recommendations"]:
                self.assertIn("sector", r)
                self.assertTrue(len(r["sector"]) > 0)

    def test_excel_export(self):
        list_resp = self.client.get("/api/videos?limit=1")
        videos = list_resp.json()["videos"]
        if videos:
            vid = videos[0]["video_id"]
            resp = self.client.get(f"/api/export/{vid}?format=xlsx")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.headers["content-type"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            self.assertGreater(len(resp.content), 1000)

    def test_markdown_export(self):
        list_resp = self.client.get("/api/videos?limit=1")
        videos = list_resp.json()["videos"]
        if videos:
            vid = videos[0]["video_id"]
            resp = self.client.get(f"/api/export/{vid}?format=md")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("# Stock Recommendations Report", resp.text)
            self.assertIn("Sector", resp.text)

    def test_stock_history_lookup(self):
        resp = self.client.get("/api/stocks/RELIANCE")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticker"], "RELIANCE")
        self.assertIn("recommendations", data)

    def test_sector_identification(self):
        from stock_extractor.sectors import get_stock_sector
        self.assertEqual(get_stock_sector("RELIANCE"), "Oil, Gas & Fuels")
        self.assertEqual(get_stock_sector("TATAMOTORS"), "Automobile & Ancillary")
        self.assertEqual(get_stock_sector("HDFCBANK"), "Banking & Financial Services")
        self.assertEqual(get_stock_sector("INFY"), "Information Technology")
        self.assertEqual(get_stock_sector("HAL"), "Aerospace & Defense")
        self.assertEqual(get_stock_sector("COALINDIA"), "Metals & Mining")

    def test_exporters_with_sector(self):
        mock_data = {
            "video_id": "mock_vid",
            "title": "Mock Video",
            "channel": "Mock Channel",
            "recommendations": [
                {
                    "ticker": "TATAMOTORS",
                    "action": "BUY",
                    "sector": "Automobile & Ancillary",
                    "analyst": "Expert",
                    "stop_loss": "900",
                    "target": "1100",
                    "horizon": "Short-term",
                    "timestamp_formatted": "01:00",
                    "timestamp_url": "https://youtu.be/mock_vid?t=60",
                    "source_quote": "Buy Tata Motors"
                }
            ]
        }
        md = export_markdown(mock_data)
        self.assertIn("Automobile & Ancillary", md)
        self.assertIn("| Ticker | Action | Sector |", md)

        csv_str = export_csv(mock_data)
        self.assertIn("Ticker,Action,Sector,Analyst", csv_str)
        self.assertIn("Automobile & Ancillary", csv_str)

        xlsx_bytes = export_excel(mock_data)
        self.assertGreater(len(xlsx_bytes), 1000)

    def test_stock_quote_endpoint(self):
        resp = self.client.get("/api/stocks/RELIANCE/quote")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticker"], "RELIANCE")
        self.assertIn("cmp", data)
        self.assertIn("pe_ratio", data)
        self.assertIn("market_cap_cr", data)
        self.assertIn("sparkline", data)
        self.assertIn("sector", data)
        self.assertEqual(data["sector"], "Oil, Gas & Fuels")

    def test_storage_stats_endpoint(self):
        resp = self.client.get("/api/system/storage")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("free_tier_limit_mb", data)
        self.assertEqual(data["free_tier_limit_mb"], 500.0)
        self.assertIn("total_used_mb", data)
        self.assertIn("free_tier_percent_used", data)
        self.assertIn("retention_days", data)
        self.assertEqual(data["retention_days"], 15)

    def test_storage_prune_endpoint(self):
        resp = self.client.post("/api/system/prune?days=30")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["retention_days"], 30)


if __name__ == "__main__":
    unittest.main()
