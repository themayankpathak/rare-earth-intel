# The website's data files (docs/data/, written by scripts/build_site.py) are present and consistent,
# so a broken or stale data file fails here before it reaches GitHub Pages.
import json
from pathlib import Path

import pandas as pd

DOCS = Path("docs")
SITE = json.loads((DOCS / "data" / "site.json").read_text())
NUMBERS = json.loads((DOCS / "data" / "numbers.json").read_text())


def test_counts_match_the_published_numbers():
    assert SITE["numbers"] == len(NUMBERS) == len(pd.read_csv(DOCS / "data" / "rare_earth_intel.csv"))
    assert SITE["documents"] == len({n["source_document"] for n in NUMBERS})


def test_no_check_failed():
    assert SITE["checks"]["FAIL"] == 0
    assert SITE["checks"]["PASS"] > 0


def test_every_open_or_expected_check_has_a_reason():
    for item in SITE["open"] + SITE["expected"]:
        assert item["reason"].strip()


def test_page_uses_the_data_files_and_the_chart():
    page = (DOCS / "index.html").read_text()
    for needed in ["data/site.json", "data/numbers.json", "data/rare_earth_intel.csv", "price_trap.png"]:
        assert needed in page
    assert (DOCS / "price_trap.png").exists()
