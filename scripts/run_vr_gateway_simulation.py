from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.vr_gateway import run_simulated_head_sequence


def main() -> None:
    for event in run_simulated_head_sequence():
        print(json.dumps(event, sort_keys=True))


if __name__ == "__main__":
    main()
