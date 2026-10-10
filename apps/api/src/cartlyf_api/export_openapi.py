"""Write the OpenAPI schema to a file: `python -m cartlyf_api.export_openapi <path>`."""

import json
import sys
from pathlib import Path

from cartlyf_api.main import create_app


def main(argv: list[str]) -> None:
    out = Path(argv[0])
    out.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
