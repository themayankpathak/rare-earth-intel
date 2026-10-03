# Lets the tests load the pipeline scripts (scripts/text_cleaner.py and the others) as modules.
# Tests run from the repo root (`pytest`), where the scripts also expect to run.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
