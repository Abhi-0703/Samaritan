"""See api/app/seeding_cli.py.
Run with the API's virtualenv: api/.venv/bin/python scripts/seed.py [--yes]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.seeding_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main("seed", sys.argv[1:]))
