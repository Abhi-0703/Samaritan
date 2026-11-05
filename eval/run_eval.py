"""Evaluate the cached transcripts against the answer keys: python eval/run_eval.py [ingest|run|label] ...

A thin wrapper; the code lives in api/app/evaluation so the API can call it too (docs/decisions.md D-023).
Use the API's virtualenv: api/.venv/bin/python eval/run_eval.py run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.evaluation.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["run"]))
