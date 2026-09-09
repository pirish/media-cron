from pathlib import Path

from media_cron.metadata.models import (
    CompanionAssetType,
    MusicCompanionAsset,
    MusicFormat,
    MusicReleaseBundle,
    MusicSpoolResult,
    MusicTrack,
)


def test_music_format_detection():
    assert MusicFormat.from_path(Path("song.mp3")) == MusicFormat.MP3
    assert MusicFormat.from_path(Path("song.flac")) == MusicFormat.FLAC
    assert MusicFormat.from_path(Path("song.m4a")) == MusicFormat.M4A
    assert MusicFormat.from_path(Path("song.aac")) == MusicFormat.M4A
    assert MusicFormat.from_path(Path("song.ogg")) == MusicFormat.OGG
    assert MusicFormat.from_path(Path("song.opus")) == MusicFormat.OPUS
    assert MusicFormat.from_path(Path("song.wav")) == MusicFormat.WAV
    assert MusicFormat.from_path(Path("song.alac")) == MusicFormat.ALAC
    assert MusicFormat.from_path(Path("song.aiff")) == MusicFormat.AIFF
    assert MusicFormat.from_path(Path("song.xyz")) == MusicFormat.UNKNOWN


def test_companion_asset_detection():
    assert CompanionAssetType.from_path(Path("cover.jpg")) == CompanionAssetType.COVER_ART
    assert CompanionAssetType.from_path(Path("folder.png")) == CompanionAssetType.COVER_ART
    assert CompanionAssetType.from_path(Path("front.jpeg")) == CompanionAssetType.COVER_ART
    assert CompanionAssetType.from_path(Path("album.cue")) == CompanionAssetType.CUE_SHEET
    assert CompanionAssetType.from_path(Path("rip.log")) == CompanionAssetType.RIP_LOG
    assert CompanionAssetType.from_path(Path("cd.accurip")) == CompanionAssetType.RIP_LOG
    assert CompanionAssetType.from_path(Path("playlist.m3u")) == CompanionAssetType.PLAYLIST
    assert CompanionAssetType.from_path(Path("playlist.m3u8")) == CompanionAssetType.PLAYLIST
    assert CompanionAssetType.from_path(Path("info.nfo")) == CompanionAssetType.OTHER


def test_music_track_and_bundle_dataclasses():
    track1 = MusicTrack(
        path=Path("/music/01.flac"),
        format=MusicFormat.FLAC,
        file_size=25000000,
        title="Track One",
        artist="Artist A",
        album="Album One",
        track_number=1,
        year=2021,
    )
    companion = MusicCompanionAsset(
        path=Path("/music/cover.jpg"),
        asset_type=CompanionAssetType.COVER_ART,
        file_size=50000,
    )
    bundle = MusicReleaseBundle(
        bundle_id="b123",
        root_path=Path("/music"),
        album_title="Album One",
        album_artist="Artist A",
        tracks=[track1],
        companion_assets=[companion],
        year=2021,
    )
    assert bundle.album_title == "Album One"
    assert len(bundle.tracks) == 1
    assert bundle.tracks[0].title == "Track One"
    assert len(bundle.companion_assets) == 1
    assert bundle.companion_assets[0].asset_type == CompanionAssetType.COVER_ART


def test_music_spool_result():
    res = MusicSpoolResult(
        bundle_id="b1",
        source_dir=Path("/src/album"),
        target_dir=Path("/drop/album"),
        file_count=12,
        bytes_transferred=100000,
        mode="hardlink",
        success=True,
        post_command_executed=True,
        post_command_exit_code=0,
    )
    assert res.success is True
    assert res.post_command_exit_code == 0
