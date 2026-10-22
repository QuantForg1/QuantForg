"""Frontend sources must not contain double-encoded UTF-8 (mojibake).

Owner report 2026-10-22: the Research page showed the em dash as three
garbage characters (its UTF-8 bytes read back as cp1252).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
# UTF-8 bytes of em dash, ellipsis, quotes, middot ... read back as cp1252.
_MOJIBAKE = re.compile(
    "|".join(
        (
            chr(0xE2) + chr(0x20AC),
            chr(0xC2) + "[" + chr(0xA0) + "-" + chr(0xBF) + "]",
            chr(0xC3) + "[" + chr(0x80) + "-" + chr(0xBF) + "]",
        )
    )
)


def test_frontend_sources_have_no_mojibake() -> None:
    offenders = []
    for path in _ROOT.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css"} or "node_modules" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _MOJIBAKE.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{lineno}")
    assert offenders == []
