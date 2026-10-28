"""Run using: python -m modules.insights.cli input.json [output.json]"""

import json
import sys
from pathlib import Path

from .service import summarise


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "Usage: python -m modules.insights.cli "
            "input.json [output.json]"
        )

    summary = summarise(
        json.loads(
            Path(sys.argv[1]).read_text(
                encoding="utf-8"
            )
        )
    )

    result = (
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False
        ) + "\n"
    )

    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(
            result,
            encoding="utf-8"
        )
    else:
        print(result, end="")


if __name__ == "__main__":
    main()