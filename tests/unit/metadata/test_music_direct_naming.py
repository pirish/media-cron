from pathlib import Path

from media_cron.config import MusicConfig
from media_cron.metadata.models import (
    CompanionAssetType,
    MusicCompanionAsset,
    MusicFormat,
    MusicReleaseBundle,
    MusicTrack,
    MusicWorkflowMode,
)
from media_cron.plugins.lookup.music import MusicLookupPlugin


def test_standard_direct_library_path_formatting():
    plugin = MusicLookupPlugin(config=MusicConfig(workflow_mode=MusicWorkflowMode.DIRECT))
    track = MusicTrack(
        path=Path("/staging/01 - Dogs.flac"),
        format=MusicFormat.FLAC,
        file_size=1000,
        title="Dogs",
        artist="Pink Floyd",
        album="Animals",
        album_artist="Pink Floyd",
        track_number=1,
        year=1977,
    )
    bundle = MusicReleaseBundle(
        bundle_id="b1",
        root_path=Path("/staging"),
        album_title="Animals",
        album_artist="Pink Floyd",
        tracks=[track],
        year=1977,
    )

    dest_rel = plugin.format_destination_path(track, bundle)
    assert dest_rel == Path("Music/Pink Floyd/Animals (1977)/01 - Dogs.flac")


def test_compilation_direct_library_path_formatting():
    plugin = MusicLookupPlugin(
        config=MusicConfig(
            workflow_mode=MusicWorkflowMode.DIRECT,
            compilation_artist="Various Artists",
        )
    )
    track1 = MusicTrack(
        path=Path("/staging/01 - Song A.mp3"),
        format=MusicFormat.MP3,
        file_size=1000,
        title="Song A",
        artist="Artist A",
        album="Top Hits",
        track_number=1,
        year=2000,
    )
    track2 = MusicTrack(
        path=Path("/staging/02 - Song B.mp3"),
        format=MusicFormat.MP3,
        file_size=1000,
        title="Song B",
        artist="Artist B",
        album="Top Hits",
        track_number=2,
        year=2000,
    )
    bundle = MusicReleaseBundle(
        bundle_id="b2",
        root_path=Path("/staging"),
        album_title="Top Hits",
        album_artist="Various Artists",
        tracks=[track1, track2],
        is_compilation=True,
        year=2000,
    )

    dest_rel1 = plugin.format_destination_path(track1, bundle)
    assert dest_rel1 == Path("Music/Various Artists/Top Hits (2000)/01 - Song A.mp3")


def test_multi_disc_direct_library_path_formatting():
    plugin = MusicLookupPlugin(config=MusicConfig(workflow_mode=MusicWorkflowMode.DIRECT))
    track = MusicTrack(
        path=Path("/staging/CD2/01 - Hey You.flac"),
        format=MusicFormat.FLAC,
        file_size=1000,
        title="Hey You",
        artist="Pink Floyd",
        album="The Wall",
        album_artist="Pink Floyd",
        track_number=1,
        disc_number=2,
        year=1979,
    )
    bundle = MusicReleaseBundle(
        bundle_id="b3",
        root_path=Path("/staging"),
        album_title="The Wall",
        album_artist="Pink Floyd",
        tracks=[track],
        total_discs=2,
        year=1979,
    )

    dest_rel = plugin.format_destination_path(track, bundle)
    assert dest_rel == Path("Music/Pink Floyd/The Wall (1979)/CD2/01 - Hey You.flac")


def test_companion_direct_library_path_formatting():
    plugin = MusicLookupPlugin(config=MusicConfig(workflow_mode=MusicWorkflowMode.DIRECT))
    companion = MusicCompanionAsset(
        path=Path("/staging/cover.jpg"),
        asset_type=CompanionAssetType.COVER_ART,
        file_size=500,
    )
    bundle = MusicReleaseBundle(
        bundle_id="b4",
        root_path=Path("/staging"),
        album_title="Animals",
        album_artist="Pink Floyd",
        companion_assets=[companion],
        year=1977,
    )

    dest_rel = plugin.format_companion_destination_path(companion, bundle)
    assert dest_rel == Path("Music/Pink Floyd/Animals (1977)/cover.jpg")
