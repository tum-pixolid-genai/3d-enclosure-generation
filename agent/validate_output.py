import argparse
from pathlib import Path
import sys

if __package__:
    from .agent import PROJECT_DIR, load_validator, read_json
else:
    from agent import PROJECT_DIR, load_validator, read_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a saved v0.1 design specification.")
    parser.add_argument("json_file", type=Path)
    args = parser.parse_args(argv)

    try:
        output_data = read_json(PROJECT_DIR / args.json_file)
        validator = load_validator(PROJECT_DIR / "schemas/design_spec.schema.json")
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    errors = list(validator.iter_errors(output_data))
    if errors:
        print("SCHEMA FAIL")
        for error in errors:
            path = ".".join(str(item) for item in error.absolute_path)
            print("Field:", path or "<root>")
            print("Problem:", error.message)
        return 1

    print("SCHEMA PASS")
    print("The output matches design_spec.schema.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
