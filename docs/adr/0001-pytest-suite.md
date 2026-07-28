# 1. Adopt Pytest for Unit and Integration Testing

Date: 2026-07-27

## Status

Accepted

## Context

Glissade had no automated test suite, relying on `glissade check --demo` and manual verification. As new features (such as `check --fix`, `upgrade`, `update`, and live notes) were added, automated unit and integration tests became essential for regression prevention and agentic development loops.

We needed to decide on:
1. The test framework and runner.
2. Where test files should be located in the repository.
3. How to isolate filesystem and network operations during testing.

## Decision

1. **Test Runner**: Adopt `pytest` as the project test runner, configured under `[tool.pytest.ini_options]` in `pyproject.toml`.
2. **Dependencies**: Add `dev = ["pytest>=8.0", "httpx>=0.27"]` under `[project.optional-dependencies]` in `pyproject.toml`.
3. **Directory Structure**: Store test files in a top-level `tests/` directory (`tests/test_*.py`). This keeps test files out of the distributed wheel packaged by Hatchling.
4. **Isolation**:
   - Use `pytest`'s `tmp_path` fixture and `monkeypatch.chdir` to isolate CLI command execution (`init`, `check`, `build`) in temporary directories.
   - Use FastAPI's `TestClient` (via `starlette`/`httpx`) for in-memory HTTP/SSE API testing without binding real network ports.
5. **CI/CD**: Add `.github/workflows/test.yml` to run tests automatically via `uv` across Python 3.10–3.13 on push and PR.

## Consequences

- **Positive**: Clean separation of concerns between distributed code (`src/glissade`) and test code (`tests/`). Fast in-memory test execution using `pytest` and `TestClient`.
- **Negative**: Adds a dev dependency on `pytest` and `httpx` for contributors running tests locally.
