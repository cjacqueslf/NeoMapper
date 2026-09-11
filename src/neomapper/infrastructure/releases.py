"""GitHub release lookup isolated from the presentation layer."""
from __future__ import annotations

from dataclasses import dataclass

import requests
from packaging.version import Version


LATEST_RELEASE_URL = "https://api.github.com/repos/cjacqueslf/NeoMapper/releases/latest"


@dataclass(frozen=True)
class WindowsRelease:
    version: Version
    installer_url: str


def latest_windows_release() -> WindowsRelease:
    """Return the latest public Windows installer published on GitHub."""
    response = requests.get(LATEST_RELEASE_URL, timeout=10)
    response.raise_for_status()
    release = response.json()
    tag = str(release["tag_name"]).removeprefix("v")
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.endswith("-Windows-x64-Setup.exe"):
            return WindowsRelease(Version(tag), str(asset["browser_download_url"]))
    raise RuntimeError("The latest release does not contain a Windows installer.")
