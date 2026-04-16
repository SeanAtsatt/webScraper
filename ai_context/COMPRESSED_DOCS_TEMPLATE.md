# Compressed Documentation Template

Use this template to create compressed documentation indexes for frameworks and libraries used in your project.

## Purpose

Compressed docs provide **immediate answers** to common questions without requiring file reads or web fetches. This reduces context usage by ~80% and speeds up Claude's responses.

## Template Structure

```markdown
# [Framework/Library] Quick Reference

> Version: X.Y.Z | Docs: [URL]

## Quick Answers

| Task | How |
|------|-----|
| [Common task 1] | `code snippet` |
| [Common task 2] | `code snippet` |
| [Common task 3] | `code snippet` |

## Patterns

### [Pattern Name]
\`\`\`[language]
[Minimal working example]
\`\`\`

### [Pattern Name]
\`\`\`[language]
[Minimal working example]
\`\`\`

## Gotchas
- [Common mistake] → [How to fix]
- [Surprising behavior] → [Explanation]

## Project-Specific Conventions
- [How we use this in our project]
- [Local patterns or wrappers]

## When to Fetch Full Docs
- [Edge case that needs full documentation]
- [Advanced feature not covered here]
```

## Example: FastAPI

```markdown
# FastAPI Quick Reference

> Version: 0.109+ | Docs: https://fastapi.tiangolo.com

## Quick Answers

| Task | How |
|------|-----|
| GET route | `@app.get("/path")` |
| POST route | `@app.post("/path")` |
| Path param | `def route(id: int):` |
| Query param | `def route(q: str = None):` |
| Request body | `def route(item: ItemModel):` |
| Response model | `@app.get("/", response_model=Item)` |
| Status code | `@app.post("/", status_code=201)` |
| Dependency | `def route(db = Depends(get_db)):` |
| Background task | `background_tasks.add_task(fn, arg)` |
| File upload | `def route(file: UploadFile):` |
| Error response | `raise HTTPException(404, "Not found")` |

## Patterns

### CRUD Router
\`\`\`python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()

@router.get("/{id}")
async def get_item(id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    return item

@router.post("/", status_code=201)
async def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    db_item = Item(**item.dict())
    db.add(db_item)
    db.commit()
    return db_item
\`\`\`

### Dependency with Cleanup
\`\`\`python
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
\`\`\`

## Gotchas
- `async def` required for async I/O (database, HTTP calls)
- Pydantic models validate automatically - no manual validation needed
- Path params are required, query params are optional by default
- Use `Optional[str] = None` for optional fields, not `str = None`

## Project Conventions
- All routes use async
- Database sessions via `Depends(get_db)`
- Pydantic models in `schemas/` directory
- Business logic in `services/` not in routes
```

## Example: pytest

```markdown
# pytest Quick Reference

> Version: 8.x | Docs: https://docs.pytest.org

## Quick Answers

| Task | How |
|------|-----|
| Run all tests | `pytest` |
| Run specific file | `pytest tests/test_foo.py` |
| Run specific test | `pytest tests/test_foo.py::test_bar` |
| Run by marker | `pytest -m slow` |
| Stop on first fail | `pytest -x` |
| Verbose output | `pytest -v` |
| Show print output | `pytest -s` |
| Coverage | `pytest --cov=src` |
| Parallel | `pytest -n auto` |

## Patterns

### Basic Test
\`\`\`python
def test_something():
    result = function_under_test()
    assert result == expected
\`\`\`

### Fixture
\`\`\`python
@pytest.fixture
def sample_user():
    return User(name="Test", email="test@example.com")

def test_with_fixture(sample_user):
    assert sample_user.name == "Test"
\`\`\`

### Parametrize
\`\`\`python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert double(input) == expected
\`\`\`

### Async Test
\`\`\`python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
\`\`\`

### Mock
\`\`\`python
def test_with_mock(mocker):
    mock_api = mocker.patch("module.api_call")
    mock_api.return_value = {"data": "mocked"}
    result = function_that_calls_api()
    assert result == expected
\`\`\`

## Gotchas
- Test files must start with `test_` or end with `_test.py`
- Test functions must start with `test_`
- Fixtures are injected by parameter name, not import
- Use `conftest.py` for shared fixtures

## Project Conventions
- Fixtures in `tests/conftest.py`
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Run `./scripts/verify.sh` before committing
```

## Adding to Your Project

1. Identify frameworks/libraries used heavily in your project
2. Create compressed docs in `ai_context/[framework].md`
3. Include in CLAUDE.md's documentation index
4. Update when upgrading versions

## When Compressed Docs Aren't Enough

Fetch full documentation when:
- Implementing rarely-used features
- Debugging unexpected behavior
- Upgrading to new major version
- Working with advanced configuration
