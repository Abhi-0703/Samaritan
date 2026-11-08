"""Record a test call alone (you read the agent, a synthetic voice reads the borrower). See
api/app/evaluation/recorder.py. Run with the API's virtualenv:

    api/.venv/bin/python scripts/record_call.py call_14
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.evaluation.recorder import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
