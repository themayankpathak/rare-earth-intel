# The question box's test set is valid: every question that should be answered points at something that
# exists in the data (docs/data/vocabulary.json), so a wrong answer is the model's fault, not the test's.
import json
from pathlib import Path

import pandas as pd

VOCABULARY = json.loads(Path("docs/data/vocabulary.json").read_text())
TESTS = pd.read_csv("eval/chatbot_questions.csv", dtype=str).fillna("")


def test_twenty_questions_some_must_be_refused():
    assert len(TESTS) == 20
    assert set(TESTS["answerable"]) == {"TRUE", "FALSE"}
    assert (TESTS["answerable"] == "FALSE").sum() >= 5


def test_every_expected_lookup_exists_in_the_data():
    for _, t in TESTS[TESTS["answerable"] == "TRUE"].iterrows():
        entry = next((e for e in VOCABULARY if e["entity"] == t["entity"] and e["metric"] == t["metric"]), None)
        assert entry, f"not in the data: {t['entity']} / {t['metric']}"
        assert not t["material"] or t["material"] in entry["materials"], t["question"]
        assert not t["segment"] or t["segment"] in entry["segments"], t["question"]
        assert not t["year"] or t["year"] in entry["years"], t["question"]


def test_vocabulary_matches_the_published_numbers():
    numbers = json.loads(Path("docs/data/numbers.json").read_text())
    assert {(n["entity"], n["metric"]) for n in numbers} == {(e["entity"], e["metric"]) for e in VOCABULARY}
