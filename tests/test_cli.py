"""
Unit tests for CLI command execution.
"""

import unittest
from typer.testing import CliRunner
from stock_extractor.cli import app

runner = CliRunner()

class TestCLI(unittest.TestCase):

    def test_cli_help(self):
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Extract structured stock recommendations", result.output)

    def test_cli_invalid_url(self):
        result = runner.invoke(app, ["extract", "invalid_url_string"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid YouTube URL", result.output)

if __name__ == "__main__":
    unittest.main()
