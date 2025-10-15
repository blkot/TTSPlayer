# Repository Guidelines

## Project Structure & Module Organization
The repository currently contains only `pyproject.toml`; add a `src/ttsplayer/` package for application code as features are introduced. Mirror runtime modules with tests under `tests/`, for example `src/ttsplayer/player.py` alongside `tests/test_player.py`. Create `assets/` only when shipping reusable audio samples, and keep filenames descriptive (`assets/samples/en_intro.wav`) so they stay discoverable.

## Environment & Setup
The project targets Python 3.13 and was bootstrapped with `uv`. Recreate the environment with `uv venv .venv` and activate it using `.\.venv\Scripts\Activate.ps1` in PowerShell or `.venv/bin/activate` on Unix shells. Install the project in editable mode via `uv pip install -e .`; record developer tools in `[project.optional-dependencies]` so `uv pip install -e .[dev]` stays reproducible for new contributors and PyCharm can sync its interpreter automatically.

## Build, Test, and Development Commands
Use `uv pip install -e .` after modifying dependencies to refresh the venv. Once the package exists, run smoke tests with `uv run python -m ttsplayer --help` or other entry points you add. Execute the test suite with `uv run pytest`; filter targets by feature using `uv run pytest -k playback`. Consider wiring these commands into PyCharm run configurations to keep the workflow consistent.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and prefer explicit type hints on public functions. Modules, functions, and variables should remain in `snake_case`; classes in `PascalCase`; constants in `UPPER_CASE`. Format and lint with Ruff (`uv run ruff format src tests` and `uv run ruff check src tests`) once the tool is declared in `pyproject.toml`, and document any exceptions inline.

## Testing Guidelines
Adopt `pytest` as the primary framework. Start every new feature with a corresponding `tests/test_<feature>.py` file and name classes `Test<Feature>` to clarify coverage. Share fixtures through `tests/conftest.py`, keeping audio samples short to maintain fast runs. Target at least 80% line coverage on new modules; explain any gaps directly in the pull request.

## Commit & Pull Request Guidelines
History is empty, so begin with Conventional Commits (e.g., `feat: scaffold cli entrypoint`, `chore: configure ruff`). Each pull request should include a concise summary, list executed commands (`uv run pytest`, manual checks), and link relevant issues or design docs. Attach screenshots or short clips when UI or audio behavior changes so reviewers can validate outcomes without rebuilding locally.
