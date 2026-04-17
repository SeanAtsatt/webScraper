"""Chrome profile copy tests."""

from pathlib import Path

import pytest

from webscraper.errors import EnvironmentError
from webscraper.profile import copy_profile, locate_profile


# [F-NONE]
def test_locate_profile_uses_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "CustomProfile"
    fake.mkdir()
    monkeypatch.setenv("WEBSCRAPER_CHROME_PROFILE", str(fake))
    assert locate_profile() == fake


# [F-NONE]
def test_locate_profile_raises_when_env_points_nowhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_CHROME_PROFILE", str(tmp_path / "missing"))
    with pytest.raises(EnvironmentError):
        locate_profile()


# [F-NONE]
def test_copy_profile_copies_files_but_skips_lock_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "Cookies").write_bytes(b"cookies-db")
    (src / "SingletonLock").symlink_to(src / "whatever")  # lock file
    (src / "LOCK").write_bytes(b"lock")
    dst_parent = tmp_path / "dst"
    dst_parent.mkdir()
    with copy_profile(src, tmp_parent=dst_parent) as copied:
        assert (copied / "Cookies").read_bytes() == b"cookies-db"
        assert not (copied / "SingletonLock").exists()
        assert not (copied / "LOCK").exists()
    # Cleanup on exit
    assert not copied.exists()


# [F-NONE]
def test_copy_profile_cleans_up_on_exception(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "Cookies").write_bytes(b"x")
    dst_parent = tmp_path / "dst"
    dst_parent.mkdir()
    copied_path: Path | None = None
    with pytest.raises(RuntimeError), copy_profile(src, tmp_parent=dst_parent) as copied:
        copied_path = copied
        raise RuntimeError("boom")
    assert copied_path is not None
    assert not copied_path.exists()
