# Python Tooling Quick Reference

> Tools: uv, ruff, pytest, mypy | Python 3.11+
> Last verified: 2026-02-04 from official docs

## uv (Package Manager)

> "10-100x faster than pip" - replaces pip, pip-tools, pipx, poetry, pyenv, virtualenv

| Task | Command |
|------|---------|
| Create project | `uv init` |
| Add dependency | `uv add package` |
| Add dev dependency | `uv add --dev package` |
| Remove dependency | `uv remove package` |
| Install all deps | `uv sync` |
| Run command | `uv run python script.py` |
| Run pytest | `uv run pytest` |
| Update lockfile | `uv lock` |
| Install Python | `uv python install 3.12` |
| Pin Python version | `uv python pin 3.11` |
| Run tool (ephemeral) | `uvx ruff check` |
| Install tool globally | `uv tool install ruff` |

### pyproject.toml
```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi", "sqlalchemy"]

[tool.uv]
dev-dependencies = ["pytest", "ruff", "mypy"]
```

## ruff (Linter + Formatter)

> "10-100x faster" than Flake8/Black - 800+ built-in rules

| Task | Command |
|------|---------|
| Check (lint) | `ruff check .` |
| Check + fix | `ruff check . --fix` |
| Check + unsafe fix | `ruff check . --fix --unsafe-fixes` |
| Format | `ruff format .` |
| Format check | `ruff format . --check` |
| Watch mode | `ruff check --watch` |
| Add noqa comments | `ruff check --add-noqa` |

### pyproject.toml
```toml
[tool.ruff]
line-length = 88
target-version = "py311"
exclude = [".git", ".venv", "build", "dist"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B"]
ignore = ["E501"]  # line too long (formatter handles)
fixable = ["ALL"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # unused imports OK in __init__
"tests/*" = ["S101"]      # assert OK in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Common Rule Codes
| Code | Source | Examples |
|------|--------|----------|
| E | pycodestyle errors | E401 (multiple imports) |
| F | Pyflakes | F401 (unused import), F841 (unused var) |
| I | isort | I001 (import sorting) |
| W | pycodestyle warnings | W291 (trailing whitespace) |
| UP | pyupgrade | UP035 (deprecated typing) |
| B | flake8-bugbear | B008 (mutable default) |
| N | pep8-naming | N801 (class name) |

## pytest

| Task | Command |
|------|---------|
| Run all | `uv run pytest` |
| Verbose | `uv run pytest -v` |
| Stop on first fail | `uv run pytest -x` |
| Show prints | `uv run pytest -s` |
| Coverage | `uv run pytest --cov=src` |
| Coverage + HTML | `uv run pytest --cov=src --cov-report=html` |
| Specific file | `uv run pytest tests/test_foo.py` |
| Specific test | `uv run pytest tests/test_foo.py::test_bar` |
| By marker | `uv run pytest -m "not slow"` |
| By name pattern | `uv run pytest -k "test_user"` |
| Last failed only | `uv run pytest --lf` |
| Parallel | `uv run pytest -n auto` |

### pyproject.toml
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow",
    "integration: integration tests",
]
```

### Fixture Pattern
```python
import pytest

@pytest.fixture
def db_session():
    """Database session with automatic rollback."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def sample_user(db_session):
    """Create a test user."""
    user = User(name="Test", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    return user
```

### Parametrize Pattern
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (-1, -2),
])
def test_double(input, expected):
    assert double(input) == expected
```

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Mock Pattern
```python
def test_with_mock(mocker):
    mock_api = mocker.patch("module.api_call")
    mock_api.return_value = {"data": "mocked"}

    result = function_that_calls_api()

    assert result == expected
    mock_api.assert_called_once()
```

## mypy (Type Checker)

| Task | Command |
|------|---------|
| Check all | `uv run mypy .` |
| Check file | `uv run mypy src/module.py` |
| Strict mode | `uv run mypy --strict .` |
| Show error codes | `uv run mypy --show-error-codes .` |

### pyproject.toml
```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Common Type Patterns
```python
from typing import Optional
from collections.abc import Sequence, Mapping

# Optional (can be None)
def get_user(id: int) -> Optional[User]: ...

# Modern union syntax (3.10+)
def get_user(id: int) -> User | None: ...

# Collections
def process(items: list[str]) -> dict[str, int]: ...

# Callable
from typing import Callable
def apply(fn: Callable[[int], int], x: int) -> int: ...

# TypeVar for generics
from typing import TypeVar
T = TypeVar("T")
def first(items: Sequence[T]) -> T | None: ...
```

## Gotchas

- Always run commands through `uv run` to use project's virtualenv
- ruff replaces flake8, isort, black - don't install those separately
- pytest fixtures inject by parameter name, not import
- mypy `strict = true` catches most issues but may need `# type: ignore` for edge cases
- Use `from __future__ import annotations` for forward references in older Python

## Project Conventions

- All commands via `uv run`
- Format with `ruff format` before committing
- Type hints on all public functions
- Tests mirror source: `src/foo.py` → `tests/test_foo.py`
- Run `./scripts/verify.sh` before committing
