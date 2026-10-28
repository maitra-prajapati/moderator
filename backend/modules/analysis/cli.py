"""
Run:

python -m backend.modules.analysis.cli --input demo/fixtures/m4-request.json
"""

import argparse
import json
import sys

from pydantic import ValidationError

from .engine import analyse_with_status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline Moderator M4 analyzer"
    )

    parser.add_argument(
        "--input",
        help="Request JSON file (defaults to stdin)",
    )

    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Print AI status to stderr",
    )

    args = parser.parse_args()

    try:
        if args.input:
            with open(
                args.input,
                encoding="utf-8",
            ) as stream:
                request_json = json.load(stream)
        else:
            request_json = json.load(sys.stdin)

        result, status = analyse_with_status(
            request_json
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

        if args.show_status:
            print(
                f"AI status: {status}",
                file=sys.stderr,
            )

        return 0

    except (
        OSError,
        ValueError,
        TypeError,
        ValidationError,
    ) as exc:
        print(
            f"Invalid analysis request: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    sys.exit(main())