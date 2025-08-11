import argparse
import random
from pathlib import Path
from typing import override

from mutagen._file import File as MutagenFile
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Label, ListItem, ListView

AUDIO_EXTS = {'.mp3', '.ogg', '.flac', '.wav', '.aac', '.m4a', '.opus'}


class ListPicker(App):
    """Textual app that renders a list and captures the chosen item."""

    CSS = """
    Screen {
        align: center middle;
    }
    ListView {
        width: 60%;
        height: 60%;
    }
    Label.instruction {
        text-style: bold;
        color: yellow;
    }
    """

    def __init__(self, instruction: str, values: list[str]) -> None:
        """Initialize the app with a list of values to display."""
        super().__init__()
        self._values: list[str] = values
        self.selection: str | None = None
        self._instruction = instruction

    @override
    def compose(self) -> ComposeResult:
        """Create the ListView and populate it with items."""
        yield Label(self._instruction, classes='instruction')
        yield ListView(*(ListItem(Label(v)) for v in self._values))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Store the selected value and exit the app."""
        label = event.item.query_one(Label)
        self.selection = str(label.renderable)
        self.exit()

    def on_key(self, event: Key) -> None:
        """Allow quitting with 'q' without making a selection."""
        if event.key == 'q':
            self.exit()


def select_value(
    instruction: str,
    values: list[str],
    /,
) -> str | None:
    """
    Run the picker and return the selected value, or None if nothing was chosen.

    Args:
        values: The list of string options to show.

    Returns:
        The chosen string, or None if the user quits.
    """
    app = ListPicker(instruction, values)
    app.run()
    return app.selection


def is_audio_file(
    path: Path,
    /,
) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


def get_audio_files(
    directory: Path,
    /,
) -> list[Path]:
    return sorted([p for p in directory.iterdir() if p.is_file() and is_audio_file(p)])


def get_average_duration(
    paths: list[Path],
    /,
) -> float:
    durations = []
    for p in paths:
        try:
            audio = MutagenFile(p)
            if audio and audio.info:
                durations.append(audio.info.length)
        except Exception:
            continue
    return sum(durations) / len(durations) if durations else 0


def seconds_to_hms(
    seconds: float,
    /,
) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def create_playlist(
    tracks: list[Path],
    ad_file: Path,
    songs_between_ads: int,
    /,
) -> list[Path]:
    random.shuffle(tracks)
    i = 0
    playlist: list = []
    while i < len(tracks):
        chunk = tracks[i : i + songs_between_ads]
        playlist.extend(chunk)
        if ad_file and len(chunk) == songs_between_ads:
            playlist.append(ad_file)
        i += songs_between_ads
    return playlist


def main():
    parser = argparse.ArgumentParser(
        prog='jukebox',
        description='Generates a playlist with ads inserted every X minutes.',
    )

    parser.add_argument(
        '--ad-every',
        type=int,
        default=15,
        help='Minutes between ads (integer).',
    )
    parser.add_argument(
        '-md',
        '--music-directory',
        required=True,
        type=Path,
        help='MPD music directory.',
    )
    parser.add_argument(
        '-pd',
        '--playlist-directory',
        required=True,
        type=Path,
        help='MPD playlists directory.',
    )

    args = parser.parse_args()

    ad_every: int = args.ad_every
    music_directory: Path = args.music_directory
    playlist_directory: Path = args.playlist_directory

    if ad_every < 0:
        parser.exit(1, '❌ Minutes between ads must be positive number')

    if not music_directory.exists():
        parser.exit(1, '❌ Music directory does not exist.')

    if not playlist_directory.exists():
        parser.exit(1, '❌ Playlists directory does not exist.')

    ads_folder = select_value(
        'Select the ads folder',
        [path.name for path in music_directory.iterdir() if path.is_dir()],
    )
    if not ads_folder:
        parser.exit(1, '❌ An ads folder must be chosen.')
    (ads_folder,) = [
        path for path in music_directory.iterdir() if path.name == ads_folder
    ]

    ad_file = select_value(
        'Select the ad file',
        [path.name for path in ads_folder.iterdir() if path.is_file()],
    )
    if not ad_file:
        parser.exit(1, '❌ An ad file must be chosen.')
    (ad_file,) = [path for path in ads_folder.iterdir() if path.name == ad_file]

    music_folder = select_value(
        'Select the music folder',
        [path.name for path in music_directory.iterdir() if path.is_dir()],
    )
    if not music_folder:
        parser.exit(1, '❌ A music folder must be chosen.')
    (music_folder,) = [
        path for path in music_directory.iterdir() if path.name == music_folder
    ]

    tracks = get_audio_files(music_folder)
    if not tracks:
        print('❌ No audio files found.')
        return

    avg_duration = get_average_duration(tracks)
    total_duration = 0
    playlist = (
        create_playlist(
            tracks,
            ad_file,
            max(1, round((args.ad_every * 60) / avg_duration)),
        )
        if ad_file and avg_duration > 0
        else tracks
    )
    for p in playlist:
        try:
            audio = MutagenFile(p)
            if audio and audio.info:
                total_duration += audio.info.length or 0
        except Exception:
            continue

    if avg_duration == 0:
        print('⚠️ Could not calculate average song duration. No ads will be inserted.')
        songs_between_ads = 0
    else:
        songs_between_ads = max(1, round((args.ad_every * 60) / avg_duration))
        print(
            f'⏱ Estimated total playlist duration: {seconds_to_hms(total_duration)} (HH:MM:SS).'
        )
        print(
            f'ℹ️ Ads will be inserted approximately every {songs_between_ads} songs (avg song length {avg_duration / 60:.2f} minutes).'
        )

    playlist_file = playlist_directory / 'jukebox.m3u'
    with playlist_file.open('w') as f:
        f.write(
            '\n'.join(str(path.relative_to(path.parent.parent)) for path in playlist)
        )


if __name__ == '__main__':
    main()
