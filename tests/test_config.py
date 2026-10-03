# The config files are data too: these tests catch a broken map or table list before it reaches a run.
from pathlib import Path

import pandas as pd
import pytest
from self_checker import RANGES

CONFIG = Path("config")
SOURCES = pd.read_csv(CONFIG / "companies.csv", dtype=str)


def test_source_list_has_known_reading_rules():
    assert SOURCES["superscripts"].isin(["keep", "drop"]).all()
    assert SOURCES["dash_means"].isin(["empty", "zero"]).all()
    assert SOURCES["precision"].isin(["printed", "significant"]).all()
    assert SOURCES["file_prefix"].is_unique and SOURCES["company"].is_unique


@pytest.mark.parametrize("source", SOURCES["company"])
def test_every_source_has_tables_and_a_map(source):
    tables = pd.read_csv(CONFIG / f"{source}_tables.csv", dtype=str).fillna("")
    label_map = pd.read_csv(CONFIG / f"{source}_label_map.csv", dtype=str)
    assert (tables["anchor"].str.strip() != "").all()
    assert tables["years"].isin(["header", "none"]).all()
    # every map line points at a table that exists
    assert set(label_map["table"]) <= set(tables["table"])


@pytest.mark.parametrize("source", SOURCES["company"])
def test_no_line_has_two_meanings(source):
    label_map = pd.read_csv(CONFIG / f"{source}_label_map.csv", dtype=str).fillna("")
    keys = label_map[["table", "group"]].assign(label=label_map["label"].str.lower())
    assert not keys.duplicated().any()


@pytest.mark.parametrize("source", SOURCES["company"])
def test_every_metric_has_a_plausible_range(source):
    label_map = pd.read_csv(CONFIG / f"{source}_label_map.csv", dtype=str).fillna("")
    for _, line in label_map.iterrows():
        key = (line["metric"], line["unit"])
        scoped = (line["metric"], line["unit"], line["entity_scope"])
        assert key in RANGES or scoped in RANGES, f"{source}: no range for {key}"
