"""Label times and speakers in the answer keys: api/.venv/bin/python eval/label_times.py [--only call_01 ...]

Shows each cached transcript with segment numbers and asks which segment holds each expected violation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.evaluation.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["label", *sys.argv[1:]]))
