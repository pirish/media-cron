from pathlib import Path

from media_cron.metadata.models import (
    MediaServerConfig,
    MediaServerRescanResult,
    MediaServerType,
    VideoCompanionAsset,
    VideoCompanionType,
    VideoFormat,
    VideoReleaseBundle,
    VideoSpoolResult,
    VideoTrack,
    VideoWorkflowMode,
)


def test_video_workflow_mode_enum():
    assert VideoWorkflowMode.SPOOL == "spool"
    assert VideoWorkflowMode.DIRECT == "direct"
    assert VideoWorkflowMode.HYBRID == "hybrid"


def test_video_format_detection():
    assert VideoFormat.from_path(Path("movie.mkv")) == VideoFormat.MKV
    assert VideoFormat.from_path(Path("movie.mp4")) == VideoFormat.MP4
    assert VideoFormat.from_path(Path("movie.avi")) == VideoFormat.AVI
    assert VideoFormat.from_path(Path("movie.mov")) == VideoFormat.MOV
    assert VideoFormat.from_path(Path("movie.webm")) == VideoFormat.WEBM
    assert VideoFormat.from_path(Path("movie.iso")) == VideoFormat.UNKNOWN


def test_video_companion_type_detection():
    assert VideoCompanionType.from_path(Path("sub.srt")) == VideoCompanionType.SUBTITLE
    assert VideoCompanionType.from_path(Path("sub.vtt")) == VideoCompanionType.SUBTITLE
    assert VideoCompanionType.from_path(Path("sub.ass")) == VideoCompanionType.SUBTITLE
    assert VideoCompanionType.from_path(Path("poster.jpg")) == VideoCompanionType.ARTWORK
    assert VideoCompanionType.from_path(Path("fanart.png")) == VideoCompanionType.ARTWORK
    assert VideoCompanionType.from_path(Path("folder.jpg")) == VideoCompanionType.ARTWORK
    assert VideoCompanionType.from_path(Path("movie.nfo")) == VideoCompanionType.METADATA_NFO
    assert VideoCompanionType.from_path(Path("random.txt")) == VideoCompanionType.UNKNOWN


def test_video_companion_asset_tag_extraction(tmp_path):
    sub1 = tmp_path / "Movie.2024.en.srt"
    sub1.write_text("dummy")
    asset1 = VideoCompanionAsset.from_path(sub1)
    assert asset1.asset_type == VideoCompanionType.SUBTITLE
    assert asset1.language == "en"
    assert asset1.descriptor is None

    sub2 = tmp_path / "Movie.2024.eng.forced.vtt"
    sub2.write_text("dummy")
    asset2 = VideoCompanionAsset.from_path(sub2)
    assert asset2.asset_type == VideoCompanionType.SUBTITLE
    assert asset2.language == "eng"
    assert asset2.descriptor == "forced"

    sub3 = tmp_path / "Movie.2024.sdh.srt"
    sub3.write_text("dummy")
    asset3 = VideoCompanionAsset.from_path(sub3)
    assert asset3.asset_type == VideoCompanionType.SUBTITLE
    assert asset3.language is None
    assert asset3.descriptor == "sdh"

    sub4 = tmp_path / "Movie.2024.srt"
    sub4.write_text("dummy")
    asset4 = VideoCompanionAsset.from_path(sub4)
    assert asset4.language is None
    assert asset4.descriptor is None


def test_video_track_and_bundle():
    track = VideoTrack(
        path=Path("/media/show.S01E01.mkv"),
        title="Pilot",
        file_size=1024000,
        format=VideoFormat.MKV,
        show_title="Test Show",
        season_number=1,
        episode_number=1,
        resolution="1080p",
        source_quality="WEB-DL",
        video_codec="x265",
    )
    assert track.title == "Pilot"
    assert track.resolution == "1080p"
    assert not track.is_sample

    bundle = VideoReleaseBundle(
        bundle_id="bundle-1",
        root_path=Path("/media/Test.Show.S01E01"),
        release_title="Test Show S01E01",
        is_series=True,
        show_title="Test Show",
        season_number=1,
        primary_videos=[track],
    )
    assert bundle.show_title == "Test Show"
    assert len(bundle.primary_videos) == 1


def test_video_spool_result():
    res = VideoSpoolResult(
        bundle_id="b-1",
        source_dir=Path("/staging/rel"),
        target_dir=Path("/drop/rel"),
        file_count=3,
        bytes_transferred=5000,
        mode="hardlink",
        success=True,
        skipped=True,
        skip_reason="Target directory already exists in drop folder",
    )
    assert res.success
    assert res.skipped
    assert "already exists" in res.skip_reason


def test_media_server_models():
    assert MediaServerType.JELLYFIN == "jellyfin"
    assert MediaServerType.EMBY == "emby"
    assert MediaServerType.PLEX == "plex"

    cfg = MediaServerConfig()
    assert not cfg.enabled
    assert cfg.provider == "jellyfin"
    assert cfg.timeout_seconds == 5.0
    assert cfg.max_retries == 0

    res = MediaServerRescanResult(
        server_type="jellyfin",
        endpoint="http://localhost:8096/Library/Refresh",
        status_code=204,
        duration_seconds=0.15,
        success=True,
    )
    assert res.status_code == 204
    assert res.success
