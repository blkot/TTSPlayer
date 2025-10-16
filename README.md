# TTSPlayer

TTSPlayer is a cross-platform desktop utility that organises local audio clips and their paired transcripts. It scans a folder of `.wav`, `.mp3`, or `.ogg` files, loads the matching `.txt` snippets, and presents them in a PySide6 card-based interface with instant playback driven by `pygame`.

## Features

- Library discovery with automatic transcript pairing (`intro.wav` + `intro.txt`)
- In-memory preloading for quick start/stop audio playback
- Modern PySide6 UI with transcript cards, instant play on selection, and synchronized progress bars
- CLI entrypoint for headless listing or launching the GUI
- pytest-based unit tests covering the loader, player, and fake mixer harness

## Requirements

- Python 3.13
- `uv` for environment and dependency management
- Runtime dependencies: PySide6, pygame, click
- Optional dev tools: pytest, pytest-mock, ruff

## Getting Started

```bash
# Create and activate a virtual environment
uv venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install in editable mode with dev extras
uv pip install -e .[dev]
```

### Running the App

- Run the GUI and pick a library folder from the `Open Folder…` button:

  ```bash
  uv run python -m ttsplayer
  ```

- Preload a specific folder at startup or list it in headless mode:

  ```bash
  uv run python -m ttsplayer --folder /path/to/library
  uv run python -m ttsplayer --folder /path/to/library --headless
  ```

### Testing & Linting

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

## Project Layout

```
src/ttsplayer/
├── audio/          # Loader & playback services (pygame mixer wrapper)
├── models/         # Core dataclasses (Track)
├── ui/             # PySide6 UI bootstrap and widgets
├── cli.py          # Click command line entrypoint
└── __main__.py     # Enables `python -m ttsplayer`

tests/              # pytest suite mirroring runtime modules
assets/             # (optional) shared audio samples
```

## Development Notes

- Follow PEP 8 with Ruff formatting (`uv run ruff format src tests`).
- Public APIs should include explicit type hints.
- When adding new modules, mirror them with `tests/test_<module>.py`.
- GUI additions should keep the PySide6 card motif and reuse `TrackPlayer` abstractions.

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE) for details.
