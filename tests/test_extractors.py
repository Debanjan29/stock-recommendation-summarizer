"""
Unit tests for Indian stock recommendation extractors.
"""

import unittest
from stock_extractor.extractors.heuristic import HeuristicExtractor
from stock_extractor.extractors.llm_base import parse_llm_json_response
from stock_extractor.extractors import get_extractor
from stock_extractor.indian_market import indian_market_manager

class TestExtractors(unittest.TestCase):

    def setUp(self):
        self.extractor = HeuristicExtractor()
        self.video_id = "test_vid_123"

    def test_heuristic_indian_buy_recommendation(self):
        chunks = [{
            'start': 150.0,
            'duration': 30.0,
            'text': "I am very bullish on Tata Motors. Buy TATAMOTORS near 950 with a stop loss at 920 and target 1100. Short term trade."
        }]
        
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertGreaterEqual(len(recs), 1)
        
        rec = recs[0]
        self.assertEqual(rec.ticker, "TATAMOTORS")
        self.assertEqual(rec.action, "BUY")
        self.assertIn("920", rec.stop_loss)
        self.assertIn("1100", rec.target)
        self.assertEqual(rec.timestamp_formatted, "02:30")
        self.assertIn("https://youtu.be/test_vid_123?t=150", rec.timestamp_url)

    def test_heuristic_indian_sell_recommendation(self):
        chunks = [{
            'start': 300.0,
            'duration': 20.0,
            'text': "Zomato is breaking down. Sell ZOMATO here. Stop loss is 240 and price target is 200."
        }]
        
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertGreaterEqual(len(recs), 1)
        
        rec = recs[0]
        self.assertEqual(rec.ticker, "ZOMATO")
        self.assertEqual(rec.action, "SELL")
        self.assertIn("240", rec.stop_loss)
        self.assertIn("200", rec.target)

    def test_heuristic_indian_spoken_alias(self):
        chunks = [{
            'start': 450.0,
            'duration': 25.0,
            'text': "Buy Reliance Industries for long term. Target is 3200 and stop loss at 2850."
        }]
        
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertGreaterEqual(len(recs), 1)
        
        rec = recs[0]
        self.assertEqual(rec.ticker, "RELIANCE")
        self.assertEqual(rec.action, "BUY")
        self.assertIn("2850", rec.stop_loss)
        self.assertIn("3200", rec.target)

    def test_filter_non_indian_stocks(self):
        # US stocks like AAPL should be filtered out when only Indian stocks are requested
        chunks = [{
            'start': 100.0,
            'duration': 20.0,
            'text': "Buy AAPL Apple at 170 stop loss 150."
        }]
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertEqual(len(recs), 0)

    def test_llm_json_parser_indian_stocks(self):
        json_str = """```json
        [
          {
            "ticker": "TATAMOTORS",
            "action": "BUY",
            "stop_loss": "Rs 920",
            "target": "Rs 1100",
            "horizon": "Short-term",
            "source_quote": "Tata Motors looks strong, buy with stop loss at 920 and target 1100.",
            "timestamp_seconds": 125.0
          }
        ]
        ```"""
        
        recs = parse_llm_json_response(json_str, self.video_id)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].ticker, "TATAMOTORS")
        self.assertEqual(recs[0].action, "BUY")
        self.assertEqual(recs[0].stop_loss, "Rs 920")
        self.assertEqual(recs[0].target, "Rs 1100")

    def test_indian_market_manager_lookup(self):
        self.assertTrue(indian_market_manager.is_indian_stock("RELIANCE"))
        self.assertTrue(indian_market_manager.is_indian_stock("SBIN"))
        self.assertTrue(indian_market_manager.is_indian_stock("NIFTY 50"))
        resolved = indian_market_manager.resolve_ticker("state bank of india")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved[0], "SBIN")

    def test_reject_common_english_words_collisions(self):
        # Bare common English words MUST NOT match as Indian stock tickers
        self.assertIsNone(indian_market_manager.resolve_ticker("dollar"))
        self.assertIsNone(indian_market_manager.resolve_ticker("take"))
        self.assertIsNone(indian_market_manager.resolve_ticker("fact"))
        self.assertIsNone(indian_market_manager.resolve_ticker("idea"))
        
        chunks = [{
            'start': 100.0,
            'duration': 20.0,
            'text': "The rupee rose against the dollar today. In fact we should take this as a good idea."
        }]
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertEqual(len(recs), 0)

    def test_no_inverted_sell_on_selling_agents(self):
        # 'selling agents' or 'selling products' must not trigger a SELL call
        chunks = [{
            'start': 60.0,
            'duration': 30.0,
            'text': "Our view on Turtlemint is very positive. The scope of small policy selling agents is limited, but Turtlemint has high long term upside."
        }]
        recs = self.extractor.extract(chunks, self.video_id)
        for rec in recs:
            self.assertNotEqual(rec.action, "SELL")

    def test_sentence_level_target_isolation(self):
        # Targets must not bleed across multiple stocks in the same chunk
        chunks = [{
            'start': 200.0,
            'duration': 40.0,
            'text': "Buy Coal India with target 1350. Meanwhile keep an eye on Tata Motors for long term."
        }]
        recs = self.extractor.extract(chunks, self.video_id)
        for rec in recs:
            if rec.ticker == "TATAMOTORS":
                self.assertNotIn("1350", rec.target)

    def test_modern_stock_aliases(self):
        res_lohia = indian_market_manager.resolve_ticker("lohia corp")
        self.assertIsNotNone(res_lohia)
        self.assertEqual(res_lohia[0], "LOHIACORP")

        res_milky = indian_market_manager.resolve_ticker("milky mist")
        self.assertIsNotNone(res_milky)
        self.assertEqual(res_milky[0], "MILKYMIST")

    def test_parse_llm_markdown_table(self):
        from stock_extractor.extractors.llm_base import parse_llm_markdown_table_response
        table_md = """
        | Ticker | Action | Stop Loss | Target | Horizon | Quote |
        | :--- | :---: | :---: | :---: | :---: | :--- |
        | **TURTLEMINT** | `WATCH` | N/A | N/A | 2-3 Years | [00:54] Turtlemint will follow the same cost |
        | **LOHIACORP** | `WATCH` | N/A | N/A | Long Term | [03:58] Lohia Corp is India largest machinery |
        """
        recs = parse_llm_markdown_table_response(table_md, self.video_id)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0].ticker, "TURTLEMINT")
        self.assertEqual(recs[0].action, "WATCH")
        self.assertEqual(recs[1].ticker, "LOHIACORP")

    def test_parse_llm_markdown_table_with_analyst_and_fund_house(self):
        from stock_extractor.extractors.llm_base import parse_llm_markdown_table_response
        table_md = """
        | Ticker | Action | Analyst / Firm | Stop-Loss | Target | Horizon | Timestamp | Source Quote |
        | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
        | **RELIANCE** | `BUY` | Varun | Rs 1260 | Rs 1345 | Short-term | [01:46](https://youtu.be/test?t=106) | Test position at 1275 with SL 1260 |
        | **TATAMOTORS** | `BUY` | Jefferies | Rs 920 | Rs 1100 | Short-term | [02:30](https://youtu.be/test?t=150) | Jefferies maintains buy rating on Tata Motors |
        """
        recs = parse_llm_markdown_table_response(table_md, self.video_id)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0].ticker, "RELIANCE")
        self.assertEqual(recs[0].action, "BUY")
        self.assertEqual(recs[0].analyst, "Varun")
        self.assertEqual(recs[0].stop_loss, "Rs 1260")
        self.assertEqual(recs[1].ticker, "TATAMOTORS")
        self.assertEqual(recs[1].analyst, "Jefferies")

    def test_heuristic_detect_fund_house_and_analyst(self):
        chunks = [{
            'start': 100.0,
            'duration': 25.0,
            'text': "Jefferies has a bullish report on Tata Motors. Buy TATAMOTORS with target 1100 and stop loss 920."
        }]
        recs = self.extractor.extract(chunks, self.video_id)
        self.assertGreaterEqual(len(recs), 1)
        self.assertEqual(recs[0].ticker, "TATAMOTORS")
        self.assertEqual(recs[0].analyst, "Jefferies")

        chunks_analyst = [{
            'start': 200.0,
            'duration': 25.0,
            'text': "Varun ji is advising to buy Reliance Industries. Support and stop loss at 1260 and target 1340."
        }]
        recs_analyst = self.extractor.extract(chunks_analyst, self.video_id)
        self.assertGreaterEqual(len(recs_analyst), 1)
        self.assertEqual(recs_analyst[0].ticker, "RELIANCE")
        self.assertEqual(recs_analyst[0].analyst, "Varun")

    def test_get_extractor_factory(self):
        ext_heuristic = get_extractor("heuristic")
        self.assertIn("Indian Market", ext_heuristic.name)

if __name__ == "__main__":
    unittest.main()
