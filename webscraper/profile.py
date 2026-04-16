"""Chrome profile discovery and copy-on-run isolation."""

from __future__ import annotations

import os
import platform
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from webscraper.errors import EnvironmentError

_LOCK_NAMES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK", "lockfile"}


def _default_profile_path() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library/Application Support/Google/Chrome/Default"
    if system == "Linux":
        return home / ".config/google-chrome/Default"
    raise EnvironmentError(f"unsupported platform: {system}")


def locate_profile() -> Path:
    override = os.environ.get("WEBSCRAPER_CHROME_PROFILE")
    if override:
        path = Path(override)
        if not path.exists() or not path.is_dir():
            raise EnvironmentError(
                f"WEBSCRAPER_CHROME_PROFILE does not point to a directory: {path}"
            )
        return path
    path = _default_profile_path()
    if not path.exists():
        raise EnvironmentError(f"Chrome profile not found at {path}")
    return path


def _ignore_locks(dir: str, names: list[str]) -> list[str]:  # noqa: A002
    return [n for n in names if n in _LOCK_NAMES]


@contextmanager
def copy_profile(src: Path, *, tmp_parent: Path | None = None) -> Iterator[Path]:
    """Copy a Chrome profile to a scratch directory; clean up on exit."""
    parent = tmp_parent or Path(tempfile.gettempdir())
    dst = Path(tempfile.mkdtemp(prefix="webscraper-profile-", dir=str(parent)))
    try:
        shutil.copytree(src, dst / "profile", ignore=_ignore_locks, dirs_exist_ok=False)
        yield dst / "profile"
    finally:
        shutil.rmtree(dst, ignore_errors=True)
