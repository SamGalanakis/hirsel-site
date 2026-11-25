"""Where the site's two inputs live.

This repo holds the hand-written pages (site/) and the generators (tools/). The language
documentation (docs/PRIMER.md, docs/COOKBOOK.md, docs/spec/, core/std/API-INDEX.md,
skills/hirsel/SKILL.md, README.md) and the Tree-sitter grammar come from a checkout of
SamGalanakis/hirsel, named by HIRSEL_REPO (tools/build_site.py sets it from --hirsel-repo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SITE_REPO = Path(__file__).resolve().parents[1]
SITE = SITE_REPO / "site"


def hirsel_repo() -> Path:
    raw = os.environ.get("HIRSEL_REPO")
    if not raw:
        sys.exit("set HIRSEL_REPO to a checkout of SamGalanakis/hirsel (or pass --hirsel-repo)")
    path = Path(raw).resolve()
    if not (path / "docs" / "PRIMER.md").is_file():
        sys.exit(f"HIRSEL_REPO={raw}: not a Hirsel checkout (no docs/PRIMER.md)")
    return path


def __getattr__(name: str) -> Path:
    # `from site_paths import HIRSEL` resolves the checkout only in tools that read it.
    if name == "HIRSEL":
        return hirsel_repo()
    raise AttributeError(name)
