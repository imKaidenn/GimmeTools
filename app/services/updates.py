"""
GimmeTools — update check against GitHub releases.

Stdlib-only (urllib), non-blocking by design: the API layer calls this from
a thread and pushes a toast if a newer tag exists. Full auto-update flow
(download + swap) is documented in docs/RELEASE_V2.md; this module is the
detection half of that architecture.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional

RELEASES_API = "https://api.github.com/repos/imKaidenn/GimmeTools/releases/latest"
RELEASES_PAGE = "https://github.com/imKaidenn/GimmeTools/releases/latest"
_TIMEOUT = 6


@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    current: str
    latest: str
    url: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_version(tag: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", tag)
    return tuple(int(n) for n in nums) if nums else (0,)


def check(current_version: str) -> UpdateInfo:
    """Never raises — returns error info instead (offline is normal)."""
    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": f"GimmeTools/{current_version}"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = str(data.get("tag_name") or "")
        url = str(data.get("html_url") or RELEASES_PAGE)
        if not latest:
            return UpdateInfo(False, current_version, "", url, "no releases found")
        newer = _parse_version(latest) > _parse_version(current_version)
        return UpdateInfo(newer, current_version, latest, url)
    except Exception as e:  # noqa: BLE001 — offline must never break the app
        return UpdateInfo(False, current_version, "", RELEASES_PAGE, str(e))


# ── Self-test (offline-safe) ───────────────────────────────────────────────────

if __name__ == "__main__":
    assert _parse_version("v2.1") > _parse_version("2.0")
    assert _parse_version("1.10") > _parse_version("1.9")
    assert not _parse_version("2.0") > _parse_version("2.0")
    info = check("0.0")  # network may or may not exist — must not raise
    assert isinstance(info.to_dict(), dict)
    print(f"updates.py OK (live check: available={info.available}, "
          f"latest='{info.latest or info.error}')")
