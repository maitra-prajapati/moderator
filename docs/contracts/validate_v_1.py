"""Validate one Moderator JSON payload against one local contract schema.

No server, examples, automatic checks, or terminal output on import.
Install: pip install jsonschema
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def _json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif str(part).isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(str(part))}]"
    return path


def validate_json(payload: Any, contract: str) -> dict:
    """Validate exactly one JSON value against a named schema.

    Args:
        payload: A parsed JSON value (usually dict) OR a JSON string.
        contract: Schema filename without '.schema.json', e.g. 'submission-create'.

    Returns:
        {"contract": str, "valid": bool, "errors": [{"path": str, "message": str}]}

    Configuration errors (missing/invalid schema) are reported as errors with
    path '$schema'; bad JSON syntax is reported at path '$'.
    """
    result = {"contract": contract, "valid": False, "errors": []}

    if not isinstance(contract, str) or not contract or not all(
        c.isalnum() or c in "-_" for c in contract
    ):
        result["errors"].append({"path": "$schema", "message": "Invalid contract name"})
        return result

    schema_path = SCHEMA_DIR / f"{contract}.schema.json"
    if not schema_path.is_file():
        result["errors"].append({"path": "$schema", "message": f"Schema not found: {schema_path.name}"})
        return result

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        result["errors"].append({"path": "$schema", "message": f"Could not load schema: {exc}"})
        return result

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            result["errors"].append({
                "path": "$",
                "message": f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            })
            return result

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(payload), key=lambda e: (list(map(str, e.absolute_path)), e.message)):
        result["errors"].append({"path": _json_path(error.absolute_path), "message": error.message})

    result["valid"] = not result["errors"]
    return result


def print_validation_result(result: dict) -> None:
    """Optional helper: print one validation result in the terminal."""
    status = "PASS" if result["valid"] else "FAIL"
    print(f"{status} [{result['contract']}]")
    for index, error in enumerate(result["errors"], 1):
        print(f"  {index}. {error['path']}: {error['message']}")
