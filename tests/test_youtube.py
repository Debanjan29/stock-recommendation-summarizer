"""
Unit tests for YouTube URL parser, timestamp helpers, and transcript chunking.
"""

import unittest
from stock_extractor.utils import parse_youtube_id, format_timestamp, make_timestamp_url, chunk_transcript

class TestYouTubeUtils(unittest.TestCase):
    
    def test_parse_youtube_id(self):
        # Valid URLs
        self.assertEqual(parse_youtube_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(parse_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(parse_youtube_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(parse_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(parse_youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(parse_youtube_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=100s"), "dQw4w9WgXcQ")
        
        # Invalid URLs
        self.assertIsNone(parse_youtube_id("invalid_url_string"))
        self.assertIsNone(parse_youtube_id("https://google.com"))

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(45.6), "00:46")
        self.assertEqual(format_timestamp(252), "04:12")
        self.assertEqual(format_timestamp(3665), "01:01:05")

    def test_make_timestamp_url(self):
        self.assertEqual(
            make_timestamp_url("dQw4w9WgXcQ", 252.3),
            "https://youtu.be/dQw4w9WgXcQ?t=252"
        )

    def test_chunk_transcript(self):
        snippets = [
            {'text': 'Hello welcome to stock analysis.', 'start': 0.0, 'duration': 5.0},
            {'text': 'Today we talk about Apple.', 'start': 5.0, 'duration': 5.0},
            {'text': 'Apple stock looks bullish.', 'start': 10.0, 'duration': 5.0}
        ]
        chunks = chunk_transcript(snippets, max_duration=60.0, max_words=300)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['start'], 0.0)
        self.assertIn("Apple stock looks bullish", chunks[0]['text'])

if __name__ == "__main__":
    unittest.main()
