#!/usr/bin/env python3
"""Export the FastAPI app's OpenAPI schema to server/openapi.json.

OpenAPI is the source of truth for the generated TypeScript client (spec
Sec 5.1); this script is how that source of truth gets written to disk, and
`--check` is how CI proves the committed file hasn't drifted from the
FastAPI app's actual routes.

Usage:
    uv run python scripts/export_openapi.py            # write server/openapi.json
    uv run python scripts/export_openapi.py --check     # exit 1 if the on-disk file is stale

`FastAPI.openapi()` builds the schema from `self.router`/`self.title`/etc.
alone -- it never touches the ASGI lifespan protocol. So this script never
opens a database connection, even though `create_app()`'s lifespan would.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def generate_schema() -> dict:
    """Build the app and return its OpenAPI schema without running lifespan."""
    from yuno.api.app import create_app

    app = create_app()
    return app.openapi()


def render(schema: dict) -> str:
    """Serialize with stable key ordering and a trailing newline so the file is diff-stable."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the FastAPI app's OpenAPI schema.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if server/openapi.json differs from freshly generated output",
    )
    args = parser.parse_args(argv)

    rendered = render(generate_schema())

    if args.check:
        if not OUTPUT_PATH.exists():
            print(
                f"{OUTPUT_PATH} does not exist. Run `uv run python scripts/export_openapi.py`.",
                file=sys.stderr,
            )
            return 1
        if OUTPUT_PATH.read_text() != rendered:
            print(
                f"{OUTPUT_PATH} is stale relative to the FastAPI app's OpenAPI schema.\n"
                "Run `uv run python scripts/export_openapi.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT_PATH} is up to date.")
        return 0

    OUTPUT_PATH.write_text(rendered)
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
