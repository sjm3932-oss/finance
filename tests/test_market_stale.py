import sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "streamlit_app"))
from lib.market_data import is_stale

class StaleTests(unittest.TestCase):
    def test_fresh(self):
        ts = datetime.now(timezone.utc).isoformat()
        self.assertFalse(is_stale(ts, stale_hours=24))
    def test_old(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        self.assertTrue(is_stale(ts, stale_hours=24))
    def test_none(self):
        self.assertTrue(is_stale(None))

if __name__ == "__main__":
    unittest.main()
