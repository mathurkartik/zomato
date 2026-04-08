#!/usr/bin/env python3
"""Build data/processed/restaurants.parquet from the Hugging Face Zomato dataset."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase1.ingest import run_ingestion

if __name__ == "__main__":
    run_ingestion()
