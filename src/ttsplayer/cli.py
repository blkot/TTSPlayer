"""Command-line entry point for ttsplayer."""

from __future__ import annotations

from pathlib import Path

import click

from ttsplayer.audio.loader import AudioLibraryLoader
from ttsplayer.audio.player import TrackPlayer
from ttsplayer.ui.app import TrackListApp


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--folder",
    "folder_path",
    type=click.Path(path_type=Path, readable=True, exists=True, file_okay=False),
    required=False,
    help="Folder containing audio files.",
)
@click.option(
    "--recursive/--no-recursive",
    default=False,
    help="Recursively discover audio files in subfolders.",
)
@click.option(
    "--headless/--gui",
    default=False,
    help="List tracks without launching the GUI.",
)
def main(folder_path: Path | None, recursive: bool, headless: bool) -> None:
    """Load an audio library and launch TTSPlayer."""
    if headless:
        if folder_path is None:
            raise click.BadParameter(
                "--folder is required when running in headless mode.", param="folder"
            )
        loader = AudioLibraryLoader(folder_path, recursive=recursive)
        tracks = loader.load_tracks()
        _print_tracks(tracks)
        return

    tracks = []
    if folder_path is not None:
        loader = AudioLibraryLoader(folder_path, recursive=recursive)
        tracks = loader.load_tracks()

    player = TrackPlayer()
    if tracks:
        player.preload(tracks)

    app = TrackListApp(
        tracks=tracks,
        player=player,
        library_root=folder_path,
        recursive=recursive,
    )
    app.run()


def _print_tracks(tracks) -> None:
    if not tracks:
        click.echo("No tracks found.")
        return

    for index, track in enumerate(tracks, start=1):
        click.echo(f"{index}. {track.title} [{track.identifier}]")
        if track.transcript:
            click.echo(f"   {track.transcript[:80]}{'…' if len(track.transcript) > 80 else ''}")


if __name__ == "__main__":
    main()
