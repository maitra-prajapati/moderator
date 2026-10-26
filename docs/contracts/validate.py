"""Validate Moderator v1 contracts. Run: python validate.py [--verbose] [--self-test]."""
import argparse
import copy
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError, ValidationError
except ImportError:
    print('ERROR: Dependency missing. Run: python -m pip install jsonschema', file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent


def location(parts):
    return '$' + ''.join(f'[{p}]' if isinstance(p, int) else f'.{p}' for p in parts)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return None, f'File not found: {path}'
    except PermissionError:
        return None, f'Permission denied: {path}'
    except UnicodeError as exc:
        return None, f'File encoding error: {path}: {exc}'
    except json.JSONDecodeError as exc:
        return None, f'Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}'
    except OSError as exc:
        return None, f'File read error: {path}: {exc}'


def describe(err):
    loc = location(err.absolute_path)
    if err.validator == 'required':
        return f'{loc}: {err.message} (add the missing required field)'
    if err.validator == 'additionalProperties':
        return f'{loc}: {err.message} (remove or rename unexpected fields)'
    if err.validator == 'type':
        return f'{loc}: {err.message} (expected {err.validator_value})'
    if err.validator == 'enum':
        return f'{loc}: {err.message} (allowed: {err.validator_value})'
    if err.validator == 'format':
        return f'{loc}: {err.message} (expected format: {err.validator_value})'
    return f'{loc}: {err.message} (constraint: {err.validator})'


def main():
    parser = argparse.ArgumentParser(description='Check all Moderator contract schemas and examples.')
    parser.add_argument('--verbose', action='store_true', help='Print validated requirements for each contract')
    parser.add_argument('--self-test', action='store_true', help='Also check that removing required fields is rejected')
    args = parser.parse_args()

    schema_dir, example_dir = ROOT / 'schemas', ROOT / 'examples'
    if not schema_dir.is_dir() or not example_dir.is_dir():
        print('ERROR: schemas/ and examples/ directories must exist next to validate.py')
        return 2
    schemas = {p.name.removesuffix('.schema.json'): p for p in schema_dir.glob('*.schema.json')}
    examples = {p.stem: p for p in example_dir.glob('*.json')}
    names = sorted(set(schemas) | set(examples))
    if not names:
        print('ERROR: No contract files found')
        return 2
    passed = failed = negative = 0
    for name in names:
        problems = []
        if name not in schemas:
            problems.append('Missing corresponding schema file')
        if name not in examples:
            problems.append('Missing corresponding example file')
        if not problems:
            schema, se = load_json(schemas[name])
            payload, pe = load_json(examples[name])
            if se: problems.append('Schema: ' + se)
            if pe: problems.append('Example: ' + pe)
            if not problems:
                try:
                    Draft202012Validator.check_schema(schema)
                    validator = Draft202012Validator(schema, format_checker=FormatChecker())
                    errors = sorted(validator.iter_errors(payload), key=lambda e: (str(list(e.absolute_path)), e.message))
                    problems.extend(describe(e) for e in errors)
                    if args.self_test and not errors:
                        for field in schema.get('required', []):
                            if isinstance(payload, dict) and field in payload:
                                invalid = copy.deepcopy(payload)
                                del invalid[field]
                                if validator.is_valid(invalid):
                                    problems.append(f'Self-test failed: removing required field {field!r} was accepted')
                                else:
                                    negative += 1
                except SchemaError as exc:
                    problems.append(f'Invalid JSON Schema: {exc.message}')
                except Exception as exc:
                    problems.append(f'Unexpected validation failure ({type(exc).__name__}): {exc}')
        if problems:
            failed += 1
            print(f'FAIL {name} ({len(problems)} issue(s))')
            for issue in problems:
                print('  - ' + issue)
        else:
            passed += 1
            print(f'PASS {name}')
            if args.verbose:
                print('  required:', ', '.join(schema.get('required', [])) or '(none)')
                print('  constraints: types, enums, formats, nesting, lengths and additional properties where specified')
    print(f'\nSUMMARY: {passed} passed, {failed} failed, {len(names)} total' + (f', {negative} negative tests passed' if args.self_test else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
