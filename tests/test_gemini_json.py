"""Unit tests that do not require live API keys."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "streamlit_app"
sys.path.insert(0, str(ROOT))

from lib.gemini_client import GeminiError, _extract_json  # noqa: E402


class ExtractJsonTests(unittest.TestCase):
    def test_plain_object(self):
        data = _extract_json('{"trades":[],"holdings_snapshot":[]}')
        self.assertEqual(data["trades"], [])

    def test_fenced_markdown(self):
        text = """```json
{"trades":[{"ticker":"AAPL","trade_type":"buy","price":1,"quantity":2}],"holdings_snapshot":[]}
```"""
        data = _extract_json(text)
        self.assertEqual(data["trades"][0]["ticker"], "AAPL")

    def test_embedded_noise(self):
        data = _extract_json('Here you go:\n{"trades":[],"holdings_snapshot":[],"ok":true}\nThanks')
        self.assertTrue(data["ok"])

    def test_invalid(self):
        with self.assertRaises(GeminiError):
            _extract_json("no json here")


if __name__ == "__main__":
    unittest.main()
