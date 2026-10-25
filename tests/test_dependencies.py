"""The server's runtime deps (pyproject.toml, used by Vercel) must also be in the dev
requirements.txt, so local runs and tests exercise the same packages as production."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _name(spec: str) -> str:
    return re.split(r"[\[<>=~! ]", spec.strip(), maxsplit=1)[0].lower()


def test_server_dependencies_are_in_dev_requirements():
    server = {_name(d) for d in tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]}
    dev = {_name(l) for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
    assert server - dev == set()
