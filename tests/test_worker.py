# The Worker's safety logic (worker/worker.js), run with Node: lookups are accepted only for things in the data,
# and a written answer is accepted only if every number in it appears in the facts it was given.
# Skipped where Node is not installed (it is on GitHub's test machines and in Codespaces).
import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parent.parent / "worker" / "worker.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")


def run(expression, tmp_path):
    # Load worker.js as a module and print the JSON value of one expression that uses it (as m).
    module = tmp_path / "worker.mjs"
    module.write_text(WORKER.read_text())
    script = f'import("{module.as_posix()}").then(m => console.log(JSON.stringify({expression})))'
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


FACTS = {"answer": [{"year": "FY2022", "value": "134", "unit": "USD per kg", "page": 152}],
         "trend": [{"year": "FY2021", "value": "98"}, {"year": "FY2023", "value": "78"}]}


def test_guard_accepts_numbers_from_the_facts(tmp_path):
    text = "Neodymium oxide averaged 134 USD per kg in 2022 (page 152), up from 98 in 2021 and down to 78 in 2023."
    assert run(f"m.guard({json.dumps(text)}, {json.dumps(FACTS)})", tmp_path)["ok"]


@pytest.mark.parametrize("text, bad", [
    ("Up 37% on 2021.", 37),                       # a calculation
    ("Analysts expect 150 next year.", 150),       # an invented figure
    ("It fell to 74 in 2023.", 74),                # a wrong figure
])
def test_guard_rejects_numbers_not_in_the_facts(tmp_path, text, bad):
    verdict = run(f"m.guard({json.dumps(text)}, {json.dumps(FACTS)})", tmp_path)
    assert not verdict["ok"] and bad in verdict["unknown"]


def test_lookup_outside_the_data_is_refused(tmp_path):
    entries = [{"entity": "China", "metric": "production_volume", "materials": ["total_REO"], "segments": [], "years": ["FY2024"]}]
    good = {"answerable": True, "entity": "China", "metric": "production_volume", "year": "FY2024"}
    invented = {"answerable": True, "entity": "Iluka Resources", "metric": "production_volume", "year": "FY2024"}
    assert run(f"m.validate({json.dumps(good)}, {json.dumps(entries)})", tmp_path)["answerable"]
    assert not run(f"m.validate({json.dumps(invented)}, {json.dumps(entries)})", tmp_path)["answerable"]


def test_preflight_reply_has_no_body(tmp_path):
    # The browser's "may I?" check must get an empty 204 reply, or the question box breaks (found after go-live).
    module = tmp_path / "worker.mjs"
    module.write_text(WORKER.read_text())
    script = (f'import("{module.as_posix()}").then(m => m.default.fetch(new Request("https://x/", {{method: "OPTIONS", '
              f'headers: {{Origin: "https://themayankpathak.github.io"}}}}), {{}})).then(r => console.log(r.status))')
    assert subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout.strip() == "204"
